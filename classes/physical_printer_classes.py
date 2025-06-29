from __future__ import annotations
from concurrent.futures._base import Future
from pathlib import Path

from gpu import state
from requests.models import Response
from typing import TYPE_CHECKING, Any, Callable, Never
if TYPE_CHECKING:
    from typing import Any
    from requests import Response

import requests
from requests.exceptions import RequestException

import bpy
import os
import time
from functools import wraps
from datetime import datetime, timezone

import threading
from concurrent.futures import ThreadPoolExecutor

if bpy.context.preferences:
    _max_conn = getattr(bpy.context.preferences.system, 'network_connection_limit', 1)
    _timeout = timeout=bpy.context.preferences.system.network_timeout
    _executor = ThreadPoolExecutor(max_workers=_max_conn)
    _lock = threading.Lock()

# Utility to safely traverse nested dicts
def get_nested(data: None | dict[str, Any], default: Any, typ: type, *keys: str) -> Any:
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k)
        if data is None:
            return default
    return typ(data)

# State wrapper
def with_api_state(state: str) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Any:
        @wraps(func)
        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            self.state = state
            try: return func(self, *args, **kwargs)
            finally: self.state = ''
        return wrapped
    return decorator

# Map HTTP methods to requests functions
method_map = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "DELETE": requests.delete,
}

from dataclasses import dataclass
@dataclass
class PrinterQueryResponse:
    progress: float = 0.0
    state: str = "OFFLINE"
    job_name: str = ""
    job_id: str = ""
    nozzle_temperature: float = 0.0
    bed_temperature: float = 0.0

class PrinterAPIException(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)   # sets the exception’s message
        self.code = code            # store your extra value

class PrinterException(Exception): pass
class UnhandledPrinterException(Exception): pass

class APIInterface:
    endpoints: list[str] = []
    
    def __init__(self, host: str, port: int, prefix: str, username: str, password: str) -> None:
        self.host: str = host
        self.port: int = port
        self.prefix: str = prefix
        self.username: str = username
        self.auth_header = {}
        self._authentication_header(username, password)
        self.api_state: str = ''
        self.command_time: datetime | None = None
        self.command_response: str = ''

    def _authentication_header(self, username: str , password: str) -> None:
        pass

    def send_request(self, endpoint: str, method: str, headers: dict[str, str] = {}, filepath: Path | None = None) -> Response:
        if not bpy.app.online_access:
            raise Exception(f"Online access not allowed!")
        
        url: str = f"http://{self.host}:{self.port}{self.prefix}{endpoint}"
        
        try:
            response: Response = method_map[method](
                url,
                headers={**headers, **self.auth_header},
                data=open(filepath, 'rb') if filepath else None,
                timeout=_timeout,
            )
        except RequestException:
            raise RequestException(f"Request to {url} failed")

        try:
            response.raise_for_status()
        except RequestException:
            raise PrinterAPIException(f"Request to {url} failed with code {response.status_code}", response.status_code)

        return response

    def get_api_responses(self) -> dict[str, dict[str, str]]:
        responses: dict[str, dict[str, str]] = {}

        for ep in self.endpoints:
            res: Response = self.send_request(ep, 'GET')
            if res.status_code == 200: responses[ep] = res.json(); continue
            elif res.status_code == 204: responses[ep] = {}; continue

        return responses

    def query_state(self) -> PrinterQueryResponse:
        return PrinterQueryResponse()

    def _get_storage_path(self) -> str | None: raise NotImplementedError("get_storage_path not implemented for this backend")
    def _pause_print(self) -> dict[str, Any]: raise NotImplementedError("pause_print not implemented for this backend")
    def _resume_print(self) -> dict[str, Any]: raise NotImplementedError("resume_print not implemented for this backend")
    def _stop_print(self) -> dict[str, Any]: raise NotImplementedError("stop_print not implemented for this backend")
    def _upload_file(self, storage_path: str, filepath: Path, filename: str) -> str: raise NotImplementedError("upload_file not implemented for this backend")
    def _start_file(self, storage_path: str, filename: str) -> str: raise NotImplementedError("start_file not implemented for this backend")

    def _start_print(self, gcode_filepath: Path, filename: str) -> None:
        storage_path = self._get_storage_path()
        print(f"Determined storage path: {storage_path}")
        if not storage_path:
            print("Error: Could not determine storage path.")
            return
        res = self._upload_file(storage_path, gcode_filepath, filename)
        print(f"Uploaded file {gcode_filepath} -> {storage_path}")
        res = self._start_file(storage_path, filename)
        print(f"Print job started: {filename} on storage '{storage_path}'")
        self.query_state()

    def _with_executor(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        f: Future[Any] = _executor.submit(func, *args, **kwargs)
        self._reset_message()

        def _handle_future(fut) -> None: 
            if exc:= fut.exception(): self._set_message(exc)

        f.add_done_callback(_handle_future)

    def _reset_message(self) -> None:
        self.command_time = None

    def _set_message(self, exc) -> None:
        self.command_time = datetime.now(timezone.utc)
        self.command_response = str(exc)

    def get_storage_path(self) -> str | None: self._with_executor(self._get_storage_path)
    def pause_print(self) -> None: self._with_executor(self._pause_print)
    def resume_print(self) -> None: self._with_executor(self._resume_print)
    def stop_print(self) -> None: self._with_executor(self._stop_print)
    def upload_file(self, storage_path: str, filepath: Path, filename: str) -> None: self._with_executor(self._upload_file, storage_path, filepath, filename)
    def start_file(self, storage_path: str, filename: str) -> None: self._with_executor(self._start_file, storage_path, filename)
    def start_print(self, filepath: Path, filename: str) -> None: self._with_executor(self._start_print, filepath, filename)
    
    @staticmethod
    def _handle_response_code(base: str, e: PrinterAPIException) -> Never:
        if e.code == 400: raise PrinterException(f'{base}: Bad request')
        if e.code == 401: raise PrinterException(f'{base}: Unauthorized, check your authentication settings')
        if e.code == 403: raise PrinterException(f'{base}: Forbidden')
        if e.code == 404: raise PrinterException(f'{base}: Not found')
        if e.code == 408: raise PrinterException(f'{base}: Request timed out')
        if e.code == 409: raise PrinterException(f'{base}: Printer currently busy')
        if e.code == 503: raise PrinterException(f'{base}: Service unavailable')
        else: raise UnhandledPrinterException(f'{base}: Unhandled response code {e}')

class Prusalink(APIInterface):
    endpoints: list[str] = [
        '/api/v1/status',
        '/api/v1/info',
        '/api/v1/job'
    ]

    def _authentication_header(self, username: str, password: str):
        self.auth_header = {}
        self.auth_header['X-Api-Key'] = password

    def query_state(self) -> PrinterQueryResponse:
        api_data: dict[str, dict[str, str]]  = self.get_api_responses()
        return PrinterQueryResponse(
            progress=get_nested(api_data, 0.0, float, '/api/v1/job', 'progress'),
            state=get_nested(api_data, 'OFFLINE', str, '/api/v1/status', 'printer', 'state'),
            job_name=get_nested(api_data, None, str, '/api/v1/job', 'file', 'display_name'),
            job_id=get_nested(api_data, None, str, '/api/v1/status', 'job', 'id'),
            nozzle_temperature=get_nested(api_data, '0', str, '/api/v1/status', 'printer', 'temp_nozzle'),
            bed_temperature=get_nested(api_data, '0', str, '/api/v1/status', 'printer', 'temp_bed'),
        )

    @with_api_state('GETTING STORAGE PATH')
    def _get_storage_path(self) -> str:
        try:
            res: Response = self.send_request( '/api/v1/storage', 'GET')
        except PrinterAPIException as e:
            base_str = f"Failed to request storage path"
            if e.code == 401: raise PrinterException(f'{base_str}: Unauthorized, check your authentication settings')
            else: raise UnhandledPrinterException(f'{base_str}: Unhandled response code {e}')

        if res.status_code == 204: raise PrinterException('Unable to determine the storage path to copy the file!')

        storage_list = res.json().get('storage_list', [])
        writable = [s for s in storage_list if s.get('available') and not s.get('read_only')]
        if not writable: raise PrinterException('No writable storages detected! Make sure a properly formatted USB drive is plugged in the printer.')

        return writable[0]['path'].lstrip('/')

    @with_api_state('PAUSING')
    def _pause_print(self) -> dict[str, Any]:
        if not (job_id := self.query_state().job_id):
            raise PrinterException("No job available to pause!")

        try:
            res: Response = self.send_request( f'/api/v1/job/{job_id}/pause', 'PUT')
        except PrinterAPIException as e: self._handle_response_code(f"Failed to pause Job {job_id}", e)
        
        return res.json()

    @with_api_state('RESUMING')
    def _resume_print(self) -> dict[str, Any]:
        if not (job_id := self.query_state().job_id):
            raise PrinterException("No job available to resume!")

        try:
            res: Response = self.send_request( f'/api/v1/job/{job_id}/resume', 'PUT')
        except PrinterAPIException as e: self._handle_response_code(f"Failed to resume Job {job_id}", e)

        return res.json()

    @with_api_state('STOPPING')
    def _stop_print(self) -> dict[str, Any]:
        if not (job_id := self.query_state().job_id):
            raise PrinterException("No job available to stop!")

        try:
            res: Response = self.send_request( f'/api/v1/job/{job_id}', 'DELETE')
        except PrinterAPIException as e: self._handle_response_code(f"Failed to stop Job {job_id}", e)
        
        return res.json()

    @with_api_state('UPLOADING')
    def _upload_file(self, storage_path: str, filepath: Path, filename: str) -> dict[str, Any]:
        headers = {
            'Overwrite': '?1',
            'Print-After-Upload': '?1',
        }

        try:
            res = self.send_request( f'/api/v1/files/{storage_path}{filename}', 'PUT', headers, filepath)
        except PrinterAPIException as e: self._handle_response_code(f"Failed to upload {filename} to {storage_path}", e)
            
        return res.json()

    @with_api_state('STARTING')
    def _start_file(self, storage_path: str, filename: str) -> dict[str, Any]:
        try:
            res = self.send_request( f"/api/v1/files/{storage_path}{filename}", 'POST')
        except PrinterAPIException as e: self._handle_response_code(f"Failed to start print {filename}", e)

        return res.json()

class Creality(APIInterface):
    endpoints: list[str] = [
        '/protocal.csp?fname=Info&opt=main&function=get'
    ]

    def query_state(self) -> PrinterQueryResponse:
        api_data  = self.get_api_responses()
        progress = round(get_nested(api_data, 0.0, float, self.endpoints[0], 'printProgress'), 1)
        state_id = get_nested(api_data, '-1', str, self.endpoints[0], 'state')
        state = (
            'OFFLINE' if state_id == '-1' else
            'PAUSED' if state_id == '5' else
            'IDLE' if state_id in ['0', '3', '4'] else
            'PRINTING' if state_id == '1' else
            'FINISHED' if state_id == '2' else
            'UNKNOWN'
        )
        return PrinterQueryResponse(
            progress,
            state,
            job_name=get_nested(api_data, None, str, self.endpoints[0], 'print'),
            job_id='',
            nozzle_temperature=get_nested(api_data, 0.0, float, self.endpoints[0], 'nozzleTemp'),
            bed_temperature=get_nested(api_data, 0.0, float, self.endpoints[0], 'bedTemp'),
        )

    def _get_storage_path(self) -> str | None:
        return '/mmcblk0p1/creality/gztemp/'

    @with_api_state('PAUSING')
    def _pause_print(self) -> dict[str, Any]:
        res = self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=1',
            'GET'
        )
        return res.json()

    @with_api_state('RESUMING')
    def _resume_print(self) -> dict[str, Any]:
        res = self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=0',
            'GET'
        )
        return res.json()

    @with_api_state('STOPPING')
    def _stop_print(self) -> dict[str, Any]:
        res = self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&stop=1',
            'GET'
        )
        return res.json()

    @with_api_state('UPLOADING')
    def _upload_file(self, storage_path: str, filepath: Path, filename: str) -> None:
        from ..functions.basic_functions import ftp_upload, ftp_wipe
        ftp_wipe(self.host, storage_path)
        ftp_upload(self.host, filepath, storage_path, filename, overwrite=True, timeout=_timeout)

    @with_api_state('STARTING')
    def _start_file(self, storage_path: str, filename: str) -> None:
        endpoint = (
            f"/protocal.csp?fname=net&opt=iot_conf&function=set&print=/media/mmcblk0p1/creality/gztemp/{filename}"
        )
        self.send_request(endpoint, 'GET')

class Moonraker(APIInterface):
    endpoints: list[str] = [
        '/printer/objects/query?webhooks&virtual_sdcard&print_stats',
        '/printer/info'
    ]

    def query_state(self) -> PrinterQueryResponse:
        api_data  = self.get_api_responses()
        state = get_nested(
                api_data, 'OFFLINE', str,
                self.endpoints[0], 'result', 'status', 'print_stats', 'state'
            ).upper()
        state = 'IDLE' if state == 'STANDBY' else state
        return PrinterQueryResponse(
            round(
                get_nested(api_data, 0.0, float,
                           self.endpoints[0], 'result', 'status', 'virtual_sdcard', 'progress') * 100,
                1
            ),
            state,
            get_nested(api_data, None, str, self.endpoints[0], 'result', 'status', 'virtual_sdcard', 'file_path'),
            '',
        )

    def _pause_print(self) -> dict[str, Any]: raise NotImplementedError("pause_print not implemented for Moonraker")
    def _resume_print(self) -> dict[str, Any]: raise NotImplementedError("resume_print not implemented for Moonraker")
    def _stop_print(self) -> dict[str, Any]: raise NotImplementedError("stop_print not implemented for Moonraker")

class Printer:
    interface: APIInterface

    def __init__(
        self,
        name: str,
        host_type: str,
        host: str,
        port: str,
        prefix: str,
        username: str,
        password: str,
    ) -> None:
    
        self.name: str = name
        self.host_type: str = host_type
        self.host: str = host
        self.port: int = int(port) if port.isdigit() else 80
        self.username: str = username

        self.status: PrinterQueryResponse = PrinterQueryResponse()

        if host_type == 'prusalink': self.interface = Prusalink(host, self.port, prefix, username, password)
        elif host_type == 'creality': self.interface = Creality(host, self.port, prefix,username, password)
        elif host_type == 'moonraker': self.interface = Moonraker(host, self.port, prefix, username, password)
        else: self.interface = APIInterface(host, self.port, prefix, username, password)

    def query_state(self):
        self.status = self.interface.query_state()
    
    def pause_print(self):
        self.interface.pause_print()

    def resume_print(self):
        self.interface.resume_print()

    def stop_print(self):
        self.interface.stop_print()

    def start_print(self, gcode_filepath: Path, name: str):
        self.interface.start_print(gcode_filepath, name)

class PrinterQuerier:
    def __init__(
        self,
        min_interval: float = 60.0,
    ) -> None:
        self._printers: dict[str, Printer] = {}
        self._min_interval: float = min_interval
        self._last_exec: float = 0.0

    def set_printers(self, printers_list: list[dict[str, str]]) -> None:
        print('Setting printers')
        with _lock:
            self._printers = {
                p["name"]: Printer(
                    name=p["name"],
                    host_type=p["host_type"],
                    host=p["ip"],
                    port=p["port"],
                    prefix=p["prefix"],
                    username=p["username"],
                    password=p["password"],
                )
                for p in printers_list
            }

    @property
    def printers(self) -> dict[str, Printer]:
        return dict(self._printers)

    def _safe_query(self, printer: Printer) -> None:
        try:
            printer.query_state()
        except Exception as e:
            raise Exception(f"Error updating printer '{printer.name}': {e}")

    def query(self) -> None:
        now = time.monotonic()
        with _lock:
            if now - self._last_exec < self._min_interval:
                return
            self._last_exec = now
            items: list[tuple[str, Printer]] = list(self._printers.items())

        for _, printer in items:
            _executor.submit(self._safe_query, printer)

printers_querier = PrinterQuerier()

from ..registry import register_timer
from ..functions.blender_funcs import redraw

@register_timer
def querier_timer() -> int:
    try: printers_querier.query()
    except: pass
    redraw()
    return 1