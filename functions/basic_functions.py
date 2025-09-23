from functools import lru_cache

import json

from pathlib import Path
import shutil
import platform
import csv
import os
import cProfile
import pstats
import io

@lru_cache(maxsize=128)
def _load_csv(filename: str, mtime: float, encoding: str | None = None) -> tuple[tuple[str, ...], ...]:
    with open(filename, 'r', newline='', encoding=encoding) as f:
        reader = csv.reader(f)
        return tuple(tuple(row) for row in reader)

def parse_csv_to_tuples(filename: str) -> list[tuple[str, ...]]:
    current_mtime = os.path.getmtime(filename)
    data: tuple[tuple[str, ...], ...] = _load_csv(filename, current_mtime)
    return sorted(data, key=lambda x: x[1])

def parse_csv_to_dict(filename: str) -> dict[str, list[str]]:
    current_mtime = os.path.getmtime(filename)
    data: tuple[tuple[str, ...], ...] = _load_csv(filename, current_mtime, encoding='utf-8-sig')
    result = {}
    for row in data:
        if row:
            result[row[0]] = list(row[1:])
    return result

def is_usb_device(partition):
    if platform.system() == "Windows":
        return 'removable' in partition.opts.lower()
    else:
        return 'usb' in partition.opts or "/media" in partition.mountpoint

def file_copy(from_file, to_file):
    shutil.copy(from_file, to_file)

def reset_selection(object, field):
    if getattr(object, field) > -1:
        setattr(object, field, -1)

def dict_from_json(path):
    with open(path, 'r') as file:
        return json.load(file)

def dump_dict_to_json(dictionary, path):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    
    with open(path, 'w') as file:
        json.dump(dictionary, file, indent=2)

import cProfile
import pstats
import io
import functools
import atexit

def profiler(func):
    profiler_inst = cProfile.Profile()
    calls: int = 0

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal calls
        profiler_inst.enable()
        result = func(*args, **kwargs)
        profiler_inst.disable()
        calls += 1 # type: ignore

        # Print stats for this call
        buf = io.StringIO()
        pstats.Stats(profiler_inst, stream=buf).sort_stats('cumulative').print_stats()
        print(f"[Profiler] Call {calls} stats:\n{buf.getvalue()}")
        return result

    return wrapper

import sys
import time
import functools
import linecache
import os
from collections import defaultdict

import functools
import sys
import time
import os
import linecache
from collections import defaultdict

def line_by_line_profiler(func):
    """
    Decorator that times each line inside func, then prints a report
    including total time spent executing profiled lines.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Map (filename, lineno) -> [total_time, hit_count]
        stats = defaultdict(lambda: [0.0, 0])
        last = {"t": None, "key": None}

        def tracer(frame, event, arg):
            if event != "line":
                return tracer
            co = frame.f_code
            # Only trace lines in our target function's code object
            if co is not func.__code__:
                return tracer

            now = time.perf_counter()
            lineno = frame.f_lineno
            filename = co.co_filename
            key = (filename, lineno)

            if last["t"] is not None and last["key"] is not None:
                elapsed = now - last["t"]
                stats[last["key"]][0] += elapsed
                stats[last["key"]][1] += 1

            last["t"] = now  # type: ignore
            last["key"] = key  # type: ignore
            return tracer

        # Install tracer, call function, then disable tracer
        sys.settrace(tracer)
        try:
            result = func(*args, **kwargs)
        finally:
            sys.settrace(None)

            # Print report sorted by total time descending
            print(f"\n[LineProfiler] Profiling results for {func.__name__}")
            header = f"{'File':<12} {'Line':>5} {'Hits':>8} {'Total(s)':>12} {'Per Hit(s)':>12} Code"
            print(header)
            print("-" * len(header))

            total_profiled = 0.0
            for (fname, lineno), (tot, cnt) in sorted(stats.items(), key=lambda kv: kv[1][0], reverse=True):
                file_only = os.path.basename(fname)
                source = linecache.getline(fname, lineno).rstrip()
                per = tot / cnt if cnt else 0
                total_profiled += tot
                print(f"{file_only:<12} {lineno:5d} {cnt:8d} {tot:12.6f} {per:12.6f} {source}")

            # Print total time spent in profiled lines
            print(f"\n[LineProfiler] Total profiled time: {total_profiled:.6f} seconds")

        return result

    return wrapper

def ftp_upload(
    host: str,
    filepath: Path,
    storage_path: str,
    filename: str,
    overwrite: bool = False,
    timeout: float = 30,
    user: str = "",
    passwd: str = "",
):
    from ftplib import FTP, error_perm

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Local file not found: {filepath}")

    remote_name = filename or os.path.basename(filepath)

    ftp = FTP(host, timeout=timeout)
    ftp.login(user=user, passwd=passwd)

    try:
        # Change to target directory
        ftp.cwd(storage_path)

        # Check if file exists remotely
        existing = ftp.nlst()
        if remote_name in existing:
            if not overwrite:
                raise FileExistsError(f"Remote file already exists: {remote_name}")
            # delete existing file
            try:
                ftp.delete(str(remote_name))
            except error_perm as e:
                raise RuntimeError(f"Failed to delete remote file: {e}")

        # Upload new file
        with open(filepath, 'rb') as f:
            ftp.storbinary(f'STOR {remote_name}', f)

    finally:
        ftp.quit()

def ftp_wipe(
    host: str,
    storage_path: str,
    timeout: int = 30,
    user: str = "",
    passwd: str = "",
):
    from ftplib import FTP, error_perm

    ftp = FTP(host, timeout=timeout)
    ftp.login(user=user, passwd=passwd)

    try:
        ftp.cwd(storage_path)
        existing = ftp.nlst()
        for f in existing:
            try:
                ftp.delete(filename=f)
            except error_perm as e:
                raise RuntimeError(f"Failed to delete remote file: {f}")
    except error_perm as e:
        raise RuntimeError("e")
    finally:
        ftp.quit()