from __future__ import annotations

from typing import TYPE_CHECKING, Any

import bpy
import numpy as np
import gpu
import blf
from gpu_extras.batch import batch_for_shader

from ..infra.gcode import labels
from .. import TYPES_NAME

if TYPE_CHECKING:
    from gpu.types import GPUShader, GPUBatch
    from bpy.types import Object
    from numpy.typing import NDArray


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

color_map = np.array(
    [
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
    ],
    dtype=np.float32,
)

prop_to_id = {
    "gcode_perimeter": "Perimeter",
    "gcode_external_perimeter": "External perimeter",
    "gcode_overhang_perimeter": "Overhang perimeter",
    "gcode_internal_infill": "Internal infill",
    "gcode_solid_infill": "Solid infill",
    "gcode_top_solid_infill": "Top solid infill",
    "gcode_bridge_infill": "Bridge infill",
    "gcode_skirt_brim": "Skirt/Brim",
    "gcode_custom": "Custom",
    "gcode_support_material": "Support material",
    "gcode_support_material_interface": "Support material interface",
    "gcode_gap_fill": "Gap fill",
}

PROP_TO_FT_IDX = {prop: labels.index(name) for prop, name in prop_to_id.items()}

range_colors = np.vstack(
    (
        np.array((0.04, 0.17, 0.48, 1.0), dtype=np.float32),
        np.array((0.07, 0.35, 0.52, 1.0), dtype=np.float32),
        np.array((0.11, 0.53, 0.57, 1.0), dtype=np.float32),
        np.array((0.02, 0.84, 0.06, 1.0), dtype=np.float32),
        np.array((0.67, 0.95, 0.00, 1.0), dtype=np.float32),
        np.array((0.99, 0.98, 0.01, 1.0), dtype=np.float32),
        np.array((0.96, 0.81, 0.04, 1.0), dtype=np.float32),
        np.array((0.89, 0.53, 0.13, 1.0), dtype=np.float32),
        np.array((0.82, 0.41, 0.19, 1.0), dtype=np.float32),
        np.array((0.76, 0.32, 0.24, 1.0), dtype=np.float32),
        np.array((0.58, 0.15, 0.09, 1.0), dtype=np.float32),
    )
).astype(np.float32, copy=False)

legend_title_mapping = {
    "feature_type": "Feature Type",
    "height": "Height (mm)",
    "width": "Width (mm)",
    "fan_speed": "Fan speed (%)",
    "temperature": "Temperature (C)",
}


# -----------------------------------------------------------------------------
# Workspace settings (cached identifiers)
# -----------------------------------------------------------------------------

_WS_PROP_IDS: list[str] | None = None


def workspace_settings() -> dict[str, Any]:
    global _WS_PROP_IDS
    workspace = bpy.context.workspace
    ws_pg = getattr(workspace, TYPES_NAME)

    if _WS_PROP_IDS is None:
        _WS_PROP_IDS = [
            p.identifier
            for p in ws_pg.bl_rna.properties
            if p.identifier not in ("rna_type", "name")
        ]

    return {p: getattr(ws_pg, p) for p in _WS_PROP_IDS}


# -----------------------------------------------------------------------------
# Segment cache: precompute everything possible
# -----------------------------------------------------------------------------

class SegmentTrisCache:
    _transform: NDArray[np.float32]
    _scale: float

    _tris_points: NDArray[np.float32]        # (S*8, 3)
    _tris_by_seg: NDArray[np.int32]          # (S, 8, 3)
    _brightness: NDArray[np.float32]         # (S*8, 4)

    _colors_by_view: dict[str, NDArray[np.float32]]  # view -> (S*8,4)
    _legend_by_view: dict[str, dict]                   # view -> legend dict

    _extrusion_mask: NDArray[np.bool]       # (S,)
    _feature_masks: list[NDArray[np.bool]]  # per feature type index, (S,)
    _ft: NDArray[np.int32]                    # (S,)
    _z: NDArray[np.float32]                  # point-z array (len = mesh_data.length or points)

    S: int

    def __init__(self, path: str, transform: NDArray[np.float32], scale: float = 0.001):
        self.path = path
        self._transform = transform.astype(np.float32, copy=False)
        self._scale = float(scale)

        self._parse_gcode()
        self.S = int(self._mesh_data.seg_count)

        # immutable per-seg/pt fields cached
        self._ft = self._mesh_data.feature_type.astype(np.int32)
        self._extrusion_mask = (self._mesh_data.extrusion > 0)

        # z array (point-based in your existing logic)
        self._z = self._mesh_data.pos[:, 2].astype(np.float32, copy=False)

        # precompute feature masks (size based on max ft present)
        max_ft = int(np.max(self._ft)) if self.S else 0
        self._feature_masks = [(self._ft == i) for i in range(max_ft + 1)]

        # geometry once
        self._tris_points = self.__tris_points

        # per-segment triangle indices once
        base_tris: NDArray[np.int32] = np.array(
            [
                [0, 4, 1],
                [1, 4, 5],
                [1, 5, 2],
                [3, 7, 0],
                [2, 5, 6],
                [2, 6, 3],
                [3, 6, 7],
                [7, 4, 0],
            ],
            dtype=np.int32,
        )  # (8,3)
        seg_offsets: NDArray[np.int32] = (np.arange(self.S, dtype=np.int32) * 8)[:, None, None]  # (S,1,1)
        self._tris_by_seg = base_tris[None, :, :] + seg_offsets  # (S,8,3)

        # brightness mask once (S*8,4)
        self._brightness = self.__color_brightness_mask.astype(np.float32, copy=False)

        # colors & legends for all views once
        self._precompute_colors()

    def _parse_gcode(self) -> None:
        from ..infra.gcode import parse_gcode
        self._mesh_data = parse_gcode(self.path)

    # -----------------------------
    # Public data used by renderer
    # -----------------------------

    @property
    def points_pos(self) -> NDArray[np.float32]:
        return self._tris_points

    def colors_for_view(self, view: str) -> NDArray[np.float32]:
        return self._colors_by_view.get(view, self._brightness)

    def legend_for_view(self, view: str) -> dict:
        return self._legend_by_view.get(view, {})

    def tris_idx_for_seg_mask(self, seg_mask: "NDArray[np.bool_]") -> NDArray[np.int32]:
        if self.S == 0:
            return np.zeros((0, 3), dtype=np.int32)
        return self._tris_by_seg[seg_mask].reshape(-1, 3).astype(np.int32, copy=False)

    # -----------------------------
    # Masks computed cheaply per update
    # -----------------------------

    def display_mask_from_settings(self, settings: dict[str, Any]) -> "NDArray[np.bool_]":
        if self.S == 0:
            return np.zeros((0,), dtype=bool)
        mask = np.zeros((self.S,), dtype=bool)
        # OR together selected feature masks
        for prop, ft_idx in PROP_TO_FT_IDX.items():
            if settings.get(prop, False):
                if 0 <= ft_idx < len(self._feature_masks):
                    mask |= self._feature_masks[ft_idx]
                else:
                    # if ft_idx beyond current max_ft, it's never present anyway
                    pass
        return mask

    def height_mask_from_settings(self, settings: dict[str, Any]) -> NDArray[np.bool]:
        min_z: float = float(settings.get("gcode_preview_min_z", 0.))
        max_z: float = float(settings.get("gcode_preview_max_z", 1000.))
        z = self._z
        return (z > min_z) & (z < max_z)

    # -----------------------------
    # Precomputed internals
    # -----------------------------

    @property
    def __color_brightness_mask(self) -> NDArray[np.float32]:
        # per-segment 8-vertex brightness pattern
        arr1: NDArray[np.float32] = np.array([1.00, 0.75, 0.50, 0.75, 1.00, 0.75, 0.50, 0.75], dtype=np.float32)
        rgba: NDArray[np.float32] = np.array([1, 1, 1, 0], dtype=np.float32)
        result: NDArray[np.float32] = arr1[:, None] * rgba
        result[:, 3] = 1.0
        return np.tile(result, (int(self.S), 1))

    @staticmethod
    def interp(attr: NDArray[np.float32], colors: NDArray[np.float32]) -> NDArray[np.float32]:
        a: NDArray[np.float32] = np.clip(attr, 0.0, 1.0)
        x: NDArray[np.float32] = a * (len(colors) - 1)
        idx: NDArray[np.int32] = np.floor(x).astype(np.int32)
        idx = np.minimum(idx, len(colors) - 2)
        frac: NDArray[np.float32] = (x - idx)[..., None].astype(np.float32, copy=False)
        c0: NDArray[np.float32] = colors[idx]
        c1: NDArray[np.float32] = colors[idx + 1]
        return ((1.0 - frac) * c0 + frac * c1).astype(np.float32, copy=False)

    @staticmethod
    def generate_legend(colors: NDArray[np.float32], lo: float | None = None, hi: float | None = None) -> dict:
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

        # preserve ordering but avoid duplicate keys
        out: dict = {}
        for k, c in zip(keys, colors):
            if k not in out:
                out[k] = c
        return out

    def _expand_seg_rgba_to_verts(self, seg_rgba: NDArray[np.float32]) -> NDArray[np.float32]:
        # seg_rgba: (S,4) -> (S*8,4), multiplied by brightness
        out = np.empty((self.S * 8, 4), dtype=np.float32)
        out.reshape(self.S, 8, 4)[:] = seg_rgba[:, None, :].astype(np.float32, copy=False)
        np.multiply(out, self._brightness, out=out)
        return out

    def _precompute_colors(self) -> None:
        self._colors_by_view = {}
        self._legend_by_view = {}

        if self.S == 0:
            self._colors_by_view["feature_type"] = np.zeros((0, 4), dtype=np.float32)
            self._legend_by_view["feature_type"] = {}
            for v in ("height", "width", "temperature", "fan_speed"):
                self._colors_by_view[v] = np.zeros((0, 4), dtype=np.float32)
                self._legend_by_view[v] = {}
            return

        ft = self._ft

        # feature_type
        seg_rgba = color_map[ft].astype(np.float32, copy=False)
        self._colors_by_view["feature_type"] = self._expand_seg_rgba_to_verts(seg_rgba)
        # Keep your previous legend mapping semantics (reverse labels/colors)
        self._legend_by_view["feature_type"] = {
            l: color_map[::-1][i] for i, l in enumerate(labels[::-1])
        }

        # numeric views
        valid = (ft != 12)  # exclude gap fill from min/max
        for view in ("height", "width", "temperature", "fan_speed"):
            attr = getattr(self._mesh_data, view)

            max_attr = float(np.max(attr[valid])) if np.any(valid) else float(np.max(attr))
            if view == "fan_speed":
                min_attr = 0.0
            else:
                min_attr = float(np.min(attr[valid])) if np.any(valid) else float(np.min(attr))

            rng = max_attr - min_attr
            if rng == 0.0:
                mapped = np.zeros_like(attr, dtype=np.float32)
            else:
                mapped = ((attr - min_attr) / rng).astype(np.float32, copy=False)

            seg_rgba = self.interp(mapped, range_colors).astype(np.float32, copy=False)
            self._colors_by_view[view] = self._expand_seg_rgba_to_verts(seg_rgba)
            self._legend_by_view[view] = self.generate_legend(range_colors, min_attr, max_attr)

    @property
    def __tris_points(self) -> NDArray[np.float32]:
        # Compute the segment vectors and directions
        p1 = self._mesh_data.pos[self._mesh_data.pt_id_of_seg[:, 0]].astype(np.float32, copy=False) + self._transform
        p2 = self._mesh_data.pos[self._mesh_data.pt_id_of_seg[:, 1]].astype(np.float32, copy=False) + self._transform
        width = self._mesh_data.width[self._mesh_data.pt_id_of_seg[:, 0]].astype(np.float32, copy=False)
        height = self._mesh_data.height[self._mesh_data.pt_id_of_seg[:, 0]].astype(np.float32, copy=False)

        if len(p1) == 0:
            return np.zeros((0, 3), dtype=np.float32)

        directions = (p2 - p1).astype(np.float32, copy=False)
        direction_lengths = np.linalg.norm(directions, axis=1).astype(np.float32, copy=False)

        # Avoid NaNs for zero-length segments
        safe = direction_lengths > 1e-12
        direction_unit = np.zeros_like(directions, dtype=np.float32)
        direction_unit[safe] = directions[safe] / direction_lengths[safe, None]

        perpendicular: NDArray[np.float32] = np.column_stack(
            [-direction_unit[:, 1], direction_unit[:, 0], np.zeros(len(direction_unit), dtype=np.float32)]
        ).astype(np.float32, copy=False)

        z_vec: NDArray[np.float32] = np.array([0, 0, 1], dtype=np.float32)

        off1 = z_vec * (height[:, None] * 0.5)
        off2 = -perpendicular * (width[:, None] * 0.5)
        off3 = -z_vec * (height[:, None] * 0.5)
        off4 = perpendicular * (width[:, None] * 0.5)

        p1_block = np.stack((p1 + off1, p1 + off2, p1 + off3, p1 + off4), axis=1) * self._scale
        p2_block = np.stack((p2 + off1, p2 + off2, p2 + off3, p2 + off4), axis=1) * self._scale

        points = np.concatenate((p1_block, p2_block), axis=1).reshape(-1, 3)
        return points.astype(np.float32, copy=False)

class GcodeDraw:
    shader: GPUShader = gpu.shader.from_builtin("SMOOTH_COLOR")

    # batches: [gcode_batch, plate_batch]
    batch: list[GPUBatch | None] = []
    enabled: bool = False

    hidden_objects: list[Object] = []

    _draw_handler = None
    _legend_draw_handler = None

    gcode: SegmentTrisCache | None = None
    _preview_data: dict | None = None

    # cached state to avoid rebuilding when unchanged
    _last_key: tuple | None = None
    _last_view: str | None = None
    _last_seg_mask: NDArray[np.bool] | None = None

    # cached plate batch and its key
    _plate_batch: GPUBatch | None = None
    _plate_key: tuple | None = None

    def _tris_batch(self, shader: GPUShader, pos: NDArray[np.float32], color: NDArray[np.float32], tris_idx: NDArray[np.int32]) -> GPUBatch | None:
        if len(tris_idx) == 0 or len(pos) == 0:
            return None
        return batch_for_shader(
            shader,
            type="TRIS",
            content={
                "pos": pos,
                "color": color,
            }, #type: ignore
            indices=tris_idx,
        )

    def _preview_plate_data(self, scale: float = 0.001) -> dict[str, Any]:
        pd = self._preview_data
        assert pd

        bed = (
            np.array(
                [
                    (-1, -1, 0),
                    (1, -1, 0),
                    (-1, 1, 0),
                    (1, 1, 0),
                ],
                dtype=np.float32,
            )
            * 0.5
            * pd["bed_size"]
            + pd["transform"]
            + pd["bed_center"]
        )

        bed_color = np.vstack([(0.05, 0.05, 0.05, 1.0)] * 4).astype(np.float32, copy=False)
        bed_tris = np.array(((0, 2, 1), (1, 2, 3)), dtype=np.int32)

        return {
            "pos": (bed * scale).astype(np.float32, copy=False),
            "color": bed_color,
            "tris_idx": bed_tris,
        }

    def _plate_settings_key(self) -> tuple:
        pd = self._preview_data
        assert pd

        return (
            tuple(np.asarray(pd["bed_size"]).tolist()),
            tuple(np.asarray(pd["transform"]).tolist()),
            tuple(np.asarray(pd["bed_center"]).tolist()),
            float(pd["scene_scale"]),
        )

    def _ensure_plate_batch(self) -> None:
        pd = self._preview_data
        assert pd

        key = self._plate_settings_key()
        if self._plate_key == key and self._plate_batch is not None:
            return

        scale = 0.001 / float(pd["scene_scale"])
        plate = self._preview_plate_data(scale=scale)
        self._plate_batch = self._tris_batch(self.shader, plate["pos"], plate["color"], plate["tris_idx"])
        self._plate_key = key

    def _tag_redraw(self) -> None:
        if not bpy.context.screen:
            return
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
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
    def _add_text(text: str = "placeholder", x: int = 0, y: int = 0, rgba=(1, 1, 1, 1), size: float = 25.0) -> None:
        blf.position(0, x, y, 0)
        blf.size(0, size)
        r, g, b, a = rgba
        blf.color(0, float(r), float(g), float(b), float(a))
        blf.draw(0, text)

    def _legend_draw(self, _0, _1) -> None:
        if not self.gcode:
            return

        settings = workspace_settings()
        view = str(settings.get("gcode_preview_view", "feature_type"))

        legend = self.gcode.legend_for_view(view)
        title_id = view

        i = 0
        for i, (k, v) in enumerate(legend.items()):
            self._add_text("■", 15, 15 + i * 40, v)
            kk = k * 100 if title_id == "fan_speed" else k
            if isinstance(kk, float):
                text = str(round(kk, 2))
            else:
                text = str(kk)
            self._add_text(text, 45, 15 + i * 40)

        i += 1
        self._add_text(legend_title_mapping.get(title_id, title_id), 15, 15 + i * 40)

    def _gpu_undraw(self) -> None:
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, "WINDOW")
            self._draw_handler = None
            self._tag_redraw()
        if self._legend_draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._legend_draw_handler, "WINDOW")
            self._legend_draw_handler = None
            self._tag_redraw()

    def _show_objects(self) -> None:
        for obj in self.hidden_objects:
            try:
                obj.hide_set(False)
            except Exception as e:
                print(f"Could not show object {obj!r}: {e}")

    def _hide_objects(self) -> None:
        for obj in self.hidden_objects:
            try:
                obj.hide_set(True)
            except Exception as e:
                print(f"Could not hide object {obj!r}: {e}")

    def draw(self, preview_data: dict, objects: list["Object"] = []) -> None:
        self.enabled = True
        self.hidden_objects = objects
        self._preview_data = preview_data

        self.gcode = SegmentTrisCache(
            self._preview_data["gcode_path"],
            self._preview_data["transform"],
            0.001 / float(self._preview_data["scene_scale"]),
        )

        # reset caches to force initial build
        self._last_key = None
        self._last_view = None
        self._last_seg_mask = None

        self.update()

    def _settings_key(self, settings: dict[str, Any]) -> tuple:
        view = str(settings.get("gcode_preview_view", "feature_type"))
        zmin = float(settings.get("gcode_preview_min_z", -1e9))
        zmax = float(settings.get("gcode_preview_max_z", 1e9))
        toggles = tuple(bool(settings.get(p, False)) for p in prop_to_id.keys())
        return (view, zmin, zmax, toggles)

    from ..utils.profiling import profiler

    @profiler
    def update(self) -> None:
        if not (self.gcode and self.enabled):
            return

        settings = workspace_settings()
        key = self._settings_key(settings)

        # If absolutely nothing changed, avoid rebuild
        if self._last_key == key:
            return

        view, zmin, zmax, _toggles = key

        # Ensure plate batch is up-to-date (cheap key check)
        self._ensure_plate_batch()

        # Build seg mask cheaply
        extrusion = self.gcode._extrusion_mask
        display = self.gcode.display_mask_from_settings(settings)
        height = self.gcode.height_mask_from_settings(settings)

        # NOTE: your height mask is point-based; original code ANDs it with seg masks.
        # This assumes mesh_data.pos is segment-aligned in length. Preserving original behavior.
        seg_mask = extrusion & display & height

        # Colors: already precomputed per view
        colors = self.gcode.colors_for_view(view)

        tris_idx = self.gcode.tris_idx_for_seg_mask(seg_mask)

        # rebuild only the gcode batch; plate batch reused
        gcode_batch = self._tris_batch(self.shader, self.gcode.points_pos, colors, tris_idx)

        self.batch = [gcode_batch, self._plate_batch]

        # handlers: only re-add if not present (but you currently remove/add each update)
        # Keeping your behavior but only when key changes.
        self._gpu_undraw()
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._gpu_draw, (None, None), "WINDOW", "POST_VIEW")
        self._legend_draw_handler = bpy.types.SpaceView3D.draw_handler_add(self._legend_draw, (None, None), "WINDOW", "POST_PIXEL")

        self._hide_objects()
        self._tag_redraw()

        self._last_key = key

    def stop(self) -> None:
        self.enabled = False
        self._gpu_undraw()
        self._show_objects()
        self.hidden_objects = []

        self.gcode = None
        self._preview_data = None
        self.batch = []

        self._last_key = None
        self._last_view = None
        self._last_seg_mask = None

        self._plate_batch = None
        self._plate_key = None

drawer: GcodeDraw = GcodeDraw()
