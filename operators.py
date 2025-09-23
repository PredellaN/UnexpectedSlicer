from __future__ import annotations
from typing import TYPE_CHECKING

from bpy_extras.io_utils import ExportHelper

if TYPE_CHECKING:
    from typing import Any
    from bpy.types import Object, Collection

    from .preferences.preferences import SlicerPreferences
    from .infra.profile_cache import LocalCache, ConfigWriter
    from bpy.stub_internal.rna_enums import OperatorReturnItems

from pathlib import Path
import bpy
import numpy as np
from numpy import float64
from numpy.typing import NDArray
import os
import subprocess
from subprocess import Popen
import tempfile
import sys

from .registry import register_class
from .utils.common import get_print_stats
from .infra.filesystem import file_copy
from .infra.prusaslicer_bridge import exec_prusaslicer
from .infra.blender_bridge import get_inherited_overrides, get_inherited_slicing_props, coll_from_selection, redraw, selected_top_level_objects, show_progress
from .utils.common import names_array_from_objects, get_bed_size
from .infra._3mf import prepare_3mf
from . import TYPES_NAME, PACKAGE

@register_class
class UnmountUsbOperator(bpy.types.Operator):
    bl_idname = "collection.unmount_usb"
    bl_label = "Unmount USB"

    mountpoint: bpy.props.StringProperty() # pyright: ignore[reportInvalidTypeForm]

    def execute(self, context) -> set[OperatorReturnItems]:
        try:
            if os.name == 'nt':
                result = os.system(f'mountvol {self.mountpoint} /D')
            else:
                result = subprocess.run(['umount', self.mountpoint],
                                        capture_output=True, text=True)
                if result.returncode != 0:
                    error_message = result.stderr
                    if 'target is busy' in error_message:
                        self.report({'ERROR'}, f"Failed to unmount: device is busy")
                    else:
                        self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to unmount {self.mountpoint}: {e}")
            return {'CANCELLED'}

class SlicingPaths():
    checksum: str = ''

    @staticmethod
    def names_array_from_objects(obj_names):
        from collections import Counter
        import re

        summarized_names = [re.sub(r'\.\d{0,3}$', '', name) for name in obj_names]
        name_counter = Counter(summarized_names)
        final_names = [f"{count}x_{name}" if count > 1 else name for name, count in name_counter.items()]
        final_names.sort()
        return final_names

    @staticmethod
    def safe_filename(base_txt: str, fixed_txt: str):
        allowed_base_length = 254 - len(fixed_txt)
        truncated_base = base_txt[:allowed_base_length]
        full_filename = f"{truncated_base}{fixed_txt}"
        return full_filename

    @property
    def blendfile_dir(self) -> Path:
        blendfile_path: str = bpy.data.filepath
        return Path(blendfile_path).parent if blendfile_path else Path('')

    @property
    def gcode_dir(self) -> Path:
        if self.out_dir: return Path(self.out_dir)
        else: return Path(tempfile.gettempdir())

    @property
    def path_gcode(self) -> Path:
        return Path(self.gcode_dir, self.name).with_suffix(self.ext)

    @property
    def path_gcode_temp(self) -> Path:
        if not self.checksum: return Path('')
        return Path(tempfile.gettempdir(), self.checksum).with_suffix(self.ext)

    @property
    def path_3mf(self) -> Path:
        return Path(tempfile.gettempdir(), self.name).with_suffix('.3mf')

    def __init__(self, config, obj_names: list[str], out_dir) -> None:
        self.out_dir = out_dir
        self.ext: str = ".bgcode" if config.config_dict.get('binary_gcode', '0') == '1' else ".gcode"
        
        #naming
        base_filename: str = "-".join(names_array_from_objects(obj_names))
        filament: str | list = config.config_dict.get('filament_type', 'Unknown filament')
        if isinstance(filament, list):
            filament = ";".join(filament)
        printer: str = config.config_dict.get('printer_model', 'Unknown printer')
        self.name: str = self.safe_filename(base_filename, f"-{filament}-{printer}")

        #3mf tempfile
        import tempfile
        temp_3mf_fd, path_3mf = tempfile.mkstemp(suffix=".3mf")
        os.close(temp_3mf_fd)
        self.path_3mf_temp = Path(path_3mf)

@register_class
class RunSlicerOperator(bpy.types.Operator, ExportHelper): # type: ignore
    bl_idname = "collection.slice"
    bl_label = "Run PrusaSlicer"

    mode: bpy.props.StringProperty(name="", default="slice") # pyright: ignore[reportInvalidTypeForm]
    mountpoint: bpy.props.StringProperty(name="", default="") # pyright: ignore[reportInvalidTypeForm]
    target_key: bpy.props.StringProperty(name="", default="") # pyright: ignore[reportInvalidTypeForm]
    filename_ext = ''

    @classmethod
    def description(cls, context, properties: RunSlicerOperator) -> str:
        if properties.mode == 'slice_and_preview': return "Slice and show the generated GCode in the PrusaSlicer GCode viewer"
        elif properties.mode == 'slice_and_preview_internal': return "Slice and show the generated GCode within blender"
        elif properties.mode == 'slice' and properties.mountpoint: return "Slice to the blendfile folder"
        elif properties.mode == 'slice' and not properties.mountpoint: return "Slice to a target folder"
        elif properties.mode == 'open': return "Open the selection in PrusaSlicer"
        else: return ""

    def invoke(self, context, event): # type: ignore
        if not self.mountpoint:
            return super().invoke(context, event) # run exporter
        else:
            return self.execute(context) # skip exporter
    
    def execute(self, context) -> set[OperatorReturnItems]:
        cx: Collection | None = coll_from_selection()
        pg = getattr(cx, TYPES_NAME)

        from .ui.gcode_preview import drawer
        drawer.stop()

        pg.running = True
        pg.print_stderr = pg.print_stdout = ""
        show_progress(pg, 0, "Preparing Configuration...")

        # Get the PrusaSlicer path from preferences.
        if not bpy.context.preferences: return {'FINISHED'}
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences
        prusaslicer_path = prefs.prusaslicer_path
        profiles_cache: 'LocalCache' = prefs.profile_cache

        # Load configuration data.
        if not cx: return {'CANCELLED'}
        if not context.scene: return {'CANCELLED'}
        
        cx_props: dict[str, Any] = get_inherited_slicing_props(cx, TYPES_NAME)

        sliceable: bool = cx_props['printer_config_file'].get('prop') and cx_props['filament_config_file'].get('prop') and cx_props['print_config_file'].get('prop')
        if sliceable: 
            try:
                overrides: dict[str, dict[str, Any]] = get_inherited_overrides(cx, TYPES_NAME)
                
                config_with_overrides: ConfigWriter = profiles_cache.generate_conf_writer(
                    cx_props['printer_config_file'].get('prop'),
                    [p['prop'] for k, p in cx_props.items() if k.startswith('filament')],
                    cx_props['print_config_file'].get('prop'),
                    overrides,
                    pg.pause_list
                )

            except Exception as e:
                pg.print_stdout = str(e)
                show_progress(pg, 0, 'Error: failed to load configuration')
                pg.running = False
                return {'FINISHED'}
        else:
            show_progress(pg, 0, 'Error: missing configuration!')
            return {'FINISHED'}

        # Export 3MF.
        show_progress(pg, 10, progress_text="Exporting 3MF...")

        from .infra.mesh_capture import SlicingGroup
        objs = bpy.context.selected_objects
        slicing_objects: SlicingGroup = SlicingGroup(objs)

        if not len(slicing_objects.collections):
            show_progress(pg, 0, 'Error: selection empty')
            pg.running = False
            return {'FINISHED'}

        bed_size: tuple[float, float] = get_bed_size(str(config_with_overrides.get('bed_shape', '')))
        bed_center: NDArray[float64] = np.array([bed_size[0] / 2, bed_size[1] / 2, 0], dtype=float64)
        transform = bed_center - slicing_objects.center_xy
        slicing_objects.offset(transform)

        obj_names: list[str] =[obj.name for obj in selected_top_level_objects()]

        import zlib, struct
        checksum_fast = zlib.crc32(struct.pack(">II", slicing_objects.checksum, config_with_overrides.checksum)) & 0xFFFFFFFF

        paths = SlicingPaths(
            config_with_overrides,
            obj_names,
            self.mountpoint if self.mountpoint else Path(getattr(self.properties, 'filepath')).parent
        )

        paths.checksum = str(checksum_fast)

        # Prepare preview_data
        preview_data = {
            'gcode_path': str(paths.path_gcode_temp),
            'transform': - transform,
            'bed_center': bed_center,
            'bed_size': (bed_size[0], bed_size[1], 0),
            'scene_scale': context.scene.unit_settings.scale_length,
            'model_height': slicing_objects.height
            }

        # If cached G-code exists, copy it and preview if needed.
        if os.path.exists(paths.path_gcode_temp) and not self.mode == "open":
            post_slicing(pg, None, objs, self.mode, self.target_key, prusaslicer_path, paths.path_gcode_temp, paths.path_gcode, preview_data)
            return {'FINISHED'}

        prepare_3mf(paths.path_3mf_temp, slicing_objects, config_with_overrides)

        # If no slicing configuration exists or mode is "open", just open PrusaSlicer.
        if not config_with_overrides or self.mode == "open":
            show_progress(pg, 100, 'Opening PrusaSlicer')

            if os.path.exists(paths.path_3mf):
                os.remove(paths.path_3mf)
            os.rename(paths.path_3mf_temp, paths.path_3mf)

            exec_prusaslicer([str(paths.path_3mf)], prusaslicer_path)

            pg.running = False
            return {'FINISHED'}

        # Otherwise, run slicing.
        show_progress(pg, 30, 'Slicing with PrusaSlicer...')
        command = [paths.path_3mf_temp, "--dont-arrange", "-g", "--output", paths.path_gcode_temp]

        proc: Popen[str] = exec_prusaslicer(command, prusaslicer_path)
        mode = self.mode
        target_key = self.target_key
        bpy.app.timers.register(
            lambda: post_slicing(pg, proc, objs, mode, target_key, prusaslicer_path, paths.path_gcode_temp, paths.path_gcode, preview_data),
            first_interval=0.5
        )

        return {'FINISHED'}

def process_handler(proc, time=0.2):
    if proc.poll() is None:
        return "", "", time

    if sys.platform.startswith("linux"):
        import select
        
        lines = ""
        while True:
            reads, _, _ = select.select([proc.stdout], [], [], 0)
            if proc.stdout in reads:
                line = proc.stdout.readline()
                if line == "":
                    break ## EOF
                lines += line
            else:
                return lines, "", time

    stdout, stderr = proc.communicate()

    return stdout, stderr, None

def post_slicing(pg, proc: Popen[str] | None, objects: list[Object], mode: str, target_key: str, prusaslicer_path: str, path_gcode_temp: Path, path_gcode_out: Path, preview_data: dict):
    stdout = stderr = ""

    if proc:
        stdout, stderr, timer = process_handler(proc)
        pg.print_stdout += stdout
        redraw()
        if timer: return timer

    if not os.path.exists(path_gcode_temp):
        pg.print_time = ""
        pg.print_weight = ""
        pg.print_stderr = stderr
        pg['preview_data'] = {}
        show_progress(pg, 0, "Slicing Failed")
        return None
        
    file_copy(path_gcode_temp, path_gcode_out)
    
    time, weight = get_print_stats(path_gcode_temp)

    pg.print_gcode = str(path_gcode_out)
    pg.print_time = time
    pg.print_weight = weight
    pg.print_stderr = ""
    pg['preview_data'] = preview_data
    show_progress(pg, 100, f"Slicing completed {'' if proc else '(copied from cache) '}to {path_gcode_out}")
    
    pg.running = False
    
    if os.path.exists(path_gcode_temp) and mode in ["slice_and_preview", "slice_and_preview_internal"]:
        if mode == "slice_and_preview" or '.bgcode' in preview_data['gcode_path']:
            show_preview(path_gcode_temp, prusaslicer_path)
        elif mode == "slice_and_preview_internal":
            from .ui.gcode_preview import drawer
            drawer.draw(preview_data, objects)

    if mode == 'slice' and target_key:
        from .services.physical_printers import printers_querier

        printers_querier.printers[target_key].start_print(path_gcode_temp, path_gcode_out.name)

    return None # Stop the timer.

def show_preview(gcode: Path, prusaslicer_path: str):
    if gcode and os.path.exists(gcode):
        exec_prusaslicer(["--gcodeviewer", str(gcode)], str(prusaslicer_path))
    else:
        print("Gcode file not found: skipping preview.")