from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import Object
    from numpy.typing import NDArray

from functools import cached_property

import bpy

import numpy as np
from numpy import float64, ndarray

from .. import TYPES_NAME

import zlib, struct

def crc32_array(a: np.ndarray) -> int:
    ac = np.ascontiguousarray(a)
    mv = memoryview(ac.data).cast("B")
    return zlib.adler32(mv)

class SlicingObject():
    name: str
    parent: str
    object_type: str
    extruder: str
    modifiers: list[dict]
    mesh: NDArray[float64]

    def __init__(self, obj: Object, parent: str):
        if not bpy.context.scene: raise Exception('No scene currently open!')

        self.name = str(obj.name)
        self.object_type = getattr(obj, TYPES_NAME).object_type
        self.extruder = getattr(obj, TYPES_NAME).extruder
        self.modifiers = list(getattr(obj, TYPES_NAME).modifiers)
        self.parent = parent

        from ..functions.blender_funcs import objects_to_tris
        depsgraph = bpy.context.evaluated_depsgraph_get()
        scene_scale: float = bpy.context.scene.unit_settings.scale_length
        eval_objects = obj.evaluated_get(depsgraph)

        self.mesh = objects_to_tris([eval_objects], 1000 * scene_scale)

    def offset(self, offset: NDArray):
        self.mesh += offset

    @property
    def checksum(self):
        return crc32_array(self.mesh)

    @property
    def height(self) -> float:
        return self.mesh[:, :3, 2].max()

    @property
    def min_x(self) -> float:
        return self.mesh[:, :3, 0].min()

    @property
    def max_x(self) -> float:
        return self.mesh[:, :3, 0].max()

    @property
    def min_y(self) -> float:
        return self.mesh[:, :3, 1].min()

    @property
    def max_y(self) -> float:
        return self.mesh[:, :3, 1].max()

    @property
    def min_xy(self) -> NDArray:
        return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray:
        return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray:
        return (self.min_xy + self.max_xy) / 2.0

class SlicingCollection():
    name: str
    objects: list[SlicingObject]

    def __init__(self, objs, parent):
        self.objects = [SlicingObject(obj, parent) for obj in objs]
        self.objects = [obj for obj in self.objects if np.any(obj.mesh)]
        self.name = parent

    def offset(self, offset: NDArray):
        for so in self.objects: so.offset(offset)

    @property
    def checksum(self) -> int:
        return crc32_array(np.array([o.checksum for o in self.objects]))

    @property
    def height(self) -> float:
        height_all = [so.height for so in self.objects if np.any(so.mesh)]
        if not height_all: return 0
        return max(height_all)

    @property
    def meshes(self) -> list[NDArray[float]]:
        return [o.mesh for o in self.objects]

    @cached_property
    def mesh_lengths_ids(self) -> NDArray:
        return np.array([len(m) for m in self.meshes])

    @cached_property
    def mesh_start_ids(self) -> NDArray:
        lengths = self.mesh_lengths_ids
        return np.insert(np.cumsum(lengths)[:-1], 0, 0)

    @cached_property
    def mesh_end_ids(self) -> NDArray:
        starts = self.mesh_start_ids
        lengths = self.mesh_lengths_ids
        return starts + lengths - 1

    @cached_property
    def all_verts(self) -> NDArray:
        all_verts = np.vstack(self.meshes)[:, :3, :]
        return all_verts.reshape(-1, 3)

    @cached_property
    def unique_verts(self) -> tuple[np.ndarray, np.ndarray]:
        verts_list = []
        idxs = []
        offset = 0

        for mesh in self.meshes:
            verts = mesh[:, :3, :].reshape(-1, 3)

            void_dtype = np.dtype((np.void, verts.dtype.itemsize * verts.shape[1]))
            verts_void = verts.view(void_dtype).ravel()

            unique_voids, inv = np.unique(verts_void, return_inverse=True)

            unique_verts = unique_voids.view(verts.dtype).reshape(-1, 3)

            verts_list.append(unique_verts)
            idxs.append(inv.reshape(-1, 3) + offset)

            offset += unique_verts.shape[0]

        all_verts = np.concatenate(verts_list, axis=0)
        all_idxs  = np.vstack(idxs)
        return all_verts, all_idxs

    @property
    def min_x(self) -> float:
        min_x_all = [so.min_x for so in self.objects if np.any(so.mesh)]
        if not min_x_all: return 0
        return min(min_x_all)

    @property
    def max_x(self) -> float:
        max_x_all = [so.max_x for so in self.objects if np.any(so.mesh)]
        if not max_x_all: return 0
        return max(max_x_all)

    @property
    def min_y(self) -> float:
        min_y_all = [so.min_y for so in self.objects if np.any(so.mesh)]
        if not min_y_all: return 0
        return min(min_y_all)

    @property
    def max_y(self) -> float:
        max_y_all = [so.max_y for so in self.objects if np.any(so.mesh)]
        if not max_y_all: return 0
        return max(max_y_all)

    @property
    def min_xy(self) -> NDArray:
        return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray:
        return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray:
        return (self.min_xy + self.max_xy) / 2.0

class SlicingGroup():

    collections: dict[str, SlicingCollection]

    # Metadata
    wipe_tower_xy: NDArray
    wipe_tower_rotation_deg: float

    def __init__(self, objs, parents):
        self.collections = {}
        for k, parent in parents.items():
            self.collections[str(parent)] = SlicingCollection([obj for obj in objs if parents[obj.name] == parent], parent)
        
        self._extract_metadata(objs)
        pass

    def _extract_metadata(self, objs):
        import math
        depsgraph = bpy.context.evaluated_depsgraph_get()
        scale_tx = 1000. * bpy.context.scene.unit_settings.scale_length #type: ignore

        for obj in objs:
            eval_obj = obj.evaluated_get(depsgraph)
            if eval_obj.blendertoprusaslicer.object_type == 'WipeTower':
                self.wipe_tower_xy = np.array(eval_obj.location[0:2]) * scale_tx
                self.wipe_tower_rotation_deg = round(eval_obj.rotation_euler[2]*180/math.pi,5)
                break

    def offset(self, offset: NDArray):
        for k, so in self.collections.items(): so.offset(offset)
        self.wipe_tower_xy = self.wipe_tower_xy + offset[0:2]

    @property
    def checksum(self):
        buf = bytearray()
        for key, col in sorted(self.collections.items(), key=lambda kv: kv[0]):
            key_bytes = key.encode('utf-8')
            buf.extend(struct.pack(">I", len(key_bytes)))
            buf.extend(key_bytes)
            buf.extend(struct.pack(">I", col.checksum))

        buf.extend(struct.pack(">I", crc32_array(self.wipe_tower_xy)))
        buf.extend(struct.pack(">I", crc32_array(np.array(self.wipe_tower_rotation_deg))))

        return zlib.crc32(buf) & 0xFFFFFFFF

    @property
    def height(self):
        return max([coll.height for k, coll in self.collections.items()])

    @property
    def min_x(self) -> float:
        return min(so.min_x for k, so in self.collections.items())

    @property
    def max_x(self) -> float:
        return max(so.max_x for k, so in self.collections.items())

    @property
    def min_y(self) -> float:
        return min(so.min_y for k, so in self.collections.items())

    @property
    def max_y(self) -> float:
        return max(so.max_y for k, so in self.collections.items())

    @property
    def min_xy(self) -> NDArray:
        return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray:
        return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray:
        return (self.min_xy + self.max_xy) / 2.0