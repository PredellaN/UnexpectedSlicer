from subprocess import Popen
from numpy import ndarray
from bpy.types import Object

from typing import Any
from bpy.types import Collection

import bpy
import numpy as np
import os
import subprocess
import tempfile
import sys

from .preferences import SlicerPreferences

from .functions.prusaslicer_funcs import get_print_stats, exec_prusaslicer
from .functions.basic_functions import file_copy
from .functions.blender_funcs import ConfigLoader, get_inherited_overrides, get_inherited_slicing_props, names_array_from_objects, coll_from_selection, prepare_mesh_split, selected_object_family, selected_top_level_objects, show_progress
from .functions.gcode_funcs import get_bed_size
from .functions._3mf_funcs import prepare_3mf
from . import TYPES_NAME, PACKAGE


def unmount_usb(mountpoint: str) -> bool:
    try:
        if os.name == 'nt':
            # Windows: use mountvol to unmount
            result = os.system(f'mountvol {mountpoint} /D')
        else:
            # POSIX: use subprocess to run umount and capture output
            result = subprocess.run(['umount', mountpoint],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                error_message = result.stderr
                if 'target is busy' in error_message:
                    raise RuntimeError("Device busy")
                else:
                    raise RuntimeError(error_message)
        return True
    except Exception as e:
        print(f"Error unmounting {mountpoint}: {e}")
        return False


class UnmountUsbOperator(bpy.types.Operator):
    bl_idname = "collection.unmount_usb"
    bl_label = "Unmount USB"

    mountpoint: bpy.props.StringProperty()

    def execute(self, context) -> set[str]: #type: ignore
        if unmount_usb(self.mountpoint):
            self.report({'INFO'}, f"Successfully unmounted {self.mountpoint}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}")
            return {'CANCELLED'}


class RunSlicerOperator(bpy.types.Operator):
    bl_idname = "collection.slice"
    bl_label = "Run PrusaSlicer"

    mode: bpy.props.StringProperty(name="", default="slice")
    mountpoint: bpy.props.StringProperty(name="", default="")

    def execute(self, context) -> set[str]: #type: ignore
        cx: Collection | None = coll_from_selection()
        pg = getattr(cx, TYPES_NAME)
        pg.running = True
        show_progress(pg, 0, "Preparing Configuration...")

        # Get the PrusaSlicer path from preferences.
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
        prusaslicer_path = prefs.prusaslicer_path

        # Load configuration data.
        loader: ConfigLoader = ConfigLoader()
        cx_props: dict[str, [str, bool]] = get_inherited_slicing_props(cx, TYPES_NAME)

        sliceable: bool = cx_props['printer_config_file']['prop'] and cx_props['filament_config_file']['prop'] and cx_props['print_config_file']['prop']
        if sliceable: 
            try:
                headers: dict[str, Any] = prefs.profile_cache.config_headers
            
                for key, attr in cx_props.items():
                    loader.load_config(attr['prop'], headers)

                loader.config_dict.update({
                    'printer_settings_id': cx_props['printer_config_file']['prop'].split(":")[1],
                    'filament_settings_id': ";".join([p['prop'].split(":")[1] for k, p in cx_props.items() if k.startswith('filament')]),
                    'print_settings_id': cx_props['print_config_file']['prop'].split(":")[1],
                })

                overrides: dict[str, dict[str, Any]] = get_inherited_overrides(cx, TYPES_NAME)
                loader.load_list_to_overrides(overrides)
                loader.add_pauses_and_changes(pg.pause_list)

            except Exception as e:
                show_progress(pg, 0, 'Error: failed to load configuration')
                pg.running = False
                return {'FINISHED'}

        # Export 3MF.
        show_progress(pg, 10, "Exporting 3MF...")
        objects: list[Object] = selected_object_family()
        obj_metadatas: list[dict] = [{
            'name': obj.name,
            'object_type': getattr(obj, TYPES_NAME).object_type,
            'extruder': getattr(obj, TYPES_NAME).extruder,
            'modifiers': list(getattr(obj, TYPES_NAME).modifiers),
        } for obj in objects]
        if not obj_metadatas:
            show_progress(pg, 0, 'Error: selection empty')
            pg.running = False
            return {'FINISHED'}

        # Prepare mesh models.
        transform, models = prepare_mesh_split(context, objects)
        
        bed_size: tuple[int, int] = get_bed_size(loader.config_with_overrides.get('bed_shape', ''))
        bed_center: ndarray  = np.array([bed_size[0] / 2, bed_size[1] / 2, 0])
        centered_models: list[ndarray] = [model + bed_center for model in models]

        # Create a temporary 3MF file and prepare the checksum.
        temp_3mf_fd, path_3mf = tempfile.mkstemp(suffix=".3mf")
        os.close(temp_3mf_fd)  # Close the file descriptor.
        checksum = prepare_3mf(path_3mf, centered_models, loader, obj_metadatas)

        # Define paths for G-code.
        path_gcode, name_gcode, ext = determine_output_path(loader.config_with_overrides, [obj.name for obj in selected_top_level_objects()], self.mountpoint)
        path_gcode_temp = os.path.join(os.path.dirname(path_3mf), f'{checksum}.{ext}')
        path_gcode_out = os.path.join(path_gcode, f'{name_gcode}.{ext}')

        # If no slicing configuration exists or mode is "open", just open PrusaSlicer.
        if not loader.config_with_overrides or self.mode == "open":
            show_progress(pg, 100, 'Opening PrusaSlicer')

            new_path_3mf = os.path.join(os.path.dirname(path_3mf), f'{name_gcode}.3mf')
            if os.path.exists(new_path_3mf):
                os.remove(new_path_3mf)
            os.rename(path_3mf, new_path_3mf)

            exec_prusaslicer([new_path_3mf], prusaslicer_path)

            pg.running = False
            return {'FINISHED'}

        # If cached G-code exists, copy it and preview if needed.
        if os.path.exists(path_gcode_temp):
            post_slicing(pg, None, self.mode, prusaslicer_path, path_gcode_temp, path_gcode_out, {'transform': - bed_center - transform})
            return {'FINISHED'}

        # Otherwise, run slicing.
        if self.mode in ("slice", "slice_and_preview"):
            show_progress(pg, 30, 'Slicing with PrusaSlicer...')
            command = [path_3mf, "--dont-arrange", "-g", "--output", path_gcode_temp]

            proc: Popen[str] = exec_prusaslicer(command, prusaslicer_path)
            mode = self.mode
            bpy.app.timers.register(
                lambda: post_slicing(pg, proc, mode, prusaslicer_path, path_gcode_temp, path_gcode_out, {'transform': - bed_center - transform}),
                first_interval=0.5
            )

        return {'FINISHED'}

def process_handler(proc):
    if proc.poll() is None:
        return "", "", 0.5

    if sys.platform.startswith("linux"):
        import select
        reads, _, _ = select.select([proc.stdout], [], [], 0)

        if proc.stdout in reads:
            line = proc.stdout.readline()
            if line:
                print(line)
            if line != "":
                return "", "", 0.1
        else:
            return "", "", 0.1

    stdout, stderr = proc.communicate()

    return stdout, stderr, None

def post_slicing(pg, proc: Popen[str] | None, mode: str, prusaslicer_path: str, path_gcode_temp: str, path_gcode_out: str, preview_data: dict):
    stdout = stderr = ""

    if proc:
        stdout, stderr, timer = process_handler(proc)
        if timer: return timer

    if not os.path.exists(path_gcode_temp):
        pg.print_time = ""
        pg.print_weight = ""
        pg.print_debug = stderr
        pg.print_gcode = ""
        pg.print_center = [0,0,0]
        show_progress(pg, 0, "Slicing Failed")
        return None
        
    file_copy(path_gcode_temp, path_gcode_out)
    
    time, weight = get_print_stats(path_gcode_temp)

    pg.print_time = time
    pg.print_weight = weight
    pg.print_debug = ""
    pg.print_gcode = path_gcode_temp
    pg.print_center = preview_data['transform']
    show_progress(pg, 100, f"Slicing completed {'' if proc else '(copied from cache) '}to {path_gcode_out}")
    
    pg.running = False
    
    if mode == "slice_and_preview" and os.path.exists(path_gcode_temp):
        show_preview(path_gcode_temp, prusaslicer_path)
    
    return None # Stop the timer.

def safe_filename(base_filename: str, filament: str, printer: str) -> str:
    fixed_part = f"-{filament}-{printer}"
    allowed_base_length = 254 - len(fixed_part)
    truncated_base = base_filename[:allowed_base_length]
    full_filename = f"{truncated_base}{fixed_part}"
    return full_filename

def determine_output_path(config: dict[str, str], obj_names: list, mountpoint: str) -> tuple[str, str, str]:
    base_filename: str = "-".join(names_array_from_objects(obj_names))
    filament: str | list = config.get('filament_type', 'Unknown filament')
    if isinstance(filament, list):
        filament = ";".join(filament)
    printer: str = config.get('printer_model', 'Unknown printer')
    ext: str = "bgcode" if config.get('binary_gcode', '0') == '1' else "gcode"
    full_filename: str = safe_filename(base_filename, filament, printer)
    gcode_filename: str = f"{full_filename}"
    blendfile_directory: str = os.path.dirname(bpy.data.filepath)
    gcode_dir: str = mountpoint if mountpoint else (blendfile_directory if blendfile_directory else '/tmp/')
    return gcode_dir, gcode_filename, ext

def show_preview(gcode: str, prusaslicer_path: str):
    if gcode and os.path.exists(gcode):
        exec_prusaslicer(["--gcodeviewer", gcode], prusaslicer_path)
    else:
        print("Gcode file not found: skipping preview.")