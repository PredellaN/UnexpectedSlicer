from _thread import LockType
from abc import abstractmethod

from typing import Any
from ...types.typeddicts import PrinterConf, PrinterData, PrinterResponse

import requests
from requests.auth import HTTPDigestAuth

import time
import bpy
import threading

from concurrent.futures import ThreadPoolExecutor, as_completed

def get_api_responses(
    host: str,
    port: int,
    endpoints: list[str],
    username: str,
    password: str,
) -> dict[str, dict]:
    def fetch(endpoint: str) -> tuple[str, dict]:
        if not bpy.app.online_access: return endpoint, {"error": "Online access is not allowed!"}
        
        url = f"http://{host}:{port}{endpoint}"
        print(f"querying {url}")
        try:
            resp = requests.get(
                url,
                auth=HTTPDigestAuth(username, password),
                timeout=min(2.0, bpy.context.preferences.system.network_timeout)
            )
            resp.raise_for_status()
            return endpoint, resp.json()
        except Exception as e:
            return endpoint, {"error": str(e)}

    responses: dict[str, dict] = {}

    for ep in endpoints:
        responses[ep] = fetch(ep)[1]

    return responses

def get_nested(data, default, type, *keys):
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k)
        if data is None:
            return default
    return type(data)

class PrinterProcessor():
    endpoints: list[str] = []

    def __init__(self, printer: dict[str, str]):
        self.printer = printer

    def get_api_data(self) -> dict[str, Any]:
        return get_api_responses(
            host=self.printer['ip'],
            port=int(self.printer['port']),
            endpoints=self.endpoints,
            username=self.printer['username'],
            password=self.printer['password'],
        )

    def process(self) -> PrinterResponse:
        api_data: dict[str, Any] = self.get_api_data()
        base: PrinterConf = self.build_base_response()
        data: PrinterData = self.build_response_data(api_data)

        return {**base, **data}

    def build_base_response(self) -> PrinterConf:
        return {
            'name': str(self.printer['name']),
            'host_type': str(self.printer['host_type']),
            'ip': str(self.printer['ip']),
            'port': int(self.printer['port']),
            'username': str(self.printer['username']),
            'password': str(self.printer['password']),
        }

    @abstractmethod
    def build_response_data(self, api_data: dict[str, Any]) -> PrinterData:
        pass

class PrusalinkProcessor(PrinterProcessor):
    endpoints = [
        '/api/v1/status',
        '/api/v1/info',
        '/api/v1/job'
    ]

    def build_response_data(self, api_data: dict[str, Any]) -> PrinterData:
        return {
            'progress': get_nested(api_data, 0, float, '/api/v1/job', 'progress'),
            'state': get_nested(api_data,  'OFFLINE', str, '/api/v1/status', 'printer', 'state'),
            'job_name': get_nested(api_data, None, str, '/api/v1/job', 'file', 'display_name'),
            'job_id': get_nested(api_data, None, str, '/api/v1/status', 'job', 'id'),
        }

class CrealityProcessor(PrinterProcessor):
    endpoints = [
        '/protocal.csp?fname=Info&opt=main&function=get'
    ]

    def build_response_data(self, api_data: dict[str, Any]) -> PrinterData:
        progress = round(get_nested(api_data, 0, float, self.endpoints[0], 'printProgress'), 1)
        paused   = get_nested(api_data, 'OFFLINE', str, self.endpoints[0], 'pause')
        state = (
            "PAUSED"   if progress > 0 and paused == '1' else
            "PRINTING" if progress > 0             else
            "IDLE"     if progress == 0            else
            "UNKNOWN"
        )
        return {
            'progress': progress,
            'state': state,
            'job_name': get_nested(api_data, None, str, self.endpoints[0], 'print'),
            'job_id': None,
        }

class MoonrakerProcessor(PrinterProcessor):
    endpoints = [
        "/printer/objects/query?webhooks&virtual_sdcard&print_stats",
        "/printer/info"
    ]

    def build_response_data(self, api_data: dict[str, Any]) -> PrinterData:
        return {
            'progress': round(get_nested(api_data, 0, float, self.endpoints[0], "result", "status", "virtual_sdcard", "progress") * 100, 1),
            'state': get_nested(api_data,  'OFFLINE', str, self.endpoints[0], "result", "status", "print_stats", "state").upper(),
            'job_name': None,
            'job_id': None,
        }

def process_printer(printer: dict[str, str]) -> PrinterResponse | None:
    host_type = printer["host_type"]

    proc = None
    if host_type == 'prusalink': proc = PrusalinkProcessor(printer)
    elif host_type == 'creality': proc = CrealityProcessor(printer)
    elif host_type == 'moonraker': proc = MoonrakerProcessor(printer)

    if not proc: return None

    resp: PrinterResponse = proc.process()

    return resp

def collect_printer_data(printers: list[dict[str, str]], max_workers: int = 5) -> dict[str, dict]:
    results: dict[str, dict] = {}
    # cap workers to avoid unbounded threads
    worker_count = min(max_workers, len(printers)) or 1
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_to_name = {
            pool.submit(process_printer, p): p['name'] for p in printers
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = {'error': str(e)}
    return results

def process_printers(printers) -> dict[str, dict]:
    processed = collect_printer_data(printers, max_workers=bpy.context.preferences.system.network_connection_limit)
    return {p['name']: processed[p['name']] for p in printers if p['name'] in processed}

class PrinterQuerier:
    printers: list[dict] = []
    min_interval: float = 60.0
    _last_exec: float = 0.0
    _lock: LockType = threading.Lock()
    data: dict[str, dict] = {}

    def _refresh(self):
        try:
            new_data = process_printers(self.printers)
            now = time.monotonic()

            self.data = new_data
            self._last_exec = now
        finally:
            self._lock.release()

    def query(self):
        now = time.monotonic()

        if now - self._last_exec >= self.min_interval:
            acquired = self._lock.acquire(blocking=False)
            if acquired:
                t = threading.Thread(target=self._refresh, daemon=True)
                t.start()

printers_querier = PrinterQuerier()