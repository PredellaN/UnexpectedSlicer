from typing import Any

from typing import Any
import requests
from requests.auth import HTTPDigestAuth

from .host_confs import host_configs

def get_api_responses(
    printer_ip: str,
    printer_port: int,
    endpoints: list[str],
    username: str,
    password: str,
    tunnel = None
) -> dict[str, dict]:

    responses: dict[str, dict] = {}
    if tunnel:
        local_host, local_port = tunnel.tunnel_bindings[(printer_ip, printer_port)]
        host, port = local_host, local_port
    else:
        host, port = printer_ip, printer_port

    for endpoint in endpoints:
        url = f"http://{host}:{port}{endpoint}"
        try:
            resp = requests.get(
                url,
                auth=HTTPDigestAuth(username, password),
                timeout=5.0
            )
            resp.raise_for_status()
            responses[endpoint] = resp.json()
        except Exception as e:
            # Record the error rather than aborting the whole batch
            responses[endpoint] = {"error": str(e)}

    return responses

def get_nested(data: dict[str, dict] | None, path: list[str], default=None) -> Any | dict[str, dict[Any, Any]] | None:
    for key in path:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
        if data is None:
            return default
    return data

def process_printer(printer: dict[str, str], tunnel = None) -> dict[str, Any]:
    ip = printer['ip']
    port = printer['port']
    username = printer['username']
    password = printer['password']
    host_type = printer["host_type"]

    # Base response template
    response: dict[str, str | dict] = {
        'name': printer['name'],
        'ip': ip,
        'state': '',
        'progress': '',
        'job_name': '',
        'job_id': '',
        'commands': {},
    }

    # Get configuration for the host type
    conf: dict[str, [list[str], list[str], dict, dict]] | None = host_configs.get(host_type)
    if conf is None:
        print(f"Unknown printer host type for printer with IP: {ip}")
        return response

    # Get data from all endpoints defined for this host type
    endpoints: list[str] = conf["endpoints"]
    data: dict[str, dict] = get_api_responses(
        printer_ip=ip,
        printer_port=int(port),
        endpoints=endpoints,
        username=username,
        password=password,
        tunnel=tunnel,
    )

    # Check if the required endpoints returned data
    if any(data[ep].get('error') for ep in conf.get("required", [])):
        response['state'] = 'OFFLINE'
        response['progress'] = ''
        return response

    # Extract fields based on the configuration
    for field, params in conf["fields"].items():
        endpoint: str = params["endpoint"]
        field_data: dict[str, dict] = data.get(endpoint, {})

        value: dict[str, dict] | None = get_nested(field_data, params["path"], params.get("default"))
        if "transform" in params and value is not None:
            value = params["transform"](value)
        response[field] = str(value)

    commands: dict[str, dict[str, str]] = conf.get("commands")
    if not commands or not response.get("job_id"):
        response["commands"] = {}
    else:
        response["commands"] = {
            name: cmd["endpoint"].format(ip=response["ip"], job_id=response["job_id"])
            for name, cmd in commands.items()
        }

    return response