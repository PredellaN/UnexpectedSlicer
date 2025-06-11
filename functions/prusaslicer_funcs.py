from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

from subprocess import Popen

from .gcode_funcs import parse_gcode

import os
import tempfile
import subprocess

temp_dir = tempfile.gettempdir()

def exec_prusaslicer(command: list[str], prusaslicer_path: str) -> Popen[str]:

    executable: list[str] = [f'{prusaslicer_path}'] if os.path.exists(prusaslicer_path) else [*prusaslicer_path.split()]
    cmd: list[str] = executable + command

    proc: Popen[str] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ)

    return proc
    
def err_to_tempfile(text) -> str:
    print(text)
    temp_file_path = os.path.join(temp_dir, "prusa_slicer_err_output.txt")
    with open(temp_file_path, "w") as temp_file:
        temp_file.write(text)
    return temp_file_path

def filter_prusaslicer_dict_by_section(dict, section) -> dict[Any, Any]:
    return {k.split(":")[1]: v for k, v in dict.items() if k.split(":")[0] == section}

def get_print_stats(gcode: str | Path) -> tuple:
    if os.path.exists(gcode):
        print_time: str = parse_gcode(gcode, 'estimated printing time \\(normal mode\\)') or ''
        print_weight: str = parse_gcode(gcode, 'filament used \\[g\\]') or ''
        return print_time, print_weight
    return '', ''