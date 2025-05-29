import requests
import bpy
import os
import time
from functools import wraps

from typing import Any
from requests import Response

import threading
from concurrent.futures import ThreadPoolExecutor
max_conn = getattr(bpy.context.preferences.system, 'network_connection_limit', 1)
_executor = ThreadPoolExecutor(max_workers=max_conn)
_lock = threading.Lock()

# Utility to safely traverse nested dicts
def get_nested(data, default: Any, typ: type, *keys: str) -> Any:
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k)
        if data is None:
            return default
    return typ(data)

# State wrapper
def with_api_state(state):
    def decorator(func):
        @wraps(func)
        def wrapped(self, *args, **kwargs):
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

    def __init__(self, ip, port, username, password):
        self.ip = ip
        self.port = port
        self.username = username
        self.authentication_header(username, password)

    def authentication_header(self, username, password):
        pass

    def get_api_responses(self) -> dict[str, dict]:
        def fetch(endpoint: str) -> tuple[str, dict]:
            if not bpy.app.online_access: return endpoint, {"error": "Online access is not allowed!"}
            
            host, rest = (self.ip.split('/', 1) + [''])[:2]
            url = f"http://{host}:{self.port}{('/' + rest) if rest else ''}{endpoint}"
            try:
                resp = requests.get(
                    url,
                    headers=self.auth_header,
                    timeout=bpy.context.preferences.system.network_timeout
                )
                resp.raise_for_status()
                return endpoint, resp.json()
            except Exception as e:
                return endpoint, {"error": str(e)}

        responses: dict[str, dict] = {}

        for ep in self.endpoints:
            responses[ep] = fetch(ep)[1]

        return responses

    def query_state(self) -> dict[str, Any]:
        return {
            'progress': 0,
            'state': 'OFFLINE',
            'job_name': None,
            'job_id': None,
        }

    def get_storage_path(self) -> str | None: raise NotImplementedError("get_storage_path not implemented for this backend")
    def pause_print(self) -> Response | None: raise NotImplementedError("pause_print not implemented for this backend")
    def resume_print(self) -> Response | None: raise NotImplementedError("resume_print not implemented for this backend")
    def stop_print(self) -> Response | None: raise NotImplementedError("stop_print not implemented for this backend")
    def upload_file(self, storage_path, filepath, filename) -> Response | None: raise NotImplementedError("upload_file not implemented for this backend")
    def start_file(self, storage_path, filename) -> Response | None: raise NotImplementedError("start_file not implemented for this backend")

    def start_print(self, gcode_filepath: str) -> None:
        storage_path = self.get_storage_path()
        if not storage_path:
            print("Error: Could not determine storage path.")
            return
        filename = os.path.basename(gcode_filepath)
        self.upload_file(storage_path, gcode_filepath, filename)
        self.start_file(storage_path, filename)
        print(f"Print job started: {filename} on storage '{storage_path}'")

    def send_request(self, endpoint: str, method: str, headers: dict[str, str] = {}, filepath: str | None = None) -> Response | None:
        host, rest = (self.ip.split('/', 1) + [''])[:2]
        url = f"http://{host}:{self.port}{('/' + rest) if rest else ''}{endpoint}"
        try:
            response: Response = method_map[method](
                url,
                headers={**headers, **self.auth_header},
                data=open(filepath, 'rb') if filepath else None
            )
            response.raise_for_status()
            print(f"Successfully requested {method} {url}")
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error requesting {url}: {e}")
            return None

class Prusalink(APIInterface):
    endpoints: list[str] = [
        '/api/v1/status',
        '/api/v1/info',
        '/api/v1/job'
    ]

    def authentication_header(self, username, password):
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
    def get_storage_path(self) -> str | None:
        resp = self.send_request( '/api/v1/storage', 'GET')
        if not resp:
            return None
        storage_list = resp.json().get('storage_list', [])
        writable = [s for s in storage_list if s.get('available') and not s.get('read_only')]
        if not writable:
            return None
        return writable[0]['path'].lstrip('/')

    @with_api_state('PAUSING')
    def pause_print(self, job_id = None) -> Response | None:
        if not (job_id := self.query_state()['job_id']):
            print("No job ID available to pause.")
            return None
        return self.send_request( f'/api/v1/job/{job_id}/pause', 'PUT')

    @with_api_state('RESUMING')
    def resume_print(self, job_id = None) -> Response | None:
        if not (job_id := self.query_state()['job_id']):
            print("No job ID available to resume.")
            return None
        return self.send_request( f'/api/v1/job/{job_id}/resume', 'PUT')

    @with_api_state('STOPPING')
    def stop_print(self, job_id = None) -> Response | None:
        if not (job_id := self.query_state()['job_id']):
            print("No job ID available to stop.")
            return None
        return self.send_request( f'/api/v1/job/{job_id}', 'DELETE')

    @with_api_state('UPLOADING')
    def upload_file(self, storage_path, filepath, filename) -> Response | None:
        headers = {
            'Overwrite': '?1',
            'Print-After-Upload': '?1',
        }
        self.send_request( f'/api/v1/files/{storage_path}{filename}', 'PUT', headers, filepath)

    @with_api_state('STARTING')
    def start_file(self, storage_path, filename) -> Response | None:
        return self.send_request( f"/api/v1/files/{storage_path}{filename}", 'POST')

class Creality(APIInterface):
    endpoints: list[str] = [
        '/protocal.csp?fname=Info&opt=main&function=get'
    ]

    def query_state(self) -> dict[str, Any]:
        api_data  = self.get_api_responses()
        progress = round(get_nested(api_data, 0.0, float, self.endpoints[0], 'printProgress'), 1)
        paused = get_nested(api_data, '0', str, self.endpoints[0], 'pause')
        state_id = get_nested(api_data, '-1', str, self.endpoints[0], 'state')
        state = (
            'OFFLINE' if state_id == '-1' else
            'PAUSED' if state_id == '5' else
            'IDLE' if state_id in ['0', '4'] else
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

    def get_storage_path(self) -> str | None:
        return '/mmcblk0p1/creality/gztemp/'

    @with_api_state('PAUSING')
    def pause_print(self) -> Response | None:
        return self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=1',
            'GET'
        )

    @with_api_state('RESUMING')
    def resume_print(self) -> Response | None:
        return self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=0',
            'GET'
        )

    @with_api_state('STOPPING')
    def stop_print(self) -> Response | None:
        return self.send_request(
            '/protocal.csp?fname=net&opt=iot_conf&function=set&stop=1',
            'GET'
        )

    @with_api_state('UPLOADING')
    def upload_file(self, storage_path, filepath, filename) -> Response | None:
        from ..functions.basic_functions import ftp_upload
        ftp_upload(self.ip, filepath, storage_path, filename, overwrite=True, timeout=bpy.context.preferences.system.network_timeout)

    @with_api_state('STARTING')
    def start_file(self, storage_path, filename) -> Response | None:
        endpoint = (
            f"/protocal.csp?fname=net&opt=iot_conf&"
            f"function=set&print=/media/mmcblk0p1/creality/gztemp//{filename}"
        )
        self.send_request( endpoint, 'GET')

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
            'job_name': None,
            'job_id': None,
        }

    def pause_print(self) -> Response | None: raise NotImplementedError("pause_print not implemented for Moonraker")
    def resume_print(self) -> Response | None: raise NotImplementedError("resume_print not implemented for Moonraker")
    def stop_print(self) -> Response | None: raise NotImplementedError("stop_print not implemented for Moonraker")

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
        port: int,
        username: str,
        password: str,
    ) -> None:
    
        self.name = name
        self.host_type = host_type
        self.ip = ip
        self.port = port
        self.username = username

        if host_type == 'prusalink': self.interface = Prusalink(ip, port, username, password)
        elif host_type == 'creality': self.interface = Creality(ip, port, username, password)
        elif host_type == 'moonraker': self.interface = Moonraker(ip, port, username, password)
        else: self.interface = APIInterface(ip, port, username, password)

    def query_state(self):
        state = self.interface.query_state()
        for key, item in state.items(): setattr(self, key, item)
    
    def pause_print(self):
        self.interface.pause_print()

    def resume_print(self):
        self.interface.resume_print()

    def stop_print(self):
        self.interface.stop_print()

    def start_print(self, gcode_filepath):
        self.interface.start_print(gcode_filepath)

class PrinterQuerier:
    def __init__(
        self,
        min_interval: float = 60.0,
    ) -> None:
        self._printers: dict[str, Printer] = {}
        self._min_interval: float = min_interval
        self._last_exec: float = 0.0

    def set_printers(self, printers_list: list[dict]) -> None:
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
            print(f"Error updating printer '{printer.name}': {e}")

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
def querier_timer():
    try: printers_querier.query()
    except: pass
    redraw()
    return 1