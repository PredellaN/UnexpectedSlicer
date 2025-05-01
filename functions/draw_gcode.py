from numpy.typing import NDArray
from typing import Any

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
}

def gcode_to_segments(path) -> tuple[
        dict[str, [np.ndarray, np.ndarray]],
        np.ndarray
    ]:

    # Initialize empty arrays for positions and colors
    points_pos = []
    points_color = []
    points_width = []
    points_height = []
    points_type = []
    segments = []

    with open(path, 'r') as f:
        prev_pt = None
        seg_i = 0

        pos_append = points_pos.append
        col_append = points_color.append
        width_append = points_width.append
        height_append = points_height.append
        type_append = points_type.append
        seg_append = segments.append
        
        starts     = str.startswith
        split      = str.split

        x = y = z = e = w = h = 0.0
        type = 'Custom'
        col = colors[type]
        for raw in f:
            if not raw:
                continue

            if raw[0] == ';':
                if starts(raw, ';TYPE:'):
                    type = raw[6:].strip() or 'Custom'
                    col = colors[type]
                    continue

                if starts(raw, ';WIDTH:'):
                    w: float = float(raw[7:].strip())
                    continue

                if starts(raw, ';HEIGHT:'):
                    h: float = float(raw[8:].strip())
                    continue
                continue

            if raw[0] == 'G' and raw[1] == '1':
                tokens = split(raw)
                e = 0.0
                for tok in tokens[1:]:
                    p, v = tok[0], tok[1:]
                    if   p == ';': break
                    if   p == 'X': x = float(v)
                    elif p == 'Y': y = float(v)
                    elif p == 'Z': z = float(v)
                    elif p == 'E': e = float(v)

                pt = (x, y, z)
                pos_append(pt)
                col_append(col)
                width_append(w)
                height_append(h)
                type_append(type)

                if prev_pt is not None and e > 0:
                    seg_append((seg_i - 1, seg_i))

                seg_i += 1
                prev_pt = pt

    points = {
        'pos': np.array(points_pos),
        'color': np.array(points_color),
        'width': np.array(points_width),
        'height': np.array(points_height),
        'type': np.array(points_type),
    }
    segments = np.array(segments)

    return points, segments

import numpy as np

def segments_to_tris(points: dict[str, list[Any]], idx: np.ndarray, transform, mask, scale: float = 0.001) -> tuple[dict[str, NDArray[float] | None], NDArray[int]]:
    # Initialize lists
    points_tris: dict[str, NDArray | None] = {'pos': None, 'color': None}

    # Extract position and color arrays once
    positions = points['pos'] + transform

    # Compute the segment vectors and directions
    mask = mask[idx[:, 0]]
    p1 = positions[idx[:, 0]][mask]
    p2 = positions[idx[:, 1]][mask]
    c = points['color'][idx[:, 0]][mask]
    w = points['width'][idx[:, 0]][mask]
    h = points['height'][idx[:, 0]][mask]

    # Remove zero length segments
    zero_length_mask = np.any(p2 - p1 != np.array([0,0,0]), -1)
    p1 = p1[zero_length_mask]
    p2 = p2[zero_length_mask]
    c = c[zero_length_mask]
    w = w[zero_length_mask]
    h = h[zero_length_mask]

    directions = p2 - p1
    direction_lengths = np.linalg.norm(directions, axis=1)
    
    # Avoid division by zero (for zero-length segments)
    valid = direction_lengths > 0
    directions[~valid] = 0  # Set zero-length directions to zero vector

    # Normalize directions (unit vectors)
    direction_unit = directions / direction_lengths[:, None]

    # Compute perpendiculars
    perpendicular = np.column_stack([-direction_unit[:, 1], direction_unit[:, 0], np.zeros(len(direction_unit))])

    # Create z-direction vector
    z = np.array([0, 0, 1])

    off1 =  z * h[:, np.newaxis]/2
    off2 = -perpendicular * w[:, np.newaxis]/2
    off3 = -z * h[:, np.newaxis]/2
    off4 =  perpendicular * w[:, np.newaxis]/2

    # build 8 pts per p1/p2 pair
    p1_block = np.stack((p1 + off1, p1 + off2, p1 + off3, p1 + off4), axis=1) * scale
    p2_block = np.stack((p2 + off1, p2 + off2, p2 + off3, p2 + off4), axis=1) * scale

    # (n,8,3) → (8n,3)
    all_points: NDArray[int] = np.concatenate((p1_block, p2_block), axis=1).reshape(-1, 3)
    points_tris['pos'] = all_points

    # triangle indices
    base_tris: NDArray[int] = np.array([[0,1,4],[1,5,4],[1,2,5],[3,0,7],
                        [2,6,5],[2,3,6],[3,7,6],[7,4,0]], dtype=int)

    num_blocks: int = len(p1)
    tris_tiled: NDArray[int] = np.tile(base_tris, (num_blocks, 1))
    offsets: NDArray[int] = np.repeat(np.arange(num_blocks) * 8, base_tris.shape[0])

    tris: NDArray[int] = tris_tiled + offsets[:, np.newaxis]

    # Compute colors once, then tile them
    c: NDArray[float] = np.repeat(c, 8, axis=0)
    c[1::2] *= (0.75, 0.75, 0.75, 1)
    c[2::4] *= (0.5, 0.5, 0.5, 1)
    
    # Flatten the list of colors and append them
    points_tris['color'] = c

    return points_tris, tris

class GcodeDraw():
    shader: GPUShader = gpu.shader.from_builtin('SMOOTH_COLOR')

    batch: GPUBatch | None = None

    _draw_handler = None

    #Bare data
    gcode_points = None
    gcode_points_idx = None
    transform = None

    #Filtered data
    points_tris = None
    tris = None

    #Workspace props
    min_z = 0
    max_z = 0
    active_layers = []

    def _tris_batch(self, shader, content, tris_idx):
        batch = batch_for_shader(
            shader,
            "TRIS",
            content={
                "pos": content['pos'].astype(np.float32),
                "color":   content['color'].astype(np.float32),
            },
            indices=tris_idx.astype(np.int32),
        )
        self.batch = batch

    def _prepare_model(self, path: str):
        if os.path.exists(path):
            self.gcode_points, self.gcode_points_idx = gcode_to_segments(path)

    def _filter_model(self):
        if self.gcode_points and len(self.gcode_points_idx):

            z = self.gcode_points['pos'][:, 2]
            default_true = np.ones_like(z, dtype=bool)

            mask_max_z = z < self.max_z
            mask_min_z = z > self.min_z

            mask_active_layer = np.isin(self.gcode_points['type'], self.active_layers)
            
            aggregated_mask = mask_max_z * mask_min_z * mask_active_layer

            self.points_tris, self.tris = segments_to_tris(self.gcode_points, self.gcode_points_idx, self.transform, aggregated_mask)

    def _create_batch(self):
        if len(self.points_tris) and len(self.tris):
            self._tris_batch(self.shader, self.points_tris, tris_idx=self.tris)

    def _tag_redraw(self):
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    
    def _draw(self):
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.front_facing_set(True)

        if self.batch:
            self.batch.draw(self.shader)

        gpu.state.depth_test_set("NONE")
        gpu.state.front_facing_set(False)

    def _props_from_context(self):
        workspace = bpy.context.workspace
        ws_pg = getattr(workspace, TYPES_NAME)
        self.min_z = ws_pg.gcode_preview_min_z
        self.max_z = ws_pg.gcode_preview_max_z
        self.active_layers = [prop_to_id[n] for n in list(prop_to_id.keys()) if getattr(ws_pg, n)]

    @profiler
    def draw(self, path, transf):
        self.stop()
        self._prepare_model(path)
        self.transform = tuple(transf)
        self.update()

    def update(self):
        self.stop()
        self._props_from_context()
        self._filter_model()
        self._create_batch()
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_VIEW')
        self._tag_redraw()
    
    def stop(self):
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
            self._tag_redraw()

