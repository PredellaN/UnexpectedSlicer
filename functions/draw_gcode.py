from numpy._typing._array_like import NDArray
from numpy._typing._array_like import NDArray
from numpy._typing._array_like import NDArray


from numpy._typing._array_like import NDArray
from numpy._typing._array_like import NDArray
from numpy._typing._array_like import NDArray
from numpy import dtype, float64, ndarray, signedinteger
from numpy._typing._array_like import NDArray
from numpy._typing._array_like import NDArray
from numpy._typing._array_like import NDArray

from typing import Any

from gpu.types import GPUShader, GPUBatch

import bpy
import numpy as np
import gpu
import re
from gpu_extras.batch import batch_for_shader

colors: dict[str, tuple[float, float, float, float]] = {
    'Perimeter': (1.0, 0.902, 0.302, 1.0),
    'External perimeter': (1.0, 0.49, 0.22, 1.0),
    'Overhang perimeter': (0.122, 0.122, 1.0, 1.0),
    'Internal infill': (0.69, 0.188, 0.161, 1.0),
    'Solid infill': (0.588, 0.329, 0.8, 1.0),
    'Top solid infill': (0.941, 0.251, 0.251, 1.0),
    'Bridge infill': (0.302, 0.502, 0.729, 1.0),
    'Skirt/Brim': (0.0, 0.529, 0.431, 1.0),
    'Custom': (0.369, 0.82, 0.58, 1.0)
}

def gcode_to_numpy(path): ### WIP

    def np_str_to_float(arr):
        idx = arr[:, 0].astype(int)
        arr[arr == ''] = '0.0'
        cx = arr[:, 2:5].astype(float)
        return np.hstack((idx[:, np.newaxis], cx))

    def get_gcode_lines(path):
        with open(path, 'r') as f:
            txt = f.read()

        return re.findall(r'(\S+)(?:\s+X(-?\d*\.?\d+))?(?:\s+Y(-?\d*\.?\d+))?(?:\s+Z(-?\d*\.?\d+))?(?:\s+E(-?\d*\.?\d+))?.*?\n', txt)

    return None

def gcode_to_segments(path) -> tuple[
        dict[str, [np.ndarray, np.ndarray]],
        np.ndarray
    ]:

    # Initialize empty arrays for positions and colors
    points_pos = []
    points_color = []
    segments = []
    
    # Regular expressions for matching G1 commands and type changes
    type_change_pattern = re.compile(r';TYPE:(.+)$')
    extrusion_pattern = re.compile(r'G1(?:\s+X(-?\d*\.?\d+))?(?:\s+Y(-?\d*\.?\d+))?(?:\s+Z(-?\d*\.?\d+))?(?:\s+E(-?\d*\.?\d+))?')

    # Read G-code file
    with open(path, 'r') as file:
        previous_point = None
        segment_index = 0
        current_point = np.zeros(3)  # Default start position (X, Y, Z)
        line_colors = {}  # Store colors for each line type

        for line in file:
            if match_type_change := type_change_pattern.search(line):
                line_type = match_type_change.group(1) if match_type_change.group(1) else 'Custom'
                line_colors[line_type] = colors[line_type]  # Generate color for each type (RGBA)

            if match_extrusion := extrusion_pattern.search(line):
                # Extract coordinates or use current position if missing
                x = float(match_extrusion.group(1)) if match_extrusion.group(1) else current_point[0]
                y = float(match_extrusion.group(2)) if match_extrusion.group(2) else current_point[1]
                z = float(match_extrusion.group(3)) if match_extrusion.group(3) else current_point[2]
                e = float(match_extrusion.group(4)) if match_extrusion.group(4) else 0.0

                # Update current position
                current_point = np.array([x, y, z])

                # Store position and associated color
                points_pos.append(current_point)
                points_color.append(line_colors.get(line_type, np.zeros(4)))  # Default color if not set

                # If extrusion occurs, create segment
                if previous_point is not None and e != 0:
                    segments.append((segment_index - 1, segment_index))

                segment_index += 1
                previous_point = current_point

    # Convert lists to numpy arrays for more efficient operations
    points_pos = np.array(points_pos)
    points_color = np.array(points_color)

    # Convert segments to numpy array for faster processing
    segments = np.array(segments)

    # Return the results as a tuple
    return {'pos': points_pos, 'color': points_color}, segments

import numpy as np

def segments_to_tris(points: dict[str, list[Any]], idx: np.ndarray, transform, width: float, height: float, scale: float = 0.001) -> tuple[dict[str, NDArray[float] | None], NDArray[int]]:
    # Initialize lists
    points_tris: dict[str, NDArray | None] = {'pos': None, 'color': None}

    # Extract position and color arrays once
    positions = np.array(points['pos']) + transform
    col = np.array(points['color'])

    # Compute the segment vectors and directions
    p1 = positions[idx[:, 0]]
    p2 = positions[idx[:, 1]]
    c = col[idx[:, 0]]

    # Remove zero length segments
    mask = np.any(p2 - p1 != np.array([0,0,0]), -1)
    p1 = p1[mask]
    p2 = p2[mask]
    c = c[mask]

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

    # Calculate half width and height
    half_width = width / 2
    half_height = height / 2

    off1 =  z * half_height
    off2 = -perpendicular * half_width
    off3 = -z * half_height
    off4 =  perpendicular * half_width

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

    def _create_batch(self, path, transform):
        points, idx = gcode_to_segments(path)
        points_tris, tris = segments_to_tris(points, idx, transform, 0.4, 0.2)
        self.batch = batch_for_shader(self.shader, 'TRIS', {'pos': points_tris['pos'].tolist(), 'color': points_tris['color'].tolist()}, indices=tris.tolist())

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
        gpu.state.face_culling_set('NONE')
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