# printer_control.py
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Callable, Any

from ..infra.printer_backends import CrealityBackend, MoonrakerBackend, PrinterHttpBackend, PrinterStatus, PrusaLinkBackend  # import your backends

@dataclass
class ManagedPrinter:
    name: str
    backend: PrinterHttpBackend
    status: PrinterStatus = field(default_factory=PrinterStatus)
    last_error: str | None = None
    last_command_time: datetime | None = None
    last_command_response: str = ""

class PrinterController:
    def __init__(self, poll_interval: float = 2.0, max_workers: int = 8) -> None:
        self._poll_interval = poll_interval
        self._exec = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = Lock()
        self._printers: dict[str, ManagedPrinter] = {}
        self._last_poll: float = 0.0

    @property
    def printers(self) -> dict[str, ManagedPrinter]:
        return self._printers 

    def set_printers(self, printers: list[dict[str, Any]]) -> None:
        self._printers = {}
        for printer in printers:
            backend_class: type | None = None
            if printer['host_type'] == 'prusalink': backend_class = PrusaLinkBackend
            elif printer['host_type'] == 'creality': backend_class = CrealityBackend
            elif printer['host_type'] == 'moonraker': backend_class = MoonrakerBackend
            assert backend_class

            self.add_printer(ManagedPrinter(
                name= printer['name'],
                backend= backend_class(
                    host=printer['ip'],
                    port=int(printer['port']),
                    prefix=printer['prefix'],
                    api_key=printer['password'],
                )
            ))

    def add_printer(self, printer: ManagedPrinter) -> None:
        with self._lock:
            self._printers[printer.name] = printer

    def remove_printer(self, name: str) -> None:
        with self._lock:
            self._printers.pop(name, None)

    def list(self) -> dict[str, ManagedPrinter]:
        with self._lock:
            return dict(self._printers)
            
    def poll(self) -> None:
        now = monotonic()
        with self._lock:
            if now - self._last_poll < self._poll_interval:
                return
            self._last_poll = now
            keys = list(self._printers.keys())

        for k in keys:
            self._exec.submit(self._poll_one, k)

    def _poll_one(self, name: str) -> None:
        with self._lock:
            mp = self._printers.get(name)
            if not mp:
                return
            backend = mp.backend

        try:
            status = backend.query_status()
            with self._lock:
                mp = self._printers.get(name)
                if mp:
                    mp.status = status
                    mp.last_error = None
        except Exception as e:
            with self._lock:
                mp = self._printers.get(name)
                if mp:
                    mp.last_error = str(e)

    def run_command(self, name: str, fn: Callable[[PrinterHttpBackend], None]) -> Future[None]:
        mp = self.list().get(name)
        if not mp:
            raise KeyError(f"Unknown printer {name}")


        # We create a wrapper to update command time/response
        def _wrapped(backend: PrinterHttpBackend) -> None:
            try:
                fn(backend)
                mp.last_command_time = datetime.now(timezone.utc)
                mp.last_command_response = "ok"
            except Exception as e:
                mp.last_command_time = datetime.now(timezone.utc)
                mp.last_command_response = str(e)
                raise  # bubble to the Future
        return self._exec.submit(_wrapped, mp.backend)

    @staticmethod
    def _run_cmd(mp: ManagedPrinter, fn: Callable[[PrinterHttpBackend], None]) -> None:
        fn(mp.backend)

    def shutdown(self) -> None:
        self._exec.shutdown(wait=False)
