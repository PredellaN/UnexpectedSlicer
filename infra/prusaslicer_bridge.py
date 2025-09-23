from subprocess import Popen
import os
import subprocess

def exec_prusaslicer(command: list[str], prusaslicer_path: str) -> Popen[str]:
    executable: list[str] = [f'{prusaslicer_path}'] if os.path.exists(prusaslicer_path) else [*prusaslicer_path.split()]
    cmd: list[str] = executable + command

    proc: Popen[str] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ)

    return proc