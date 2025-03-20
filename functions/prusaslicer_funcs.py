from .gcode_funcs import parse_gcode
from .basic_functions import threaded_copy
from typing import Any

import time
import os
import tempfile
import subprocess

temp_dir = tempfile.gettempdir()

def run_slice(command: list, path_gcode: str, results_queue, prusaslicer_path: str):
    start_time = time.time()
    result_error = exec_prusaslicer(command, prusaslicer_path)

    print_time = ''
    print_weight = ''

    if result_error:
        path_gcode_temp = ''
        progress_pct = 0
        progress_text = f'Failed ({result_error})'
    else:
        path_gcode_temp = command[4]
        print_time, print_weight = get_stats(path_gcode_temp)
        progress_pct = 100
        elapsed = time.time() - start_time
        progress_text = f'Done (in {elapsed:.2f}s)'
        if path_gcode_temp != path_gcode:
            threaded_copy(path_gcode_temp, path_gcode)

    results_queue.put({
        "error": bool(result_error),
        "print_time": print_time,
        "print_weight": print_weight,
        "progress_pct": progress_pct,
        "progress_text": progress_text,
        "output_gcode_path": path_gcode_temp,
    })

def exec_prusaslicer(command: list[str], prusaslicer_path: str) -> str | None:

    executable: list[str] = [f'{prusaslicer_path}'] if os.path.exists(prusaslicer_path) else [*prusaslicer_path.split()]
    cmd: list[str]=executable + command 

    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ)

    except subprocess.CalledProcessError as e:
        if e.stderr:
            return f"Slicing failed, error output: {e.stderr}"
        return f"Slicing failed, return code {e.returncode}"

    if result.stdout:
        for line in result.stdout.splitlines():
            if "[error]" in line.lower():
                error_part = line.lower().split("[error]", 1)[1].strip()
                err_to_tempfile(result.stderr)
                return error_part

            if "slicing result exported" in line.lower():
                return

        tempfile = err_to_tempfile(" ".join(cmd) + "\n\n" + result.stderr + "\n\n" + result.stdout)
        return f"Slicing failed, error log at {tempfile}."
    
def err_to_tempfile(text) -> str:
    print(text)
    temp_file_path = os.path.join(temp_dir, "prusa_slicer_err_output.txt")
    with open(temp_file_path, "w") as temp_file:
        temp_file.write(text)
    return temp_file_path

def filter_prusaslicer_dict_by_section(dict, section) -> dict[Any, Any]:
    return {k.split(":")[1]: v for k, v in dict.items() if k.split(":")[0] == section}

def get_stats(gcode: str) -> tuple:
    if os.path.exists(gcode):
        print_time: str = parse_gcode(gcode, 'estimated printing time .+') or ''
        print_weight: str = parse_gcode(gcode, 'filament used \\[g\\]') or ''
        return print_time, print_weight
    return '', ''