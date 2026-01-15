from dataclasses import dataclass, asdict
from pathlib import Path
import struct
from subprocess import Popen
import os
from typing import Any, Callable
import zlib
import bpy
import subprocess
import numpy as np

from ..preferences.preferences import SlicerPreferences
from ..props.property_groups import SlicingPaths
from ..ui.gcode_preview import drawer
from ..utils.common import get_bed_size, get_print_stats
from ..infra.system import ProcessReader
from ..infra.filesystem import file_copy
from ..infra.blender_bridge import coll_from_selection, get_inherited_slicing_props, show_progress, get_inherited_overrides, selected_top_level_objects, redraw
from ..infra.profile_cache import LocalCache, ConfigWriter
from ..infra.blender_mesh_capture import SlicingGroup
from ..infra.blender_gcode_manipulation import import_g1_as_mesh

from .. import TYPES_NAME, PACKAGE

def exec_prusaslicer(command: list[str], prusaslicer_path: str) -> Popen[str]:
    executable: list[str] = [f'{prusaslicer_path}'] if os.path.exists(prusaslicer_path) else [*prusaslicer_path.split()]
    cmd: list[str] = executable + command

    proc: Popen[str] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ)

    return proc

@dataclass
class GCodePreviewData:
    gcode_path: str
    transform: np.ndarray
    bed_center: np.ndarray
    bed_size: tuple[float, float, float]
    scene_scale: float
    model_height: float
    config: dict[str, str | list[str]]
    objs: list[str]

@dataclass
class Z_GCode:
    z: float
    type: int
    extruder: int
    color: str
    extra: str
    gcode: str

    @property
    def dict(self) -> dict:
        return asdict(self)

def rgb_to_html(rgb: tuple[float, float, float]) -> str:
    r: int = int(round(rgb[0] * 255))
    g: int = int(round(rgb[1] * 255))
    b: int = int(round(rgb[2] * 255))
    html: str = "#{:02X}{:02X}{:02X}".format(r, g, b)
    return html

class SlicerService:
    def __init__(self, prusaslicer_path: str, profiles_cache: LocalCache):
        self.prusaslicer_path: str = prusaslicer_path
        self.profiles_cache: LocalCache = profiles_cache
        self.config_with_overrides: ConfigWriter | None = None
        self.z_gcodes: list[Z_GCode] = []

    def _load_config(self, cx, types_name: str, pg) -> ConfigWriter | None:
        cx_props: dict[str, Any] = get_inherited_slicing_props(cx, types_name)
        sliceable = (
            cx_props['printer_config_file'].get('prop')
            and cx_props['filament_config_file'].get('prop')
            and cx_props['print_config_file'].get('prop')
        )
        if not sliceable:
            show_progress(pg, 0, 'Error: missing configuration!')
            return None

        try:
            overrides: dict[str, dict[str, Any]] = get_inherited_overrides(cx, types_name)

            self.config_with_overrides = self.profiles_cache.generate_conf_writer(
                cx_props['printer_config_file'].get('prop'),
                [p['prop'] for k, p in cx_props.items() if k.startswith('filament')],
                cx_props['print_config_file'].get('prop'),
                overrides,
            )

            cfg = self.config_with_overrides.config_dict
            assert isinstance(cfg['num_extruders'], str)
            colors: list[str] = []
            for i in range(int(cfg['num_extruders'])):
                rgb = getattr(pg, f"filament{['','_2','_3','_4','_5'][i]}_color")
                colors += [rgb_to_html(rgb)]
            cfg['extruder_colour'] = ';'.join(colors)

        except Exception as e:
            pg.print_stdout = str(e)
            show_progress(pg, 0, 'Error: failed to load configuration')        

    def _prepare_z_gcodes(self, p_list):
        assert self.config_with_overrides
        assert self.config_with_overrides.config_dict

        p_map: dict[str, int] = {
            'pause': 1,
            'color_change': 0,
            'custom_gcode': 4
        }
        p_xlat: dict[str, str] = {
            'pause': 'Pause',
            'color_change': 'Color Change',
            'custom_gcode': 'Custom Gcode'
        }
        
        for p in list(p_list):
            p_gcode: dict[str, str] = {
                'pause': "M601",
                'color_change': "M600\nG1 E0.3 F1500 ; prime after color change",
                'custom_gcode': p.param_cmd
            }
            layer_heights: str | list[str] = self.config_with_overrides.config_dict['layer_height']
            layer_height: float = float(layer_heights) if isinstance(layer_heights, str) else float(layer_heights[0])
            z_value = p.param_float if p.param_value_type == 'height' else p.param_float * layer_height

            self.z_gcodes += [Z_GCode(
                z=z_value,
                type=p_map[p.param_type],
                extruder=1,
                color=rgb_to_html(p.param_color) if p.param_type == 'color_change' else '',
                extra=p_xlat[p.param_type],
                gcode=p_gcode[p.param_type]
            )]

    def build_slicing_group_and_transform(self, pg) -> tuple[SlicingGroup, np.ndarray, np.ndarray, tuple[float, float]]:
        assert self.config_with_overrides

        objs = bpy.context.selected_objects
        slicing_objects = SlicingGroup(objs)

        bed_size = get_bed_size(str(self.config_with_overrides.get('bed_shape', '')))
        bed_center = np.array([bed_size[0] / 2, bed_size[1] / 2, 0], dtype=np.float64)
        transform = bed_center - slicing_objects.center_xy
        slicing_objects.offset(transform)
        return slicing_objects, transform, bed_center, bed_size

    def make_paths(self, conf: ConfigWriter, mountpoint: str | None, operator_props) -> None:
        assert self.config_with_overrides

        obj_names = [obj.name for obj in selected_top_level_objects()]
        target_dir = (
            Path(mountpoint)
            if mountpoint
            else Path(getattr(operator_props, 'filepath')).parent
        )
        self.paths = SlicingPaths(self.config_with_overrides, obj_names, target_dir)
        self._paths_checksum()

    def _paths_checksum(self):
        assert self.config_with_overrides
        checksum_fast = zlib.crc32(struct.pack(
            ">III",
            self.slicing_objects.checksum,
            self.config_with_overrides.checksum,
            self._z_gcodes_checksum,
        )) & 0xFFFFFFFF
        self.paths.checksum = str(checksum_fast)

    @property
    def _z_gcodes_checksum(self):
        import json, zlib
        data = json.dumps([z.dict for z in self.z_gcodes] , sort_keys=True).encode("utf-8")
        return zlib.crc32(data) & 0xFFFFFFFF

    def export_3mf(self, paths: SlicingPaths):
        from ..infra._3mf import prepare_3mf
        prepare_3mf(paths.path_3mf_temp, self.slicing_objects, self.config_with_overrides, self.z_gcodes)

    def open_in_prusaslicer(self, three_mf: Path):
        show_progress(self.pg, 100, 'Opening PrusaSlicer')
        if os.path.exists(self.paths.path_3mf):
            os.remove(self.paths.path_3mf)
        os.rename(three_mf, self.paths.path_3mf)
        exec_prusaslicer([str(self.paths.path_3mf)], self.prusaslicer_path)

    def run_slice(self):
        show_progress(self.pg, 30, 'Slicing with PrusaSlicer...')
        command = [self.paths.path_3mf_temp, "--dont-arrange", "-g", "--output", self.paths.path_gcode_temp]
        return exec_prusaslicer(command, self.prusaslicer_path)

    def after_slice_success(self, mode: str, target_key: str, metadata: GCodePreviewData):
        file_copy(self.paths.path_gcode_temp, self.paths.path_gcode)

        time_str, weight = get_print_stats(self.paths.path_gcode_temp)
        self.pg.print_gcode = str(self.paths.path_gcode)
        self.pg.print_time = time_str
        self.pg.print_weight = weight
        self.pg.print_stderr = ""

        self.pg['metadata'] = metadata.__dict__

        show_progress(self.pg, 100, f"Slicing completed {'(copied from cache) ' if self._used_cache else ''}to {self.paths.path_gcode}")

        self.pg.running = False

        # Open previews
        if os.path.exists(self.paths.path_gcode_temp) and mode in ["slice_and_preview", "slice_and_preview_internal"]:
            if mode == "slice_and_preview" or '.bgcode' in metadata.gcode_path:
                PreviewManager.show_external(self.paths.path_gcode_temp, self.prusaslicer_path)
            else:
                PreviewManager.show_internal(metadata, self.objects)

        # Direct print
        if mode == 'slice' and target_key:
            from ..services.physical_printers import printers_querier
            lf: Callable[[], None] = lambda: printers_querier.printers[target_key].backend.start_print(self.paths.path_gcode_temp, self.paths.path_gcode.name)
            printers_querier.run_command(target_key, lf)

    def execute(self, context, operator_props, mode: str, mountpoint: str, target_key: str) -> set[str]:
        drawer.stop()

        cx = coll_from_selection()
        if not cx or not context.scene:
            return {'CANCELLED'}
        self.pg = getattr(cx, TYPES_NAME)
        self.pg.running = True
        self.pg.print_stderr = self.pg.print_stdout = ""
        show_progress(self.pg, 0, "Preparing Configuration...")

        if not bpy.context.preferences:
            return {'FINISHED'}
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences
        self.prusaslicer_path = prefs.prusaslicer_path
        self.profiles_cache = prefs.profile_cache

        # Configuration
        self._load_config(cx, TYPES_NAME, self.pg)
        if self.config_with_overrides is None:
            self.pg.running = False
            return {'FINISHED'}

        # Z Gcodes
        self._prepare_z_gcodes(self.pg.pause_list)

        # Geometry
        so, transform, bed_center, bed_size = self.build_slicing_group_and_transform(self.pg)
        if not so:
            self.pg.running = False
            return {'FINISHED'}

        self.slicing_objects = so
        self.objects = bpy.context.selected_objects

        self.make_paths(self.config_with_overrides, mountpoint, operator_props)

        metadata: GCodePreviewData = GCodePreviewData(
            gcode_path=str(self.paths.path_gcode_temp),
            transform=-transform,
            bed_center=bed_center,
            bed_size=(bed_size[0], bed_size[1], 0),
            scene_scale=context.scene.unit_settings.scale_length,
            model_height=self.slicing_objects.height,
            config=self.config_with_overrides.config_dict,
            objs=[o.name for o in self.objects]
        )

        # Cache hit short-circuit
        if os.path.exists(self.paths.path_gcode_temp) and mode != "open":
            self._used_cache = True
            PostSliceTimer.finish_immediately(self.pg, None, self.objects, mode, target_key, self.prusaslicer_path, self.paths, metadata)
            return {'FINISHED'}

        # Export 3MF
        show_progress(self.pg, 10, progress_text="Exporting 3MF...")
        self.export_3mf(self.paths)

        # Open-only mode
        if mode == "open" or not self.config_with_overrides:
            show_progress(self.pg, 100, 'Opening PrusaSlicer')
            self.open_in_prusaslicer(self.paths.path_3mf_temp)
            self.pg.running = False
            return {'FINISHED'}

        # Slice and register timer to poll process
        self._used_cache = False
        proc = self.run_slice()
        bpy.app.timers.register(
            lambda: PostSliceTimer.poll_and_finish(
                self.pg,
                proc,
                self.objects,
                mode,
                target_key,
                self.prusaslicer_path,
                self.paths,
                metadata,
            ),
            first_interval=0.5,
        )
        return {'FINISHED'}



class PreviewManager:
    @staticmethod
    def show_external(gcode: Path, prusaslicer_path: str):
        if gcode and os.path.exists(gcode):
            exec_prusaslicer(["--gcodeviewer", str(gcode)], str(prusaslicer_path))
        else:
            print("Gcode file not found: skipping preview.")

    @staticmethod
    def show_internal(metadata: GCodePreviewData, objects: list[bpy.types.Object]):
        drawer.draw(metadata.__dict__, objects)

class PostSliceTimer:
    @staticmethod
    def poll_and_finish(pg, proc: Popen[str], objects: list[bpy.types.Object], mode: str, target_key: str, prusaslicer_path: str, paths: SlicingPaths, metadata: GCodePreviewData):
        stdout, stderr, next_wait = ProcessReader.read(proc)
        if stdout:
            pg.print_stdout += stdout
            redraw()
        if next_wait: return next_wait
        # finished
        return PostSliceTimer._finalize(pg, stderr, objects, mode, target_key, prusaslicer_path, paths, metadata)

    @staticmethod
    def finish_immediately(pg, proc: Popen[str] | None, objects: list[bpy.types.Object], mode: str, target_key: str, prusaslicer_path: str, paths: SlicingPaths, metadata: GCodePreviewData):
        return PostSliceTimer._finalize(pg, "", objects, mode, target_key, prusaslicer_path, paths, metadata)

    @staticmethod
    def _finalize(pg, stderr: str, objects: list[bpy.types.Object], mode: str, target_key: str, prusaslicer_path: str, paths: SlicingPaths, metadata: GCodePreviewData):
        if not os.path.exists(paths.path_gcode_temp):
            pg.print_time = ""
            pg.print_weight = ""
            pg.print_stderr = stderr
            pg['metadata'] = {}
            show_progress(pg, 0, "Slicing Failed")
            return None

        # import_g1_as_mesh(metadata)
        
        # Copy gcode to final location and update UI/state
        file_copy(paths.path_gcode_temp, paths.path_gcode)
        time_str, weight = get_print_stats(paths.path_gcode_temp)
        pg.print_gcode = str(paths.path_gcode)
        pg.print_time = time_str
        pg.print_weight = weight
        pg.print_stderr = ""
        pg['metadata'] = metadata.__dict__
        show_progress(pg, 100, f"Slicing completed to {paths.path_gcode}")
        pg.running = False

        # Previews
        if os.path.exists(paths.path_gcode_temp) and mode in ["slice_and_preview", "slice_and_preview_internal"]:
            if mode == "slice_and_preview" or '.bgcode' in metadata.gcode_path:
                PreviewManager.show_external(paths.path_gcode_temp, prusaslicer_path)
            else:
                PreviewManager.show_internal(metadata, objects)

        # Optional: auto start print
        if mode == 'slice' and target_key:
            from ..services.physical_printers import printers_querier
            lf: Callable[[], None] = lambda: printers_querier._printers[target_key].backend.start_print(paths.path_gcode_temp, paths.path_gcode.name)
            printers_querier.run_command(target_key, lf)

        return None  # stop timer

def apply_texture(path):
    pass