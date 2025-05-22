import requests
from requests.auth import HTTPDigestAuth

method_map = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "DELETE": requests.delete,
    # Add other methods as needed
}

def send_request(printer, endpoint, method):
    if printer['host_type'] != 'prusalink':
        return
    
    url = f"http://{printer['ip']}:{printer['port']}{endpoint}"
    try:
        response = method_map[method](url, auth=HTTPDigestAuth(printer['username'], printer['password']))
        response.raise_for_status()
        print(f"Successfully requested on {printer['ip']}")
    except requests.exceptions.RequestException as e:
        print(f"Error requesting on {printer['ip']}: {e}")

def pause_print(printer):
    job_id = printer['job_id']
    if not job_id:
        return
    send_request(printer, f'/api/v1/job/{job_id}/pause', 'PUT')

def resume_print(printer):
    job_id = printer['job_id']
    if not job_id:
        return
    send_request(printer, f'/api/v1/job/{job_id}/resume', 'PUT')

def stop_print(printer):
    job_id = printer['job_id']
    if not job_id:
        return
    send_request(printer, f'/api/v1/job/{job_id}', 'DELETE')