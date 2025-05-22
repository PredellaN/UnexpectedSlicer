from typing import Any, Callable
import os
import requests
from requests.auth import HTTPDigestAuth
from concurrent.futures import ThreadPoolExecutor, as_completed

from .host_confs import host_configs

def get_api_responses(
    host: str,
    port: int,
    endpoints: list[str],
    username: str,
    password: str,
    max_workers: int = 5
) -> dict[str, dict]:
    def fetch(endpoint: str) -> tuple[str, dict]:
        url = f"http://{host}:{port}{endpoint}"
        print(f"querying {url}")
        try:
            resp = requests.get(
                url,
                auth=HTTPDigestAuth(username, password),
                timeout=2.0
            )
            resp.raise_for_status()
            return endpoint, resp.json()
        except Exception as e:
            return endpoint, {"error": str(e)}

    responses: dict[str, dict] = {}
    worker_count = min(max_workers, len(endpoints)) or 1
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_to_ep = {pool.submit(fetch, ep): ep for ep in endpoints}
        for future in as_completed(future_to_ep):
            ep, result = future.result()
            responses[ep] = result

    return responses

def get_nested(data, default, type, *keys):
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k)
        if data is None:
            return default
    return type(data)


from typing import TypedDict, Optional
class PrinterResponse(TypedDict):
    name: str
    host_type: str
    ip: str
    port: int
    username: str
    password: str
    progress: float
    state: str
    job_name: Optional[str]
    job_id: Optional[str]

def process_prusalink(printer: dict):
    endpoints = [
        '/api/v1/status',
        '/api/v1/info',
        '/api/v1/job'
    ]

    api_data = get_api_responses(
        host=printer['ip'],
        port=int(printer['port']),
        endpoints=endpoints,
        username=printer['username'],
        password=printer['password'],
    )
    
    response: PrinterResponse = {
        'name': str(printer['name']),
        'host_type': str(printer['host_type']),
        'ip': str(printer['ip']),
        'port': int(printer['port']),
        'username': str(printer['username']),
        'password': str(printer['password']),
        'progress': get_nested(api_data, 0, float, '/api/v1/job', 'job', 'progress'),
        'state': get_nested(api_data,  'OFFLINE', str, '/api/v1/status', 'printer', 'state'),
        'job_name': get_nested(api_data, None, str, '/api/v1/job', 'file', 'display_name'),
        'job_id': get_nested(api_data, None, str, '/api/v1/status', 'job', 'id'),
    }

    return response

def process_creality(printer: dict):
    endpoints = [
        '/protocal.csp?fname=Info&opt=main&function=get'
    ]

    api_data = get_api_responses(
        host=printer['ip'],
        port=int(printer['port']),
        endpoints=endpoints,
        username=printer['username'],
        password=printer['password'],
    )
    
    response: PrinterResponse = {
        'name': str(printer['name']),
        'host_type': str(printer['host_type']),
        'ip': str(printer['ip']),
        'port': int(printer['port']),
        'username': str(printer['username']),
        'password': str(printer['password']),
        'progress': round(get_nested(api_data, 0, float, endpoints[0], 'printProgress'), 1),
        'state': {'0': "IDLE", '1': "PRINTING"}.get(get_nested(api_data,  'OFFLINE', str, endpoints[0], 'mcu_is_print'), "UNKNOWN"),
        'job_name': get_nested(api_data, None, str, endpoints[0], 'print'),
        'job_id': None,
    }

    return response

def process_moonraker(printer: dict):
    endpoints = [
        "/printer/objects/query?webhooks&virtual_sdcard&print_stats",
        "/printer/info"
    ]

    api_data = get_api_responses(
        host=printer['ip'],
        port=int(printer['port']),
        endpoints=endpoints,
        username=printer['username'],
        password=printer['password'],
    )
    
    response: PrinterResponse = {
        'name': str(printer['name']),
        'host_type': str(printer['host_type']),
        'ip': str(printer['ip']),
        'port': int(printer['port']),
        'username': str(printer['username']),
        'password': str(printer['password']),
        'progress': round(get_nested(api_data, 0, float, endpoints[0], "result", "status", "virtual_sdcard", "progress") * 100, 1),
        'state': get_nested(api_data,  'OFFLINE', str, endpoints[0], "result", "status", "print_stats", "state").upper(),
        'job_name': None,
        'job_id': None,
    }

    return response

def process_printer(printer: dict[str, str]) -> dict[str, Any]:
    host_type = printer["host_type"]

    func: Callable = globals().get(f'process_{host_type}') #type: ignore
    print(f'process_{host_type}')
    resp: dict[str, str | dict] = func(printer)

    return resp

def collect_printer_data(printers: list[dict[str, str]], max_workers: int = 10) -> dict[str, dict]:
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

def collection_to_dict_list(coll):
    return [
        {p.identifier: getattr(item, p.identifier)
         for p in item.bl_rna.properties
         if not p.is_readonly and p.identifier != "rna_type"}
        for item in coll
    ]

def process_printers(printers_pointer) -> dict[str, dict]:
    processed = collect_printer_data(collection_to_dict_list(printers_pointer))
    return {p['name']: processed[p['name']] for p in printers_pointer if p['name'] in processed}