from pathlib import Path
import shutil
import platform

def is_usb_device(partition):
    if platform.system() == "Windows":
        return 'removable' in partition.opts.lower()
    else:
        return 'usb' in partition.opts or "/media" in partition.mountpoint

def file_copy(from_file, to_file):
    shutil.copy(from_file, to_file)

def calculate_md5(file_paths) -> str:
    import hashlib
    from _hashlib import HASH

    md5_hash: HASH = hashlib.md5()
    for file_path in file_paths:
        with open(file=file_path, mode="rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
    return md5_hash.hexdigest()

import mmap
def count_lines_mmap(path: str | Path, filter=b'\n'):
    with open(path, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        n = mm[:].count(filter)
        mm.close()
    return n

def err_to_tempfile(text) -> str:
    import os, tempfile
    print(text)
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, "errlog.txt")
    with open(temp_file_path, "w") as temp_file:
        temp_file.write(text)
    return temp_file_path