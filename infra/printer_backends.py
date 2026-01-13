from __future__ import annotations
from functools import wraps
from typing import Any, Callable

def with_api_state(api_state: str) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Any:
        @wraps(func)
        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            self.api_state = api_state
            try: return func(self, *args, **kwargs)
            finally: self.api_state = None
        return wrapped
    return decorator

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Any, Optional
import requests
import time

@dataclass(frozen=True)
class PrinterStatus:
    progress: float = 0.0
    state: str = "OFFLINE"
    job_name: str = ""
    job_id: str = ""
    nozzle_temperature: float = 0.0
    bed_temperature: float = 0.0
    nozzle_diameter: float = 0.0

class PrinterBackend(Protocol):
    def query_status(self) -> PrinterStatus: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...
    def start_print(self, gcode: Path, name: str) -> None: ...

class HttpBackend:
    def __init__(self, host: str, port: int, prefix: str, api_key: Optional[str] = None, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.base = f"http://{host}:{port}{prefix}"
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {}
        self.api_state: str | None = None
        if api_key:
            self.headers["X-Api-Key"] = api_key

    def _get(self, path: str, **kw) -> requests.Response:
        headers = {**self.headers, **kw.pop('headers', {})}
        return self.session.get(self.base + path, headers=headers, timeout=self.timeout, **kw)

    def _post(self, path: str, **kw) -> requests.Response:
        headers = {**self.headers, **kw.pop('headers', {})}
        return self.session.post(self.base + path, headers=headers, timeout=self.timeout, **kw)

    def _put(self, path: str, **kw) -> requests.Response:
        headers = {**self.headers, **kw.pop('headers', {})}
        return self.session.put(self.base + path, headers=headers, timeout=self.timeout, **kw)

    def _delete(self, path: str, **kw) -> requests.Response:
        headers = {**self.headers, **kw.pop('headers', {})}
        return self.session.delete(self.base + path, headers=headers, timeout=self.timeout, **kw)

    def _json(self, resp, default: dict = {}, ok=(200, 201, 202, 204)) -> dict:
        if resp.status_code not in ok:
            resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return default
        return resp.json()

class PrinterHttpBackend(HttpBackend, PrinterBackend):
    pass

class PrusaLinkBackend(PrinterHttpBackend):
    def query_status(self) -> PrinterStatus:
        s = self._get("/api/v1/status").json()
        info = self._get("/api/v1/info").json()
        job = self._json(self._get("/api/v1/job"))
        return PrinterStatus(
            progress=float(job.get("progress", 0.0)),
            state=str(s.get("printer", {}).get("state", "OFFLINE")),
            job_name=str(job.get("file", {}).get("display_name", "")),
            job_id=str(s.get("job", {}).get("id", "")),
            nozzle_temperature=float(s.get("printer", {}).get("temp_nozzle", 0) or 0),
            bed_temperature=float(s.get("printer", {}).get("temp_bed", 0) or 0),
            nozzle_diameter=float(info.get('nozzle_diameter', 0.0)),
        )

    @with_api_state('PAUSING')
    def pause(self) -> None:
        jid = self.query_status().job_id
        if not jid: raise RuntimeError("No job to pause")
        self._put(f"/api/v1/job/{jid}/pause").raise_for_status()

    @with_api_state('RESUMING')
    def resume(self) -> None:
        jid = self.query_status().job_id
        if not jid: raise RuntimeError("No job to resume")
        self._put(f"/api/v1/job/{jid}/resume").raise_for_status()

    @with_api_state('STOPPING')
    def stop(self) -> None:
        jid = self.query_status().job_id
        if not jid: raise RuntimeError("No job to stop")
        self._delete(f"/api/v1/job/{jid}").raise_for_status()

    @with_api_state('STARTING')
    def start_print(self, gcode: Path, name: str) -> None:
        storage = self._get("/api/v1/storage").json()
        writables = [s for s in storage.get("storage_list", []) if s.get("available") and not s.get("read_only")]
        if not writables:
            print("No writable storage")
            raise RuntimeError("No writable storage")
        path = writables[0]["path"].lstrip("/")
        file_size = gcode.stat().st_size
        with open(gcode, "rb") as f:
            self._put(f"/api/v1/files/{path}/{name}",
                      headers={"Overwrite":"?1", 
                        "Content-Type": "text/x.gcode" if Path(name).suffix == '.gcode' else 'application/octet-stream',
                        "Content-Length": str(file_size),
                    }, data=f).raise_for_status()
        time.sleep(10)
        self._post(f"/api/v1/files/{path}/{name}").raise_for_status()

class CrealityBackend(PrinterHttpBackend):
    STATUS_EP = "/protocal.csp?fname=Info&opt=main&function=get"
    STORAGE_PATH = "/mmcblk0p1/creality/gztemp/"
    STORAGE_PATH_PRINT = "/media/mmcblk0p1/creality/gztemp/"

    def query_status(self) -> PrinterStatus:
        r = self._get(self.STATUS_EP)
        r.raise_for_status()
        d = r.json()

        # Map numeric state to string
        state_id = str(d.get("state", "-1"))
        state: str = (
            "OFFLINE" if state_id == "-1" else
            "PAUSED"  if state_id == "5"  else
            "IDLE"    if state_id in {"0", "3", "4"} else
            "PRINTING" if state_id == "1" else
            "FINISHED" if state_id == "2" else
            "UNKNOWN"
        )

        # Defensive casting
        def f(x, default=0.0):
            try:
                return float(x)
            except Exception:
                return default

        def s(x, default=""):
            return str(x) if x is not None else default

        return PrinterStatus(
            progress=round(f(d.get("printProgress"), 0.0), 1),
            state=state,
            job_name=s(d.get("print")),
            job_id="",  # Not exposed by this API
            nozzle_temperature=f(d.get("nozzleTemp"), 0.0),
            bed_temperature=f(d.get("bedTemp"), 0.0),
        )

    @with_api_state('PAUSING')
    def pause(self) -> None:
        r = self._get("/protocal.csp?fname=net&opt=iot_conf&function=set&pause=1")
        r.raise_for_status()

    @with_api_state('RESUMING')
    def resume(self) -> None:
        r = self._get("/protocal.csp?fname=net&opt=iot_conf&function=set&pause=0")
        r.raise_for_status()

    @with_api_state('STOPPING')
    def stop(self) -> None:
        r = self._get("/protocal.csp?fname=net&opt=iot_conf&function=set&stop=1")
        r.raise_for_status()

    @with_api_state('STARTING')
    def start_print(self, gcode: Path, name: str) -> None:
        from ..infra.ftp import ftp_upload, ftp_wipe  # adjust import to your layout

        # Clean target dir and upload
        ftp_wipe(self.host, self.STORAGE_PATH)
        ftp_upload(self.host, gcode, self.STORAGE_PATH, name, overwrite=True, timeout=self.timeout)
        
        time.sleep(10)

        # Trigger print
        ep = (
            "/protocal.csp?fname=net&opt=iot_conf&function=set"
            f"&print={self.STORAGE_PATH_PRINT}{name}"
        )
        r = self._get(ep)
        r.raise_for_status()

class MoonrakerBackend(PrinterHttpBackend):
    def query_status(self) -> PrinterStatus:
        url = f"{self.base}/printer/objects/query?webhooks&virtual_sdcard&print_stats"
        r = self.session.get(url, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        data = r.json().get("result", {}).get("status", {})

        sd = data.get("virtual_sdcard", {}) or {}
        ps = data.get("print_stats", {}) or {}

        state = str(ps.get("state", "OFFLINE")).upper()
        if state == "STANDBY":
            state = "IDLE"

        progress = 0.0
        try:
            progress = float(sd.get("progress", 0.0)) * 100.0
        except Exception:
            pass

        file_path = sd.get("file_path", "") or ""

        return PrinterStatus(
            progress=round(progress, 1),
            state=state,
            job_name=str(file_path),
            job_id="",
            nozzle_temperature=0.0,
            bed_temperature=0.0,
        )

    @with_api_state('PAUSING')
    def pause(self) -> None:
        url = f"{self.base}/printer/print/pause"
        r = self.session.post(url, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()

    @with_api_state('RESUMING')
    def resume(self) -> None:
        url = f"{self.base}/printer/print/resume"
        r = self.session.post(url, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()

    @with_api_state('STOPPING')
    def stop(self) -> None:
        url = f"{self.base}/printer/print/cancel"
        r = self.session.post(url, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()

    @with_api_state('STARTING')
    def start_print(self, gcode: Path, name: str) -> None:
        upload_url = f"{self.base}/server/files/upload"
        with open(gcode, "rb") as f:
            files = {
                "file": (name, f, "application/octet-stream")
            }
            form = {"print": "False"}  # You may set "True" to auto-start
            r = self.session.post(upload_url, headers=self.headers, files=files, data=form, timeout=self.timeout)
        r.raise_for_status()

        time.sleep(10)

        start_url = f"{self.base}/printer/print/start"
        payload = {"filename": name}
        r2 = self.session.post(start_url, headers=self.headers, json=payload, timeout=self.timeout)
        r2.raise_for_status()