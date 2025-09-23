from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import time, threading

from ..infra.printer_backends import APIInterface, PrinterQueryResponse
from ..infra.printer_backends import Prusalink, Creality, Moonraker

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
        timeout: float = 60.0,
        executor: ThreadPoolExecutor | None = None,
        lock: threading.Lock | None = None
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
        else: self.interface = APIInterface(host, self.port, prefix, username, password, timeout=timeout, executor=executor, lock=lock)

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
        timeout: float = 60.0,
        executor: ThreadPoolExecutor | None = None,
        lock: threading.Lock | None = None
    ) -> None:
        self._timeout: float = timeout
        self._executor: ThreadPoolExecutor = executor or ThreadPoolExecutor()
        self._lock: threading.Lock = lock or threading.Lock()
        self._printers: dict[str, Printer] = {}
        self._last_exec: float = 0.0

    def set_printers(self, printers_list: list[dict[str, str]]) -> None:
        print('Setting printers')
        with self._lock:
            self._printers = {
                p["name"]: Printer(
                    name=p["name"],
                    host_type=p["host_type"],
                    host=p["ip"],
                    port=p["port"],
                    prefix=p["prefix"],
                    username=p["username"],
                    password=p["password"],
                    timeout=self._timeout,
                    executor=self._executor,
                    lock=self._lock
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
        with self._lock:
            if now - self._last_exec < self._timeout:
                return
            self._last_exec = now
            items: list[tuple[str, Printer]] = list(self._printers.items())

        for _, printer in items:
            self._executor.submit(self._safe_query, printer)