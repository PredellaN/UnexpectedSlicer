
import os
import tempfile
import subprocess

temp_dir = tempfile.gettempdir()

def exec_prusaslicer(command, prusaslicer_path):

    if os.path.exists(prusaslicer_path):
        command=[f'{prusaslicer_path}'] + command
    else:
        command=[*prusaslicer_path.split() + command]

    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ)

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

        tempfile = err_to_tempfile(" ".join(command) + "\n\n" + result.stderr + "\n\n" + result.stdout)
        return f"Slicing failed, error log at {tempfile}."
    
def err_to_tempfile(text):
    print(text)
    temp_file_path = os.path.join(temp_dir, "prusa_slicer_err_output.txt")
    with open(temp_file_path, "w") as temp_file:
        temp_file.write(text)
    return temp_file_path

def filter_prusaslicer_dict_by_section(dict, section):
    return {k.split(":")[1]: v for k, v in dict.items() if k.split(":")[0] == section}