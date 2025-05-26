from typing import Any

import requests
from requests import Response
import base64
import os

method_map = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "DELETE": requests.delete,
}

def send_request(printer, endpoint, method, headers = {}, filepath = None) -> Response | None:

    url = f"http://{printer['ip']}:{printer['port']}{endpoint}"

    if printer['host_type'] == 'prusalink':
        headers['X-Api-Key'] = printer['password']
    else:
        if printer['password']:
            creds = f"{printer['username']}:{printer['password']}".encode("utf-8")
            b64creds = base64.b64encode(creds).decode("ascii")
            headers['Authorization'] = f"Basic {b64creds}"

    try:
        response: Response = method_map[method](url, headers=headers, data=open(filepath, 'rb') if filepath else None)
        response.raise_for_status()
        print(f"Successfully requested on {printer['ip']}")
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error requesting on {printer['ip']}: {e}")
        return None

def pause_print(printer) -> Response | None:
    if printer['host_type'] == 'prusalink':
        job_id = printer['job_id']
        if not job_id:
            return
        return send_request(printer, f'/api/v1/job/{job_id}/pause', 'PUT')
    elif printer['host_type'] == 'creality':
        return send_request(printer, '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=1', 'GET')

def resume_print(printer) -> Response | None:
    if printer['host_type'] == 'prusalink':
        job_id = printer['job_id']
        if not job_id:
            return
        return send_request(printer, f'/api/v1/job/{job_id}/resume', 'PUT')
    elif printer['host_type'] == 'creality':
        return send_request(printer, '/protocal.csp?fname=net&opt=iot_conf&function=set&pause=0', 'GET')

def stop_print(printer) -> Response | None:
    if printer['host_type'] == 'prusalink':
        job_id = printer['job_id']
        if not job_id:
            return
        return send_request(printer, f'/api/v1/job/{job_id}', 'DELETE')
    elif printer['host_type'] == 'creality':
        return send_request(printer, '/protocal.csp?fname=net&opt=iot_conf&function=set&stop=1', 'GET')


def get_storage_path(printer) -> Any | None:
    if printer['host_type'] == 'prusalink':
        resp: Response | None = send_request(printer, f'/api/v1/storage', 'GET')
        if not resp: return None 
        storage_list = resp.json().get("storage_list", [])
        writable = [s for s in storage_list if s.get("available") and not s.get("read_only")]
        if not writable: return None
        return writable[0]["path"].lstrip("/")

    elif printer['host_type'] == 'creality':
        return f'/mmcblk0p1/creality/gztemp/'

def upload_file(printer, gcode_filepath, storage_path, filename):
    if printer['host_type'] == 'prusalink':
        headers = {
            "Overwrite": "?1",
            "Print-After-Upload": "?1",
        }
        send_request(printer, f'/api/v1/files/{storage_path}{filename}', 'PUT', headers, gcode_filepath)
        return 

    elif printer['host_type'] == 'creality':
        from ftplib import FTP

        host = printer['ip']
        if not os.path.isfile(gcode_filepath):
            raise FileNotFoundError(f"Local file not found: {gcode_filepath}")

        ftp = FTP(host, timeout=30)
        ftp.login()
        try:
            ftp.cwd(storage_path)
            with open(gcode_filepath, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
        finally:
            ftp.quit()

def start_file(printer, storage_path, filename):
    if printer['host_type'] == 'prusalink':
        send_request(printer, f"/api/v1/files/{storage_path}{filename}", "POST")

    elif printer['host_type'] == 'creality':
        endpoint = f'/protocal.csp?fname=net&opt=iot_conf&function=set&print=/media/mmcblk0p1/creality/gztemp//{filename}'
        send_request(printer, endpoint, "GET")

def start_print(printer, gcode_filepath: str) -> None:
    storage_path = get_storage_path(printer)

    filename = os.path.basename(gcode_filepath)
    upload_file(printer, gcode_filepath, storage_path, filename)
    start_file(printer, storage_path, filename)
    
    print(f"Print job started: {filename} on storage '{storage_path}'")