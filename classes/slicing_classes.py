from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import Object
    from numpy.typing import NDArray

from functools import cached_property

import bpy

import numpy as np
from numpy import float64

from .. import TYPES_NAME

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
        self.name = parent

    def offset(self, offset: NDArray):
        for so in self.objects: so.offset(offset)

    @property
    def height(self) -> float:
        return max([so.height for so in self.objects])

    @property
    def meshes(self) -> list[NDArray[float64]]:
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
        all_tris = np.vstack(self.meshes)[:, :3, :]
        return all_tris.reshape(-1, 3)

    @cached_property
    def unique_verts(self) -> NDArray:
        uniques = []
        for mesh in self.meshes:
            verts = mesh[:, :3, :].reshape(-1, 3)
            verts = np.round(verts, decimals=4)
            u, _ = np.unique(verts, axis=0, return_inverse=True)
            uniques.append(u)
        return np.vstack(uniques)

    @cached_property
    def tris_idx(self) -> NDArray:
        idxs = []
        offset = 0
        for mesh in self.meshes:
            verts = np.round(mesh[:, :3, :].reshape(-1, 3), decimals=4)
            _, inv = np.unique(verts, axis=0, return_inverse=True)
            idxs.append(inv.reshape(-1, 3) + offset)
            offset += np.unique(verts, axis=0).shape[0]
        return np.vstack(idxs)

    @property
    def min_x(self) -> float:
        return min(so.min_x for so in self.objects)

    @property
    def max_x(self) -> float:
        return max(so.max_x for so in self.objects)

    @property
    def min_y(self) -> float:
        return min(so.min_y for so in self.objects)

    @property
    def max_y(self) -> float:
        return max(so.max_y for so in self.objects)

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

    def __init__(self, objs, parents):
        self.collections = {}
        for k, parent in parents.items():
            self.collections[str(parent)] = SlicingCollection([obj for obj in objs if parents[obj.name] == parent], parent)
        pass

    def offset(self, offset: NDArray):
        for k, so in self.collections.items(): so.offset(offset)

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