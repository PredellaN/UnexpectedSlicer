from bpy.types import Object
from numpy.typing import NDArray

import bpy
import numpy as np
import gpu
import os
from gpu.types import GPUShader, GPUBatch
from gpu_extras.batch import batch_for_shader

from ..functions.basic_functions import profiler
from .. import TYPES_NAME

colors: dict[str, tuple[float, float, float, float]] = {
    'Perimeter': (1.0, 0.902, 0.302, 1.0),
    'External perimeter': (1.0, 0.49, 0.22, 1.0),
    'Overhang perimeter': (0.122, 0.122, 1.0, 1.0),
    'Internal infill': (0.69, 0.188, 0.161, 1.0),
    'Solid infill': (0.588, 0.329, 0.8, 1.0),
    'Top solid infill': (0.941, 0.251, 0.251, 1.0),
    'Bridge infill': (0.302, 0.502, 0.729, 1.0),
    'Skirt/Brim': (0.0, 0.529, 0.431, 1.0),
    'Custom': (0.369, 0.82, 0.58, 1.0),
    'Support material': (0, 1, 0, 1),
    'Support material interface': (0, 0.5, 0, 1),
    'Gap fill': (1, 1, 1, 1),
}

prop_to_id = {
    'gcode_perimeter': 'Perimeter',
    'gcode_external_perimeter': 'External perimeter',
    'gcode_overhang_perimeter': 'Overhang perimeter',
    'gcode_internal_infill': 'Internal infill',
    'gcode_solid_infill': 'Solid infill',
    'gcode_top_solid_infill': 'Top solid infill',
    'gcode_bridge_infill': 'Bridge infill',
    'gcode_skirt_brim': 'Skirt/Brim',
    'gcode_custom': 'Custom',
    'gcode_support_material': 'Support material',
    'gcode_support_material_interface': 'Support material interface',
    'gcode_gap_fill': 'Gap fill',
}

import mmap
def count_lines_mmap(path):
    """Count newlines by slicing the mmap and using bytes.count."""
    with open(path, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        # mm[:] gives you a bytes object of the whole file
        n = mm[:].count(b'\n')
        mm.close()
    return n

class GcodeData():
    path: str

    size: int
    pos: NDArray[np.float32]
    idx: NDArray[np.int32]
    color: NDArray[np.float32]
    width: NDArray[np.float32]
    height: NDArray[np.float32]
    z: NDArray[np.float32]
    type: NDArray[np.bytes_]
    mask: NDArray[bool]

    def __init__(self, path):
        self.path = path

        n = count_lines_mmap(self.path)

        self.pos = np.zeros((n, 3), dtype=np.float32)
        self.color = np.zeros((n, 4), dtype=np.float32)
        self.width = np.zeros((n), dtype=np.float32)
        self.height = np.zeros((n), dtype=np.float32)
        self.type = np.empty((n), dtype='S26')
        self.mask = np.full(n, True, dtype=bool)

        segments = np.full((n, 2), -1, dtype=np.int64)

        with open(self.path, 'r') as f:
            
            split = str.split

            #temporary vars
            x = y = z = e = w = h = 0.0
            last_valid_point = None
            type = 'Custom'
            col = colors[type]

            for i, raw in enumerate(f):
                if not raw:
                    continue

                if raw[0] == ';':
                    if raw[0:6] == ';TYPE:':
                        type = raw[6:].strip() or 'Custom'
                        col = colors[type]
                        continue

                    if raw[0:7] == ';WIDTH:':
                        w: float = float(raw[7:])
                        continue

                    if raw[0:8] == ';HEIGHT:':
                        h: float = float(raw[8:])
                        continue
                    continue

                if raw[0:2] == 'G1':
                    e=0

                    tokens=split(raw[2:])
                        
                    for tok in tokens:
                        p, v = tok[0], tok[1:]
                        if   p == ';': break
                        if   p == 'X': x = float(v)
                        elif p == 'Y': y = float(v)
                        elif p == 'Z': z = float(v)
                        elif p == 'E': e = float(v)

                    self.pos[i] = (x, y, z)
                    self.color[i] = col
                    self.width[i] = w
                    self.height[i] = h
                    self.type[i] = type

                    if last_valid_point and e > 0:
                        segments[i] = (last_valid_point, i)

                    last_valid_point = i
                        
                    continue

            segment_mask = segments[:, 0] != -1
            self.idx = segments[segment_mask]

    def to_tris(self, transform, mask, scale: float = 0.001) -> dict[str, dict[str, np.ndarray] | np.ndarray]:

        p = {}

        # Initialize lists
        result: dict[str, dict[str, np.ndarray] | np.ndarray] = {
            'content': {
                'pos': np.empty((0, 4)),
                'color': np.empty((0, 3)),
            },
            'tris_idx': np.empty((0,3), dtype=np.int32),
        }

        if len(self.pos) == 0:
            return result
            
        # Compute the segment vectors and directions
        mask = mask[self.idx[:, 0]]
        p['p1'] = self.pos[self.idx[:, 0]] + transform
        p['p2'] = self.pos[self.idx[:, 1]] + transform
        p['color'] = self.color[self.idx[:, 0]]
        p['width'] = self.width[self.idx[:, 0]]
        p['height'] = self.height[self.idx[:, 0]]

        p = { k: v[mask] for k, v in p.items() }

        if len(p['p1']) == 0:
            return result

        directions = p['p2'] - p['p1']
        direction_lengths = np.linalg.norm(directions, axis=1)

        # Normalize directions (unit vectors)
        mask_length = direction_lengths != 0
        p = { k: v[mask_length] for k, v in p.items() }
        direction_unit = directions[mask_length] / direction_lengths[mask_length][:, None]

        # Compute perpendiculars
        perpendicular = np.column_stack([-direction_unit[:, 1], direction_unit[:, 0], np.zeros(len(direction_unit))])

        # Create z-direction vector
        z = np.array([0, 0, 1])

        off1 =  z * p['height'][:, np.newaxis]/2
        off2 = -perpendicular * p['width'][:, np.newaxis]/2
        off3 = -z * p['height'][:, np.newaxis]/2
        off4 =  perpendicular * p['width'][:, np.newaxis]/2

        # build 8 pts per p1/p2 pair
        p1_block = np.stack((p['p1'] + off1, p['p1'] + off2, p['p1'] + off3, p['p1'] + off4), axis=1) * scale
        p2_block = np.stack((p['p2'] + off1, p['p2'] + off2, p['p2'] + off3, p['p2'] + off4), axis=1) * scale

        # (n,8,3) → (8n,3)
        all_points: NDArray[int] = np.concatenate((p1_block, p2_block), axis=1).reshape(-1, 3)

        # triangle indices
        base_tris: NDArray[int] = np.array([[0,4,1],[1,4,5],[1,5,2],[3,7,0],
                            [2,5,6],[2,6,3],[3,6,7],[7,4,0]], dtype=int)

        num_blocks: int = len(p['p1'])
        tris_tiled: NDArray[int] = np.tile(base_tris, (num_blocks, 1))
        offsets: NDArray[int] = np.repeat(np.arange(num_blocks) * 8, base_tris.shape[0])

        tris: NDArray[int] = tris_tiled + offsets[:, np.newaxis]

        # Compute colors once, then tile them
        c: NDArray[float] = np.repeat(p['color'], 8, axis=0)
        c[1::2] *= (0.75, 0.75, 0.75, 1)
        c[2::4] *= (0.5, 0.5, 0.5, 1)

        return {
            'content': {
                'pos': all_points,
                'color': c,
            }, 
            'tris_idx': tris
        }

class GcodeDraw():
    shader: GPUShader = gpu.shader.from_builtin('SMOOTH_COLOR')
    batch: list[GPUBatch | None] = []
    enabled: bool = False

    hidden_objects: list[Object] = []
    max_z: float = 0

    _draw_handler = None

    gcode: GcodeData | None = None
    filters = {}

    def _tris_batch(self, shader, content, tris_idx):
        if len(tris_idx) == 0 or len(content['pos']) == 0: return None
        return batch_for_shader(
            shader,
            "TRIS",
            content={
                "pos": content['pos'].astype(np.float32),
                "color":   content['color'].astype(np.float32),
            },
            indices=tris_idx.astype(np.int32),
        )

    def _filter_model(self):
            z = self.gcode.pos[:, 2]

            mask_max_z = z < self.filters['max_z']
            mask_min_z = z > self.filters['min_z']
            mask_active_layer = np.isin(self.gcode.type, [ name.encode('utf-8') for name in self.filters['active_layers'] ])
            
            self.mask = mask_max_z * mask_min_z * mask_active_layer

    def _preview_plate(self, scale = 0.001):
        bed = np.array([
            (-1, -1,  0),
            ( 1, -1,  0),
            (-1,  1,  0),
            ( 1,  1,  0),
        ], dtype=np.float32) * 0.5 * self._preview_data['bed_size'] + self._preview_data['transform'] + self._preview_data['bed_center']
        bed_color = np.vstack([(0.05, 0.05, 0.05, 1)] * 4)
        bed_tris = np.array(((0,2,1), (1,2,3)), dtype=np.int32)

        return {
            'content': {
                'pos': bed * scale,
                'color': bed_color,
            },
            'tris_idx': bed_tris,
        }

    def _prepare_batches(self):
        self.batch = []

        self.batch += [self._tris_batch(self.shader, **self.gcode.to_tris(self._preview_data['transform'], self.mask, scale = 0.001 / self._preview_data['scene_scale']))]
        self.batch += [self._tris_batch(self.shader, **self._preview_plate(scale = 0.001 / self._preview_data['scene_scale']))]

    def _tag_redraw(self):
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    
    def _props_from_context(self):
        workspace = bpy.context.workspace
        ws_pg = getattr(workspace, TYPES_NAME)
        self.filters = {
            'min_z': ws_pg.gcode_preview_min_z,
            'max_z': ws_pg.gcode_preview_max_z,
            'active_layers': [prop_to_id[n] for n in list(prop_to_id.keys()) if getattr(ws_pg, n)],
        }
    
    def _default_preview_settings(self):
        workspace = bpy.context.workspace
        ws_pg = getattr(workspace, TYPES_NAME)
        self.max_z = self._preview_data['model_height']
        ws_pg.gcode_preview_min_z = 0
        ws_pg.gcode_preview_max_z = self._preview_data['model_height']
        
    def _gpu_draw(self):
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.front_facing_set(True)
        gpu.state.face_culling_set("BACK")

        for b in self.batch:
            if b:
                b.draw(self.shader)

        gpu.state.face_culling_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.front_facing_set(False)

    def _gpu_undraw(self):
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
            self._tag_redraw()

    def _show_objects(self):
        for obj in self.hidden_objects:
            try:
                obj.hide_set(False)
            except Exception as e:
                print(f"Could not show object {obj!r}: {e}")

    def _hide_objects(self):
        for obj in self.hidden_objects:
            try:
                obj.hide_set(True)
            except Exception as e:
                print(f"Could not hide object {obj!r}: {e}")

    def draw(self, preview_data, objects = []):
        self.enabled = True
        self.hidden_objects = objects
        self._preview_data = preview_data
        self._default_preview_settings()
        self.gcode = GcodeData(self._preview_data['gcode_path'])
        self.update()

    def update(self):
        if self.gcode and self.enabled:
            self._gpu_undraw()
            self._props_from_context()
            self._filter_model()
            self._prepare_batches()
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._gpu_draw, (), 'WINDOW', 'POST_VIEW')
            self._hide_objects()
            self._tag_redraw()
    
    def stop(self):
        self.enabled = False
        self._gpu_undraw()
        self._show_objects()
        self.hidden_objects = []

drawer: GcodeDraw = GcodeDraw()