from __future__ import annotations

import bpy
from bpy.types import Object, Mesh

import zlib, struct
from functools import cached_property

import numpy as np
from numpy import dtype, float64
from numpy.typing import NDArray

from typing import Any

from ..core.geometry import crc32_array
from ..infra.blender_bridge import get_all_children

from .. import TYPES_NAME

class SlicingObject():
    name: str
    parent: str
    object_type: str
    extruder: str
    modifiers: list[dict]
    mesh: NDArray[float64]

    def __init__(self, obj: Object, parent: str) -> None:
        if not bpy.context.scene: raise Exception('No scene currently open!')

        self.name = str(obj.name)
        self.object_type = getattr(obj, TYPES_NAME).object_type
        self.extruder = getattr(obj, TYPES_NAME).extruder
        self.modifiers = list(getattr(obj, TYPES_NAME).modifiers)
        self.parent = parent

        depsgraph = bpy.context.evaluated_depsgraph_get()
        scene_scale: float = bpy.context.scene.unit_settings.scale_length
        eval_objects = obj.evaluated_get(depsgraph)

        self.mesh = objects_to_tris([eval_objects], 1000 * scene_scale)

    def offset(self, offset: NDArray):
        self.mesh += offset

    @property
    def checksum(self) -> int: return crc32_array(self.mesh)

    @property
    def height(self) -> float: return self.mesh[:, :3, 2].max()

    @property
    def min_x(self) -> float: return self.mesh[:, :3, 0].min()

    @property
    def max_x(self) -> float: return self.mesh[:, :3, 0].max()

    @property
    def min_y(self) -> float: return self.mesh[:, :3, 1].min()

    @property
    def max_y(self) -> float: return self.mesh[:, :3, 1].max()

    @property
    def min_xy(self) -> NDArray: return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray: return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray: return (self.min_xy + self.max_xy) / 2.0

class SlicingCollection():
    name: str
    objects: list[SlicingObject]

    def __init__(self, objs: list[Object], parent: str):
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
    wipe_tower_xy: NDArray = np.array([0, 0])
    wipe_tower_rotation_deg: float = 0

    def __init__(self, selected_objs: list[Object]) -> None:

        family = []
        for obj in selected_objs:
            family.append(obj)
            family.extend(get_all_children(obj))
        # Remove duplicates
        family = list(set(family))

        filtered_objs = [o for o in family if getattr(o, TYPES_NAME).object_type != 'Ignore']

        def find_top_parent(o):
            current = o
            while current.parent is not None:
                current = current.parent
            return current
        
        parents: dict[str, list[Object]] = {}
        [parents.setdefault(find_top_parent(o).name, []).append(o) for o in filtered_objs]

        self.collections = {}
        for k, objects in parents.items():
            self.collections[k] = SlicingCollection(objects, k)
        
        self._extract_metadata(family)

    def _extract_metadata(self, objs) -> None:
        import math
        depsgraph = bpy.context.evaluated_depsgraph_get()
        scale_tx = 1000. * bpy.context.scene.unit_settings.scale_length #type: ignore

        self.wipe_tower_xy = self.center_xy[0:2]
        for obj in objs:
            eval_obj = obj.evaluated_get(depsgraph)
            if eval_obj.blendertoprusaslicer.object_type == 'WipeTower':
                self.wipe_tower_xy = np.array(eval_obj.location[0:2]) * scale_tx
                self.wipe_tower_rotation_deg = round(eval_obj.rotation_euler[2]*180/math.pi,5)
                break

        return

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
    def height(self) -> float: return max(so.height for k, so in self.collections.items() if so.meshes)

    @property
    def min_x(self) -> float: return min(so.min_x for k, so in self.collections.items() if so.meshes)

    @property
    def max_x(self) -> float: return max(so.max_x for k, so in self.collections.items() if so.meshes)

    @property
    def min_y(self) -> float: return min(so.min_y for k, so in self.collections.items() if so.meshes)

    @property
    def max_y(self) -> float: return max(so.max_y for k, so in self.collections.items() if so.meshes)

    @property
    def min_xy(self) -> NDArray: return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray: return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray: return (self.min_xy + self.max_xy) / 2.0

class TriMesh():
    mesh: Mesh
    length_verts: int
    length_tris: int
    matrix_world: Any

    def __init__(self, mesh: Mesh, v: int, t: int, m) -> None:
        self.mesh = mesh
        self.length_verts = v
        self.length_tris = t
        self.matrix_world = m

def objects_to_tris(objects: list[Object], scale) -> np.ndarray[tuple[int, int, int], dtype[np.float64]]:
    tris_count: int = 0
    meshes: list[TriMesh] = []

    for obj in objects:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            mesh: Mesh = obj.to_mesh(depsgraph=depsgraph, preserve_all_data_layers=True)
        except: continue
        mesh.calc_loop_triangles()

        cur_length = len(mesh.loop_triangles)
        if cur_length == 0: continue

        tris_count += cur_length
        
        meshes += [TriMesh(
            mesh,
            len(mesh.vertices),
            len(mesh.loop_triangles),
            np.array(obj.matrix_world.transposed())
        )]

    # tris_count: int = sum(len(obj.data.loop_triangles) for obj in objects if hasattr(obj.data, 'loop_triangles'))
    tris_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(tris_count * 4 * 3, dtype=dtype(np.float64))
    tris: np.ndarray[tuple[int, int, int], dtype[np.float64]] = tris_flat.reshape(-1,  4,  3)

    col_idx = 0
    for trimesh in meshes:
        tris_v_i_flat: np.ndarray[tuple[int], dtype[np.int32]] = np.empty(trimesh.length_tris * 3, dtype=dtype(np.int32))
        tris_v_n_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(trimesh.length_tris * 3, dtype=dtype(np.float64))
        tris_verts_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(trimesh.length_verts * 3, dtype=dtype(np.float64))

        trimesh.mesh.loop_triangles.foreach_get("vertices", tris_v_i_flat)
        trimesh.mesh.loop_triangles.foreach_get("normal", tris_v_n_flat)
        trimesh.mesh.vertices.foreach_get("co", tris_verts_flat)

        tris_v_i: np.ndarray[tuple[int, int], dtype[np.int32]] = tris_v_i_flat.reshape((-1, 3))
        tris_v_n: np.ndarray[tuple[int, int], dtype[np.float64]] = tris_v_n_flat.reshape((-1, 3))
        tris_verts: np.ndarray[tuple[int, int], dtype[np.float64]] = tris_verts_flat.reshape((-1, 3))

        homogeneous_verts = np.hstack((tris_verts, np.ones((tris_verts.shape[0], 1)))) # type: ignore
        tx_verts = homogeneous_verts @ trimesh.matrix_world
        tx_verts = (tx_verts[:, :3]) * scale

        homogeneous_norm = np.hstack((tris_v_n, np.ones((tris_v_n.shape[0], 1)))) # type: ignore
        tx_norm = homogeneous_norm @ trimesh.matrix_world.T
        tx_norm = tx_norm[:, :3]
        tx_norm = tx_norm / np.linalg.norm(tx_norm, axis=1, keepdims=True)
        tx_norm = tx_norm[:, np.newaxis, :]

        tx_tris = tx_verts[tris_v_i]
        
        tris_coords_and_norm = np.concatenate((tx_tris, tx_norm), axis=1)
        
        tris[col_idx:col_idx + trimesh.length_tris,:] = tris_coords_and_norm
        
        col_idx += trimesh.length_tris

    return tris