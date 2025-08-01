from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gpu.types import GPUShader, GPUBatch
    from bpy.types import Object
    from numpy.typing import NDArray

import bpy
import numpy as np
import gpu
import blf
from gpu_extras.batch import batch_for_shader

from .draw_gcode_funcs.parse_gcode import labels

from .. import TYPES_NAME

color_map = np.array([
    [1.000, 0.902, 0.302, 1.000],  # Perimeter
    [1.000, 0.490, 0.220, 1.000],  # External perimeter
    [0.122, 0.122, 1.000, 1.000],  # Overhang perimeter
    [0.690, 0.188, 0.161, 1.000],  # Internal infill
    [0.588, 0.329, 0.800, 1.000],  # Solid infill
    [0.941, 0.251, 0.251, 1.000],  # Top solid infill
    [0.302, 0.502, 0.729, 1.000],  # Bridge infill
    [0.000, 0.529, 0.431, 1.000],  # Skirt/Brim
    [0.369, 0.820, 0.580, 1.000],  # Custom
    [0.000, 1.000, 0.000, 1.000],  # Support material
    [0.000, 0.500, 0.000, 1.000],  # Support material interface
    [1.000, 1.000, 1.000, 1.000],  # Gap fill
], dtype=float)

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

range_colors = np.vstack((
    np.array((0.04, 0.17, 0.48, 1.0)),
    np.array((0.07, 0.35, 0.52, 1.0)),
    np.array((0.11, 0.53, 0.57, 1.0)),
    np.array((0.02, 0.84, 0.06, 1.0)),
    np.array((0.67, 0.95, 0.00, 1.0)),
    np.array((0.99, 0.98, 0.01, 1.0)),
    np.array((0.96, 0.81, 0.04, 1.0)),
    np.array((0.89, 0.53, 0.13, 1.0)),
    np.array((0.82, 0.41, 0.19, 1.0)),
    np.array((0.76, 0.32, 0.24, 1.0)),
    np.array((0.58, 0.15, 0.09, 1.0)),
))

legend_title_mapping = {
    'feature_type': 'Feature Type',
    'height': 'Height (mm)',
    'width': 'Width (mm)',
    'fan_speed': 'Fan speed (%)',
    'temperature': 'Temperature (C)',
}

def workspace_settings():
    workspace = bpy.context.workspace
    ws_pg = getattr(workspace, TYPES_NAME)
    props = [p.identifier for p in ws_pg.bl_rna.properties if p.identifier not in ['rna_type', 'name']]
    return {p: getattr(ws_pg, p) for p in props}

class SegmentTrisCache:
    _transform: NDArray
    _scale: float = 0.001

    def __init__(self, path, transform, scale=0.001):
        self.path = path
        self._transform = transform
        self._scale = scale

        self._parse_gcode()

    def _parse_gcode(self):
        from .draw_gcode_funcs.parse_gcode import parse_gcode
        self._mesh_data = parse_gcode(self.path)
            
    @property
    def batch_data(self) -> dict[str, [dict[str, NDArray], NDArray]]:
        return {
            'content': {
                "pos": self.tris_points,
                "color": self.points_colors,
            },
            'tris_idx': self.tris_idx
        }

    @property
    def color_brightness_mask(self):
        arr1 = np.array([1.00, 0.75, 0.50, 0.75, 1.00, 0.75, 0.50, 0.75])
        rgba = np.array([1, 1, 1, 0])
        result = arr1[:, None] * rgba
        result[:, 3] = 1   
        return np.tile(result, (int(self._mesh_data.seg_count), 1))

    @staticmethod
    def interp(attr, colors):
        a = np.clip(attr, 0.0, 1.0)

        x = a * (len(colors) - 1)

        idx = np.floor(x).astype(int)
        idx = np.minimum(idx, len(colors) - 2)

        frac = (x - idx)[..., None]

        C_start = colors[idx]
        C_end   = colors[idx + 1]

        return (1 - frac) * C_start + frac * C_end

    @staticmethod
    def generate_legend(colors, lo=None, hi=None):
        n = len(colors)
        if n == 0:
            return {}
        if n == 1:
            key = lo if lo is not None else 0.0
            return {key: colors[0]}

        if lo is None or hi is None:
            keys = [i / (n - 1) for i in range(n)]
        else:
            step = (hi - lo) / (n - 1)
            keys = [lo + step * i for i in range(n)]

        return {keys[i]: colors[i] for i in range(len(set(keys)))}

    @property
    def points_colors(self):
        settings = workspace_settings()
        view = settings['gcode_preview_view']

        attr = getattr(self._mesh_data, view)

        if view in ['feature_type']:
            attr_col = color_map[attr]
            self.legend = {l: color_map[::-1][i] for i, l in enumerate(labels[::-1])}
            pass

        elif view in ['height', 'width', 'temperature', 'fan_speed']:
            max_attr = attr[self._mesh_data.feature_type != 12].max()
            if view == 'fan_speed':
                min_attr = 0
                range_attr = attr.max() - (attr).min()
            else:
                min_attr = attr[self._mesh_data.feature_type != 12].min()
            
            range_attr = max_attr - min_attr

            attr_mapped = (attr - min_attr) / (range_attr if range_attr else 1)
            attr_col = self.interp(attr_mapped, range_colors)

            self.legend = self.generate_legend(range_colors, min_attr, max_attr)

        else:
            return self.color_brightness_mask

        tiled_attr = np.repeat(attr_col, 8, axis=0)   

        return self.color_brightness_mask * tiled_attr

    @property
    def extrusion_mask(self):
        mask = self._mesh_data.extrusion > 0
        return mask

    @property
    def display_mask(self):
        mask = np.full(self._mesh_data.length, False, dtype=bool)
        settings = workspace_settings()
        for prop in prop_to_id:
            if settings[prop]:
                mask += self._mesh_data.feature_type == labels.index(prop_to_id[prop])
        return mask

    @property
    def height_mask(self):
        settings = workspace_settings()
        z = self._mesh_data.pos[:,2]
        mask = (z > settings['gcode_preview_min_z']) & (z < settings['gcode_preview_max_z'])
        return mask

    @property
    def tris_idx(self):
        base_tris: NDArray[int] = np.array([[0,4,1],[1,4,5],[1,5,2],[3,7,0],
                            [2,5,6],[2,6,3],[3,6,7],[7,4,0]], dtype=int)

        tris_tiled: NDArray[int] = np.tile(base_tris, (self._mesh_data.seg_count, 1))
        offsets: NDArray[int] = np.repeat(np.arange(self._mesh_data.seg_count) * 8, base_tris.shape[0])

        tris: NDArray[int] = tris_tiled + offsets[:, np.newaxis]

        masks = self.extrusion_mask * self.display_mask * self.height_mask
        masks =  np.repeat(masks, 8, axis=0)
        tris = tris[masks]

        return tris

    @property
    def tris_points(self):
        p = {}

        # Compute the segment vectors and directions
        p['p1'] = self._mesh_data.pos[self._mesh_data.pt_id_of_seg[:, 0]] + self._transform
        p['p2'] = self._mesh_data.pos[self._mesh_data.pt_id_of_seg[:, 1]] + self._transform
        p['width'] = self._mesh_data.width[self._mesh_data.pt_id_of_seg[:, 0]]
        p['height'] = self._mesh_data.height[self._mesh_data.pt_id_of_seg[:, 0]]

        if len(p['p1']) == 0:
            return np.zeros((0, 3), dtype=np.float32)

        directions = p['p2'] - p['p1']
        direction_lengths = np.linalg.norm(directions, axis=1)

        # Normalize directions (unit vectors)
        # mask_length = direction_lengths != 0
        # p = { k: v[mask_length] for k, v in p.items() }
        # direction_unit = directions[mask_length] / direction_lengths[mask_length][:, None]
        direction_unit = directions / direction_lengths[:, None]

        # Compute perpendiculars
        perpendicular = np.column_stack([-direction_unit[:, 1], direction_unit[:, 0], np.zeros(len(direction_unit))])

        # Create z-direction vector
        z = np.array([0, 0, 1])

        off1 =  z * p['height'][:, np.newaxis]/2
        off2 = -perpendicular * p['width'][:, np.newaxis]/2
        off3 = -z * p['height'][:, np.newaxis]/2
        off4 =  perpendicular * p['width'][:, np.newaxis]/2

        # build 8 pts per p1/p2 pair
        p1_block = np.stack((p['p1'] + off1, p['p1'] + off2, p['p1'] + off3, p['p1'] + off4), axis=1) * self._scale
        p2_block = np.stack((p['p2'] + off1, p['p2'] + off2, p['p2'] + off3, p['p2'] + off4), axis=1) * self._scale

        points = np.concatenate((p1_block, p2_block), axis=1).reshape(-1, 3) # (n,8,3) → (8n,3)

        return points

class GcodeDraw():
    shader: GPUShader = gpu.shader.from_builtin('SMOOTH_COLOR')
    batch: list[GPUBatch | None] = []
    enabled: bool = False

    hidden_objects: list[Object] = []
    max_z: float = 0

    _draw_handler = None
    _legend_draw_handler = None

    gcode: SegmentTrisCache | None = None
    filters = {}

    def _tris_batch(self, shader, content, tris_idx) -> GPUBatch | None:
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

    def _prepare_batches(self) -> None:
        self.batch = []

        if self.gcode: self.batch += [self._tris_batch(self.shader, **self.gcode.batch_data)]
        self.batch += [self._tris_batch(self.shader, **self._preview_plate(scale = 0.001 / self._preview_data['scene_scale']))]

    def _tag_redraw(self) -> None:
        if not bpy.context.screen: return
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    
    def _gpu_draw(self, _0, _1) -> None:
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.front_facing_set(True)
        gpu.state.face_culling_set("BACK")

        for b in self.batch:
            if b:
                b.draw(self.shader)

        gpu.state.face_culling_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.front_facing_set(False)

    @staticmethod
    def _add_text(text = "placeholder", x=0, y=0, rgba=(1,1,1,1), size = 25.0):
        blf.position(0, x, y, 0)
        blf.size(0, size)
        r, g, b, a = rgba
        blf.color(0, r, g, b, a)
        blf.draw(0, text)

    def _legend_draw(self, _0, _1):
        if not self.gcode: return

        settings = workspace_settings()
        title_id = settings['gcode_preview_view']
        i=0
        for i, (k, v) in enumerate(self.gcode.legend.items()):
            self._add_text(f"■", 15, 15+i*40, v)
            if title_id == 'fan_speed': k=k*100
            if isinstance(k, float): text = str(round(k, 2))
            else: text=k
            self._add_text(text, 45, 15+i*40)
        i+=1
        self._add_text(legend_title_mapping[title_id], 15, 15+i*40)

    def _gpu_undraw(self):
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
            self._tag_redraw()
        if self._legend_draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._legend_draw_handler, 'WINDOW')
            self._legend_draw_handler = None
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

    def draw(self, preview_data, objects = [], ):
        self.enabled = True
        self.hidden_objects = objects
        self._preview_data = preview_data
        self.gcode = SegmentTrisCache(
            self._preview_data['gcode_path'],
            self._preview_data['transform'],
            0.001 / self._preview_data['scene_scale']
        )
        self.update()
        pass

    def update(self):
        if self.gcode and self.enabled:
            self._gpu_undraw()
            self._prepare_batches()
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._gpu_draw, (None, None), 'WINDOW', 'POST_VIEW')
            self._legend_draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._legend_draw, (None, None), 'WINDOW', 'POST_PIXEL')
            self._hide_objects()
            self._tag_redraw()
    
    def stop(self):
        self.enabled = False
        self._gpu_undraw()
        self._show_objects()
        self.hidden_objects = []

drawer: GcodeDraw = GcodeDraw()