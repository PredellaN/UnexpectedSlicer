import bpy # type: ignore
import numpy as np

import os, subprocess, time, tempfile, multiprocessing, json
from collections import namedtuple

from .functions import prusaslicer_funcs as psf 

from .functions.basic_functions import show_progress, threaded_copy, dict_from_json, redraw
from .functions import blender_funcs as bf
from .functions import gcode_funcs as gf
from . import TYPES_NAME

temp_files = []

class UnmountUsbOperator(bpy.types.Operator):
    bl_idname = f"export.unmount_usb"
    bl_label = "Unmount USB"
    mountpoint: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        try:
            if os.name == 'nt':
                result = os.system(f'mountvol {self.mountpoint} /D')
            else:
                # Use subprocess to capture output
                result = subprocess.run(['umount', self.mountpoint], capture_output=True, text=True)
                
                if result.returncode != 0:
                    if 'target is busy' in result.stderr:
                        self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}: device busy")
                    else:
                        self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}: {result.stderr}")
                    return {'CANCELLED'}
            
            self.report({'INFO'}, f"Successfully unmounted {self.mountpoint}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}
    
class RunPrusaSlicerOperator(bpy.types.Operator):
    bl_idname = f"export.slice"
    bl_label = "Run PrusaSlicer"

    mode: bpy.props.StringProperty(name="", default="slice") # type: ignore
    mountpoint: bpy.props.StringProperty(name="", default="") # type: ignore

    def progress_callback(self, context):
        cx = bf.coll_from_selection()
        pg = getattr(cx, TYPES_NAME)
        show_progress(pg, 0, "Preparing Configuration...")
    
    def execute(self, context):
        ws = context.workspace
        cx = bf.coll_from_selection()
        pg = getattr(cx, TYPES_NAME)

        prefs = bpy.context.preferences.addons[__package__].preferences
        global prusaslicer_path
        prusaslicer_path = prefs.prusaslicer_path

        pg.running = 1

        show_progress(pg, 0, "Preparing Configuration...")

        loader = bf.ConfigLoader()

        if pg.printer_config_file and pg.filament_config_file and pg.print_config_file:
            try:
                loader.load_config(pg.printer_config_file, prefs.profile_cache.config_headers, append=False)
                loader.load_config(pg.filament_config_file, prefs.profile_cache.config_headers, append=True)
                loader.load_config(pg.print_config_file, prefs.profile_cache.config_headers, append=True)
                loader.load_list_to_overrides(pg.list)
                loader.add_pauses_and_changes(pg.pause_list)
            except:
                show_progress(pg, 0, f'Error: failed to load configuration')

                pg.running = 0
                return {'FINISHED'}

        show_progress(pg, 10, "Exporting STL...")

        objects = context.selected_objects
        obj_names = [obj.name for obj in objects]

        if not len(obj_names):
            show_progress(pg, 0, f'Error: selection empty')
            getattr(cx, TYPES_NAME).running = 0
            return{'FINISHED'}

        paths = determine_paths(loader.config_with_overrides, obj_names, self.mountpoint)

        global temp_files
        temp_files = []

        depsgraph = bpy.context.evaluated_depsgraph_get()

        scene_scale = context.scene.unit_settings.scale_length

        selected_objects = [obj.evaluated_get(depsgraph) for obj in bpy.context.selected_objects if obj.type == 'MESH']
        tris_by_object = [bf.objects_to_tris([obj], 1000 * scene_scale) for obj in selected_objects]

        global_tris = np.concatenate(tris_by_object)
        vertices = global_tris[:, :3, :]
        min_coords, max_coords = vertices.min(axis=(0, 1)), vertices.max(axis=(0, 1))
        bed_size = gf.get_bed_size(loader.config_with_overrides['bed_shape']) if 'bed_shape' in loader.config_with_overrides else (0, 0)
        transform = (min_coords*(-0.5, -0.5, 1) + max_coords*(-0.5, -0.5, 0)) + np.array([bed_size[0]/2, bed_size[1]/2, 0])

        all_tris = []

        for i, tris in enumerate(tris_by_object):
            tris_transformed = bf.transform_tris(tris, transform)
            all_tris.append(tris_transformed)

        # Combine all transformed triangles into a single numpy array
        all_tris_combined = np.concatenate(all_tris, axis=0)

        bf.save_stl(all_tris_combined, paths.stl_path)
        temp_files.append(paths.stl_path)

        if not loader.config_dict:
            show_progress(pg, 100, 'Opening PrusaSlicer')
            command = [paths.stl_path]

            results_queue = multiprocessing.Queue()
            process = multiprocessing.Process(target=run_slice, args=(command, None, results_queue))
            process.start()
            bpy.app.timers.register(lambda: slicing_queue(pg, paths, results_queue), first_interval=0.5)

            getattr(cx, TYPES_NAME).running = 0
            return {'FINISHED'}

        temp_files.append(loader.write_ini(paths.ini_path))

        if self.mode == "open":
            show_progress(pg, 100, 'Opening PrusaSlicer')
            command = [paths.stl_path] + ["--load", paths.ini_path] + ["--dont-arrange"]

            process = multiprocessing.Process(target=psf.exec_prusaslicer, args=(command, prusaslicer_path,))
            process.start()

            pg.running = 0
            return {'FINISHED'}

        if os.path.exists(paths.gcode_temp_path) and os.path.exists(paths.json_temp_path):
            cached_data = dict_from_json(paths.json_temp_path)
            stl_chk = bf.calculate_md5([paths.stl_path])
            ini_chk = bf.calculate_md5([paths.ini_path])

            if stl_chk == cached_data.get('stl_chk') and ini_chk == cached_data.get('ini_chk'):

                threaded_copy(paths.gcode_temp_path, paths.gcode_path)
                if self.mode == "slice_and_preview":
                    process = show_preview(paths.gcode_temp_path)
                append_done = f" to {self.mountpoint.split('/')[-1]}" if self.mountpoint else ""
                show_progress(pg, 100, f'Done (copied from cached gcode){append_done}')
                
                print_time, print_weight = get_stats(paths.gcode_temp_path)
                pg.print_time = print_time
                pg.print_weight = print_weight

                getattr(cx, TYPES_NAME).running = 0
                return {'FINISHED'}

        if self.mode in ("slice", "slice_and_preview"):
            show_progress(pg, 30, 'Slicing with PrusaSlicer...')
            command = [
                "--load", paths.ini_path, 
                "-g",
                "--dont-arrange",
                "--output", os.path.join(paths.gcode_temp_path)
            ]
            command += [paths.stl_path]

            results_queue = multiprocessing.Queue()
            process = multiprocessing.Process(target=run_slice, args=(command, paths, results_queue))
            process.start()
            bpy.app.timers.register(lambda: slicing_queue(pg, paths, results_queue), first_interval=0.5)

            return {'FINISHED'}
        
def slicing_queue(pg, paths, results_queue):
    if results_queue.empty():
        return 0.5 

    result = results_queue.get()

    if not result.get("error", False):
        pg.print_time = result["print_time"]
        pg.print_weight = result["print_weight"]
        show_progress(pg, result["progress_pct"], result["progress_text"])
    else:
        pg.print_time = "Error"
        pg.print_weight = "Error"
        show_progress(pg, 0, "Error")

    pg.running = 0
    redraw()

    show_preview(paths.gcode_temp_path)
    cleanup()

    return None


def determine_paths(config, obj_names, mountpoint):
    paths = namedtuple('Paths', ['ini_path', 'stl_path', 'stl_temp_path', 'gcode_path', 'gcode_temp_path', 'json_temp_path'], defaults=[""]*5)

    base_filename = "-".join(bf.names_array_from_objects(obj_names))

    filament = config.get('filament_type', 'Unknown filament')
    printer = config.get('printer_model', 'Unknown printer')

    extension = "bgcode" if config.get('binary_gcode', '0') == '1' else "gcode"
    full_filename = f"{base_filename}-{filament}-{printer}"
    gcode_filename = f"{full_filename}.{extension}"
    json_filename = f"{full_filename}.json"

    temp_dir = tempfile.gettempdir()

    blendfile_directory = os.path.dirname(bpy.data.filepath)
    paths.stl_path = os.path.join(temp_dir, base_filename + ".stl")

    if mountpoint:
        gcode_dir = mountpoint
    elif blendfile_directory:
        gcode_dir = blendfile_directory
    else:
        gcode_dir = temp_dir

    paths.gcode_path = os.path.join(gcode_dir, gcode_filename)
    paths.gcode_temp_path = os.path.join(temp_dir, gcode_filename)
    paths.json_temp_path = os.path.join(temp_dir, json_filename)
    paths.ini_path = os.path.join(temp_dir, 'config.ini')
    return paths

def run_slice(command, paths, results_queue = None):

    start_time = time.time()
    res = psf.exec_prusaslicer(command, prusaslicer_path)
    
    print_time, print_weight = '', ''
    if res:
        end_time = time.time()
        progress_pct, progress_text = (0, f'Failed ({res})')
    else:
        
        if paths.gcode_temp_path:
            checksums = {
                "stl_chk": bf.calculate_md5([paths.stl_path]),
                "ini_chk": bf.calculate_md5([paths.ini_path])
            }
            with open(paths.json_temp_path, 'w') as json_file:
                json.dump(checksums, json_file, indent=4)
            
            print_time, print_weight = get_stats(paths.gcode_temp_path)
            threaded_copy(paths.gcode_temp_path, paths.gcode_path)
            
        end_time = time.time()
        progress_pct, progress_text = (100, f'Done (in {(end_time - start_time):.2f}s)')

    if results_queue:
        results_queue.put({
                "error": False,
                "print_time": print_time,
                "print_weight": print_weight,
                "progress_pct": progress_pct,
                "progress_text": progress_text
            })
            
    return {'FINISHED'}

def show_preview(gcode_path):
    if gcode_path and os.path.exists(gcode_path):
        gcode_process = multiprocessing.Process(target=psf.exec_prusaslicer, args=(["--gcodeviewer", gcode_path], prusaslicer_path))
        gcode_process.start()
    else:
        print("Gcode file not found: skipping preview.")

def get_stats(gcode_path):
    if os.path.exists(gcode_path):
        print_time = gf.parse_gcode(gcode_path, 'estimated printing time \(normal mode\)')
        print_weight = gf.parse_gcode(gcode_path, 'filament used \[g\]')
    return print_time if print_time else '', print_weight if print_weight else ''
    
def cleanup():
    global temp_files
    for file in temp_files:
        os.remove(file)
    temp_files = []