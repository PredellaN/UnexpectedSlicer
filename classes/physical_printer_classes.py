from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
if TYPE_CHECKING:
    from typing import Any
    from requests import Response #type: ignore

import requests #type: ignore
import bpy
import os
import time
from functools import wraps

import threading
from concurrent.futures import ThreadPoolExecutor
_max_conn = getattr(bpy.context.preferences.system, 'network_connection_limit', 1)
_executor = ThreadPoolExecutor(max_workers=_max_conn)
_lock = threading.Lock()
_timeout = timeout=bpy.context.preferences.system.network_timeout

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

class APIInterface:
    endpoints: list[str] = []
    state: str = ''

    auth_header = {}

    def __init__(self, ip: str, port: int, username: str, password: str):
        self.ip: str = ip
        self.port: int = port
        self.username: str = username
        self.authentication_header(username, password)

    def authentication_header(self, username: str , password: str):
        pass

    def send_request(self, endpoint: str, method: str, headers: dict[str, str] = {}, filepath: str | Path | None = None) -> dict[str, Any]:
        if not bpy.app.online_access:
            raise Exception(f"Online access not allowed!")
        
        host, rest = (self.ip.split('/', 1) + [''])[:2]
        url = f"http://{host}:{self.port}{('/' + rest) if rest else ''}{endpoint}"
        try:
            response: Response = method_map[method](
                url,
                headers={**headers, **self.auth_header},
                data=open(filepath, 'rb') if filepath else None,
                timeout=_timeout,
            )
            response.raise_for_status()

            if not response.content:
                raise requests.exceptions.RequestException(f"No content from {url}")

            return response.json()
        except requests.exceptions.RequestException:
            return {}

    def get_api_responses(self) -> dict[str, dict[str, str]]:
        responses: dict[str, Any] = {}

        for ep in self.endpoints:
            responses[ep] = self.send_request(ep, 'GET')

        return responses

    def query_state(self) -> dict[str, Any]:
        return {
            'progress': 0,
            'state': 'OFFLINE',
            'job_name': None,
            'job_id': None,
        }

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

    def get_storage_path(self) -> str | None: _executor.submit(self._get_storage_path)
    def pause_print(self) -> None: _executor.submit(self._pause_print)
    def resume_print(self) -> None: _executor.submit(self._resume_print)
    def stop_print(self) -> None: _executor.submit(self._stop_print)
    def upload_file(self, storage_path: str, filepath: Path, filename: str) -> None: _executor.submit(self._upload_file, storage_path, filepath, filename)
    def start_file(self, storage_path: str, filename: str) -> None: _executor.submit(self._start_file, storage_path, filename)
    def start_print(self, filepath: Path, filename: str) -> None: _executor.submit(self._start_print, filepath, filename)

class Prusalink(APIInterface):
    endpoints: list[str] = [
        '/api/v1/status',
        '/api/v1/info',
        '/api/v1/job'
    ]

    def authentication_header(self, username: str, password: str):
        self.auth_header = {}
        self.auth_header['X-Api-Key'] = password

    def query_state(self) -> dict[str, Any]:
        api_data  = self.get_api_responses()
        return {
            'progress': get_nested(api_data, 0.0, float, '/api/v1/job', 'progress'),
            'state': get_nested(api_data, 'OFFLINE', str, '/api/v1/status', 'printer', 'state'),
            'job_name': get_nested(api_data, None, str, '/api/v1/job', 'file', 'display_name'),
            'job_id': get_nested(api_data, None, str, '/api/v1/status', 'job', 'id'),
        }

    @with_api_state('GETTING STORAGE PATH')
    def _get_storage_path(self) -> str:
        resp = self.send_request( '/api/v1/storage', 'GET')
        if not resp:
            return ''
        storage_list = resp.get('storage_list', [])
        writable = [s for s in storage_list if s.get('available') and not s.get('read_only')]
        if not writable:
            return ''
        return writable[0]['path'].lstrip('/')

    @with_api_state('PAUSING')
    def _pause_print(self) -> dict[str, Any]:
        if not (job_id := self.query_state()['job_id']):
            print("No job ID available to pause.")
            return {}
        return self.send_request( f'/api/v1/job/{job_id}/pause', 'PUT')

    @with_api_state('RESUMING')
    def _resume_print(self) -> dict[str, Any]:
        if not (job_id := self.query_state()['job_id']):
            print("No job ID available to resume.")
            return {}
        return self.send_request( f'/api/v1/job/{job_id}/resume', 'PUT')

    @with_api_state('STOPPING')
    def _stop_print(self) -> dict[str, Any]:
        if not (job_id := self.query_state()['job_id']):
            print("No job ID available to stop.")
            return {}
        return self.send_request( f'/api/v1/job/{job_id}', 'DELETE')

    @with_api_state('UPLOADING')
    def _upload_file(self, storage_path: str, filepath: Path, filename: str) -> dict[str, Any]:
        headers = {
            'Overwrite': '?1',
            'Print-After-Upload': '?1',
        }
        return self.send_request( f'/api/v1/files/{storage_path}{filename}', 'PUT', headers, filepath)

    @with_api_state('STARTING')
    def _start_file(self, storage_path: str, filename: str) -> dict[str, Any]:
        return self.send_request( f"/api/v1/files/{storage_path}{filename}", 'POST')

class Creality(APIInterface):
    endpoints: list[str] = [
        '/protocal.csp?fname=Info&opt=main&function=get'
    ]

    def query_state(self) -> dict[str, Any]:
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
        return {
            'progress': progress,
            'state': state,
            'job_name': get_nested(api_data, None, str, self.endpoints[0], 'print'),
            'job_id': None,
        }

    def _get_storage_path(self) -> str | None:
        return '/mmcblk0p1/creality/gztemp/'

    @with_api_state('PAUSING')
    def _pause_print(self) -> dict[str, Any]:
        return self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=1',
            'GET'
        )

    @with_api_state('RESUMING')
    def _resume_print(self) -> dict[str, Any]:
        return self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=0',
            'GET'
        )

    @with_api_state('STOPPING')
    def _stop_print(self) -> dict[str, Any]:
        return self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&stop=1',
            'GET'
        )

    @with_api_state('UPLOADING')
    def _upload_file(self, storage_path: str, filepath: Path, filename: str) -> None:
        from ..functions.basic_functions import ftp_upload, ftp_wipe
        ftp_wipe(self.ip, storage_path)
        ftp_upload(self.ip, filepath, storage_path, filename, overwrite=True, timeout=_timeout)

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

    def query_state(self) -> dict[str, Any]:
        api_data  = self.get_api_responses()
        state = get_nested(
                api_data, 'OFFLINE', str,
                self.endpoints[0], 'result', 'status', 'print_stats', 'state'
            ).upper()
        state = 'IDLE' if state == 'STANDBY' else state
        return {
            'progress': round(
                get_nested(api_data, 0.0, float,
                           self.endpoints[0], 'result', 'status', 'virtual_sdcard', 'progress') * 100,
                1
            ),
            'state': state,
            'job_name': get_nested(api_data, None, str, self.endpoints[0], 'result', 'status', 'virtual_sdcard', 'file_path'),
            'job_id': None,
        }

    def _pause_print(self) -> dict[str, Any]: raise NotImplementedError("pause_print not implemented for Moonraker")
    def _resume_print(self) -> dict[str, Any]: raise NotImplementedError("resume_print not implemented for Moonraker")
    def _stop_print(self) -> dict[str, Any]: raise NotImplementedError("stop_print not implemented for Moonraker")

class Printer:
    progress: float = 0
    state: str = ''
    job_name: str = ''
    job_id: str = ''

    interface: APIInterface

    def __init__(
        self,
        name: str,
        host_type: str,
        ip: str,
        port: str,
        username: str,
        password: str,
    ) -> None:
    
        self.name: str = name
        self.host_type: str = host_type
        self.ip: str = ip
        self.port: int = int(port) if port.isdigit() else 80
        self.username: str = username

        if host_type == 'prusalink': self.interface = Prusalink(ip, self.port, username, password)
        elif host_type == 'creality': self.interface = Creality(ip, self.port, username, password)
        elif host_type == 'moonraker': self.interface = Moonraker(ip, self.port, username, password)
        else: self.interface = APIInterface(ip, self.port, username, password)

    def query_state(self):
        state = self.interface.query_state()
        for key, item in state.items(): setattr(self, key, item)
    
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
                    ip=p["ip"],
                    port=p["port"],
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