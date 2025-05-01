from numpy.typing import NDArray
from typing import Any

import bpy
import numpy as np
import gpu
import re
from gpu.types import GPUShader, GPUBatch
from gpu_extras.batch import batch_for_shader

from ..functions.basic_functions import profiler

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

def gcode_to_segments(path) -> tuple[
        dict[str, [np.ndarray, np.ndarray]],
        np.ndarray
    ]:

    # Initialize empty arrays for positions and colors
    points_pos = []
    points_color = []
    points_width = []
    points_height = []
    segments = []

    with open(path, 'r') as f:
        prev_pt = None
        seg_i = 0

        pos_append = points_pos.append
        col_append = points_color.append
        width_append = points_width.append
        height_append = points_height.append
        seg_append = segments.append
        
        starts     = str.startswith
        split      = str.split

        x = y = z = e = 0.0
        line_width = 0
        line_height = 0
        line_color = colors['Custom']
        for raw in f:
            if not raw:
                continue

            if raw[0] == ';':
                if starts(raw, ';TYPE:'):
                    line_type = raw[6:].strip() or 'Custom'
                    line_color = colors[line_type]
                    continue

                if starts(raw, ';WIDTH:'):
                    line_width: float = float(raw[7:].strip())
                    continue

                if starts(raw, ';HEIGHT:'):
                    line_height: float = float(raw[8:].strip())
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
                col_append(line_color)
                width_append(line_width)
                height_append(line_height)

                if prev_pt is not None and e > 0:
                    seg_append((seg_i - 1, seg_i))

                seg_i += 1
                prev_pt = pt

    points = {
        'pos': np.array(points_pos),
        'color': np.array(points_color),
        'width': np.array(points_width),
        'height': np.array(points_height),
    }
    segments = np.array(segments)

    return points, segments

import numpy as np

def segments_to_tris(points: dict[str, list[Any]], idx: np.ndarray, transform, width: float, height: float, scale: float = 0.001) -> tuple[dict[str, NDArray[float] | None], NDArray[int]]:
    # Initialize lists
    points_tris: dict[str, NDArray | None] = {'pos': None, 'color': None}

    # Extract position and color arrays once
    positions = points['pos'] + transform

    # Compute the segment vectors and directions
    p1 = positions[idx[:, 0]]
    p2 = positions[idx[:, 1]]
    c = points['color'][idx[:, 0]]
    w = points['width'][idx[:, 0]]
    h = points['height'][idx[:, 0]]

    # Remove zero length segments
    mask = np.any(p2 - p1 != np.array([0,0,0]), -1)
    p1 = p1[mask]
    p2 = p2[mask]
    c = c[mask]
    w = w[mask]
    h = h[mask]

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

class SegmentDraw():
    shader: GPUShader = gpu.shader.from_builtin('SMOOTH_COLOR')
    batch: GPUBatch | None = None
    _draw_handler = None

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

    @profiler
    def _create_batch(self, path, transform):
        points, idx = gcode_to_segments(path)
        points_tris, tris = segments_to_tris(points, idx, transform, 0.4, 0.2)
        self._tris_batch(self.shader, points_tris, tris_idx=tris)

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

    def draw(self, path, transform):
        self.stop()
        self._create_batch(path, transform)
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_VIEW')
        self._tag_redraw()
    
    def stop(self):
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
            self._tag_redraw()

