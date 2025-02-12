import bpy
import numpy as np
import os
import subprocess
import time
import multiprocessing
import tempfile

from .functions import prusaslicer_funcs as psf
from .functions.basic_functions import show_progress, threaded_copy, redraw
from .functions import blender_funcs as bf
from .functions.gcode_funcs import get_bed_size, parse_gcode
from .functions._3mf_funcs import prepare_3mf
from . import TYPES_NAME


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
    bl_idname = "export.unmount_usb"
    bl_label = "Unmount USB"

    mountpoint: bpy.props.StringProperty()

    def execute(self, context):
        if unmount_usb(self.mountpoint):
            self.report({'INFO'}, f"Successfully unmounted {self.mountpoint}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}")
            return {'CANCELLED'}


class RunPrusaSlicerOperator(bpy.types.Operator):
    bl_idname = "export.slice"
    bl_label = "Run PrusaSlicer"

    mode: bpy.props.StringProperty(name="", default="slice")
    mountpoint: bpy.props.StringProperty(name="", default="")

    def execute(self, context):
        cx = bf.coll_from_selection()
        pg = getattr(cx, TYPES_NAME)
        pg.running = True
        show_progress(pg, 0, "Preparing Configuration...")

        # Get the PrusaSlicer path from preferences.
        prefs = bpy.context.preferences.addons[__package__].preferences
        prusaslicer_path = prefs.prusaslicer_path

        # Load configuration data.
        loader = bf.ConfigLoader()
        cx_props, _ = bf.get_inherited_slicing_props(cx, TYPES_NAME)
        if all(cx_props.values()):
            try:
                headers = prefs.profile_cache.config_headers
                loader.load_config(cx_props['printer'], headers)
                loader.load_config(cx_props['filament'], headers, append=True)
                loader.load_config(cx_props['print'], headers, append=True)
                loader.config_dict.update({
                    'printer_settings_id': cx_props['printer'].split(":")[1],
                    'filament_settings_id': cx_props['filament'].split(":")[1],
                    'print_settings_id': cx_props['print'].split(":")[1],
                })
                loader.load_list_to_overrides(pg.list)
                loader.add_pauses_and_changes(pg.pause_list)
            except Exception as e:
                show_progress(pg, 0, 'Error: failed to load configuration')
                pg.running = False
                return {'FINISHED'}

        # Export 3MF.
        show_progress(pg, 10, "Exporting 3MF...")
        objects = context.selected_objects
        model_names = [obj.name for obj in objects]
        if not model_names:
            show_progress(pg, 0, 'Error: selection empty')
            pg.running = False
            return {'FINISHED'}

        # Prepare mesh models.
        models = bf.prepare_mesh_split(context)
        bed_size = get_bed_size(loader.config_with_overrides.get('bed_shape', ''))
        bed_center = np.array([bed_size[0] / 2, bed_size[1] / 2, 0])
        models = [model + bed_center for model in models]

        # Create a temporary 3MF file and prepare the checksum.
        temp_3mf_fd, path_3mf = tempfile.mkstemp(suffix=".3mf")
        os.close(temp_3mf_fd)  # Close the file descriptor.
        checksum = prepare_3mf(path_3mf, models, loader, model_names)

        # Define paths for G-code.
        path_gcode_temp = os.path.join(os.path.dirname(path_3mf), f'{checksum}.gcode')
        path_gcode = determine_output_path(loader.config_with_overrides, model_names, self.mountpoint)

        # If no slicing configuration exists or mode is "open", just open PrusaSlicer.
        if not loader.config_dict or self.mode == "open":
            show_progress(pg, 100, 'Opening PrusaSlicer')
            process = multiprocessing.Process(
                target=psf.exec_prusaslicer,
                args=([path_3mf], prusaslicer_path)
            )
            process.start()
            pg.running = False
            return {'FINISHED'}

        # If cached G-code exists, copy it and preview if needed.
        if os.path.exists(path_gcode_temp):
            threaded_copy(path_gcode_temp, path_gcode)
            if self.mode == "slice_and_preview":
                show_preview(path_gcode_temp, prusaslicer_path)
            append_done = f" to {os.path.basename(self.mountpoint)}" if self.mountpoint else ""
            show_progress(pg, 100, f'Done (copied from cached gcode){append_done}')
            pg.print_time, pg.print_weight = get_stats(path_gcode_temp)
            pg.running = False
            return {'FINISHED'}

        # Otherwise, run slicing.
        if self.mode in ("slice", "slice_and_preview"):
            show_progress(pg, 30, 'Slicing with PrusaSlicer...')
            command = [path_3mf, "--dont-arrange", "-g", "--output", path_gcode_temp]
            results_queue = multiprocessing.Queue()
            process = multiprocessing.Process(
                target=run_slice,
                args=(command, path_gcode, results_queue, prusaslicer_path)
            )
            process.start()
            mode = self.mode
            bpy.app.timers.register(
                lambda: slicing_queue(pg, results_queue, mode, prusaslicer_path),
                first_interval=0.5
            )
            return {'FINISHED'}

        return {'FINISHED'}


def slicing_queue(pg, results_queue, mode: str, prusaslicer_path: str):
    if results_queue.empty():
        return 0.5  # Check again after 0.5 seconds.
    
    result = results_queue.get()
    if not result.get("error", False):
        pg.print_time = result["print_time"]
        pg.print_weight = result["print_weight"]
        show_progress(pg, result["progress_pct"], result["progress_text"])
    else:
        pg.print_time = "Error"
        pg.print_weight = "Error"
        show_progress(pg, 0, "Error")
    
    pg.running = False
    redraw()

    if mode == "slice_and_preview":
        show_preview(result['output_gcode_path'], prusaslicer_path)
    
    return None  # Stop the timer.


def determine_output_path(config: dict, obj_names: list, mountpoint: str) -> str:
    base_filename = "-".join(bf.names_array_from_objects(obj_names))
    filament = config.get('filament_type', 'Unknown filament')
    printer = config.get('printer_model', 'Unknown printer')
    ext = "bgcode" if config.get('binary_gcode', '0') == '1' else "gcode"
    full_filename = f"{base_filename}-{filament}-{printer}"
    gcode_filename = f"{full_filename}.{ext}"
    blendfile_directory = os.path.dirname(bpy.data.filepath)
    gcode_dir = mountpoint if mountpoint else (blendfile_directory if blendfile_directory else '/tmp/')
    return os.path.join(gcode_dir, gcode_filename)


def run_slice(command: list, path_gcode: str,
              results_queue: multiprocessing.Queue, prusaslicer_path: str):
    start_time = time.time()
    result_error = psf.exec_prusaslicer(command, prusaslicer_path)

    print_time = ''
    print_weight = ''

    if result_error:
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


def show_preview(gcode: str, prusaslicer_path: str):
    if gcode and os.path.exists(gcode):
        process = multiprocessing.Process(
            target=psf.exec_prusaslicer,
            args=(["--gcodeviewer", gcode], prusaslicer_path)
        )
        process.start()
    else:
        print("Gcode file not found: skipping preview.")


def get_stats(gcode: str) -> tuple:
    if os.path.exists(gcode):
        print_time = parse_gcode(gcode, 'estimated printing time \(normal mode\)') or ''
        print_weight = parse_gcode(gcode, 'filament used \[g\]') or ''
        return print_time, print_weight
    return '', ''
