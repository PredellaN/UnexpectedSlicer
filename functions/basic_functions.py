from functools import lru_cache

import json

import shutil
import multiprocessing
import platform
import csv
import os

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

def threaded_copy(from_file, to_file):
    process = multiprocessing.Process(target=shutil.copy, args=(from_file, to_file))
    process.start()

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