from requests.auth import HTTPDigestAuth

def send_request(printer, endpoint):
    if printer['host_type'] != 'prusalink':
        return
    
    url = f"http://{printer['ip']}:{printer['port']}{endpoint}"
    import requests
    try:
        response = requests.put(url, auth=HTTPDigestAuth(printer['username'], printer['password']))
        response.raise_for_status()
        print(f"Successfully requested on {printer['ip']}")
    except requests.exceptions.RequestException as e:
        print(f"Error requesting on {printer['ip']}: {e}")

def pause_print(printer):
    job_id = printer['job_id']
    if not job_id:
        return
    send_request(printer, f'/api/v1/job/{job_id}/pause')

def resume_print(printer):
    job_id = printer['job_id']
    if not job_id:
        return
    send_request(printer, f'/api/v1/job/{job_id}/resume')