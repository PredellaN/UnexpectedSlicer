from typing import Any

import requests
from requests import Response
from requests.auth import HTTPDigestAuth

method_map = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "DELETE": requests.delete,
}

def send_request(printer, endpoint, method, headers = None, data = None) -> Response | None:
    if printer['host_type'] != 'prusalink':
        return
    
    url = f"http://{printer['ip']}:{printer['port']}{endpoint}"
    try:
        response: Response = method_map[method](url, auth=HTTPDigestAuth(printer['username'], printer['password']), headers=headers, data=data)
        response.raise_for_status()
        print(f"Successfully requested on {printer['ip']}")
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error requesting on {printer['ip']}: {e}")
        return None

def pause_print(printer) -> Response | None:
    job_id = printer['job_id']
    if not job_id:
        return
    return send_request(printer, f'/api/v1/job/{job_id}/pause', 'PUT')

def resume_print(printer) -> Response | None:
    job_id = printer['job_id']
    if not job_id:
        return
    return send_request(printer, f'/api/v1/job/{job_id}/resume', 'PUT')

def stop_print(printer) -> Response | None:
    job_id = printer['job_id']
    if not job_id:
        return
    return send_request(printer, f'/api/v1/job/{job_id}', 'DELETE')

def get_storage_path(printer) -> Any | None:
    resp: Response | None = send_request(printer, f'/api/v1/storage', 'GET')
    if not resp: return None 
    storage_list = resp.json().get("storage_list", [])
    writable = [s for s in storage_list if s.get("available") and not s.get("read_only")]
    if not writable: return None
    return writable[0]["path"].lstrip("/")

def upload_file(printer, gcode_filepath, storage_path, filename):
    with open(gcode_filepath, "rb") as f:
        data = f.read()

    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(data)),
        "Overwrite": "?1"
    }
    return send_request(printer, f'/api/v1/files/{storage_path}/{filename}', 'PUT', headers, data)

def start_file(printer, storage_path, filename):
    return send_request(printer, f"/api/v1/files/{storage_path}/{filename}", "POST")

def start_print(printer, gcode_filepath: str) -> None:
    storage_path = get_storage_path(printer)

    import os
    filename = os.path.basename(gcode_filepath)
    resp = upload_file(printer, gcode_filepath, storage_path, filename)

    if resp.status_code not in (200, 201, 204):
        resp.raise_for_status()

    start_file(printer, storage_path, filename)
    
    if resp.status_code != 204:
        resp.raise_for_status()

    print(f"Print job started: {filename} on storage '{storage_path}'")