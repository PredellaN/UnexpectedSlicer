from __future__ import annotations
from bpy.types import FloatAttribute, Object, Mesh
import bpy
import zlib, struct
from functools import cached_property

import numpy as np
from numpy import dtype, float64
from numpy.typing import NDArray

from typing import Any, cast

from ..core.geometry import crc32_array
from ..infra.blender_bridge import get_all_children

from .. import TYPES_NAME

class MeshCaptureException(Exception): pass

class SlicingObject():
    name: str
    parent: str
    object_type: str
    extruder: str
    modifiers: list[dict]
    displacement: NDArray[float64]
    mesh: NDArray[float64]
    extruder_ids: NDArray[np.int32]
    support_states: NDArray[np.int32]
    fuzzy_states: NDArray[np.int32]

    def __init__(self, obj: Object, parent: str) -> None:
        if not bpy.context.scene: raise Exception('No scene currently open!')

        self.name = str(obj.name)
        self.object_type = getattr(obj, TYPES_NAME).object_type
        self.extruder = getattr(obj, TYPES_NAME).extruder
        self.modifiers = [
            {k: item[k] for k in item.keys()}
            for item in getattr(obj, TYPES_NAME).modifiers
        ]
        self.parent = parent

        depsgraph = bpy.context.evaluated_depsgraph_get()
        scene_scale: float = bpy.context.scene.unit_settings.scale_length
        eval_objects = obj.evaluated_get(depsgraph)

        self.mesh, self.displacement, self.extruder_ids, self.support_states, self.fuzzy_states = objects_to_tris([eval_objects], 1000 * scene_scale)

    def offset(self, offset: NDArray):
        self.mesh += offset

    def copy_with_transform(self, M_rel: NDArray[float64], new_parent: str) -> SlicingObject:
        new_obj = SlicingObject.__new__(SlicingObject)
        new_obj.name = self.name
        new_obj.parent = new_parent
        new_obj.object_type = 'ModelPart' if self.object_type in ('Ignore', 'Instance') else self.object_type
        new_obj.extruder = self.extruder
        new_obj.modifiers = [dict(mod) for mod in self.modifiers]
        new_obj.extruder_ids = self.extruder_ids.copy() if hasattr(self, 'extruder_ids') and self.extruder_ids is not None else np.empty(0, dtype=np.int32)
        new_obj.support_states = self.support_states.copy() if hasattr(self, 'support_states') and self.support_states is not None else np.empty(0, dtype=np.int32)
        new_obj.fuzzy_states = self.fuzzy_states.copy() if hasattr(self, 'fuzzy_states') and self.fuzzy_states is not None else np.empty(0, dtype=np.int32)
        new_obj.displacement = self.displacement.copy() if hasattr(self, 'displacement') and self.displacement is not None else None

        if hasattr(self, 'mesh') and self.mesh is not None and self.mesh.size:
            R = M_rel[:3, :3].T
            t = M_rel[:3, 3]
            v = self.mesh[:, :3, :]
            v_tx = v @ R + t
            n = self.mesh[:, 3:4, :]
            n_tx = n @ R
            norm_len = np.linalg.norm(n_tx, axis=2, keepdims=True)
            norm_len[norm_len == 0] = 1.0
            n_tx = n_tx / norm_len
            new_obj.mesh = np.concatenate((v_tx, n_tx), axis=1)
        else:
            new_obj.mesh = self.mesh.copy() if hasattr(self, 'mesh') and self.mesh is not None else np.empty(0)

        return new_obj

    @property
    def checksum(self) -> int:
        import json

        buf = bytearray()
        buf.extend(struct.pack(">I", crc32_array(self.mesh)))
        buf.extend(struct.pack(">I", crc32_array(self.extruder_ids)))
        buf.extend(struct.pack(">I", crc32_array(self.support_states)))
        buf.extend(struct.pack(">I", crc32_array(self.fuzzy_states)))
        buf.extend(struct.pack(">I", zlib.crc32(self.name.encode("utf-8"))))
        buf.extend(struct.pack(">I", zlib.crc32(self.parent.encode("utf-8"))))
        buf.extend(struct.pack(">I", zlib.crc32(self.object_type.encode("utf-8"))))
        buf.extend(struct.pack(">I", zlib.crc32(str(self.extruder).encode("utf-8"))))

        modifiers_dict = [dict(mod) for mod in self.modifiers]
        modifiers_json = json.dumps(modifiers_dict , sort_keys=True).encode("utf-8")
        buf.extend(struct.pack(">I", zlib.crc32(modifiers_json)))

        return zlib.crc32(buf) & 0xFFFFFFFF

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
        self.objects = [o for o in self.objects if o.mesh.size]
        self.name = parent

    @classmethod
    def from_existing_with_transform(cls, existing_coll: SlicingCollection, M_rel: NDArray[float64], new_name: str) -> SlicingCollection:
        new_coll = cls.__new__(cls)
        new_coll.name = new_name
        new_coll.objects = [o.copy_with_transform(M_rel, new_name) for o in existing_coll.objects]
        new_coll.objects = [o for o in new_coll.objects if o.mesh.size]
        return new_coll

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

    @cached_property
    def extruder_ids(self) -> NDArray:
        if not self.objects:
            return np.empty(0, dtype=np.int32)
        return np.concatenate([o.extruder_ids for o in self.objects])

    @cached_property
    def support_states(self) -> NDArray:
        if not self.objects:
            return np.empty(0, dtype=np.int32)
        return np.concatenate([o.support_states for o in self.objects])

    @cached_property
    def fuzzy_states(self) -> NDArray:
        if not self.objects:
            return np.empty(0, dtype=np.int32)
        return np.concatenate([o.fuzzy_states for o in self.objects])

    @property
    def min_x(self) -> float | None:
        return min([so.min_x for so in self.objects if np.any(so.mesh)], default=None)

    @property
    def max_x(self) -> float | None:
        return max([so.max_x for so in self.objects if np.any(so.mesh)], default=None)

    @property
    def min_y(self) -> float | None:
        return min([so.min_y for so in self.objects if np.any(so.mesh)], default=None)

    @property
    def max_y(self) -> float | None:
        return max([so.max_y for so in self.objects if np.any(so.mesh)], default=None)

    @property
    def min_xy(self) -> NDArray | None:
        if self.min_x is None or self.min_y is None: return None
        return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray | None:
        if self.max_x is None or self.max_y is None: return None
        return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray | None:
        if self.min_xy is None or self.max_xy is None: return None
        return (self.min_xy + self.max_xy) / 2.0

class SlicingInstance():
    name: str
    target_name: str
    target_collection: SlicingCollection
    inst_obj: Object
    target_obj: Object
    transformed_meshes: list[NDArray[float64]]
    M_inst_mm: NDArray[float64]
    M_target_mm: NDArray[float64]
    M_rel: NDArray[float64]
    _offset: NDArray[float64]

    def __init__(
        self,
        inst_obj: Object,
        target_obj: Object,
        target_name: str,
        target_coll: SlicingCollection,
        mat_inst: NDArray[float64] | None = None,
        mat_target: NDArray[float64] | None = None,
        name: str | None = None,
    ) -> None:
        self.name = name if name is not None else str(inst_obj.name)
        self.target_name = target_name
        self.target_collection = target_coll
        self.inst_obj = inst_obj
        self.target_obj = target_obj
        self._offset = np.array([0.0, 0.0, 0.0], dtype=np.float64)

        depsgraph = bpy.context.evaluated_depsgraph_get() if bpy.context.scene else None
        scene_scale: float = bpy.context.scene.unit_settings.scale_length if bpy.context.scene else 1.0
        scale_tx: float = 1000.0 * scene_scale

        if mat_inst is None:
            eval_inst = inst_obj.evaluated_get(depsgraph) if depsgraph else inst_obj
            mat_inst = np.array(eval_inst.matrix_world, dtype=np.float64)

        if mat_target is None:
            eval_target = target_obj.evaluated_get(depsgraph) if depsgraph else target_obj
            mat_target = np.array(eval_target.matrix_world, dtype=np.float64)

        M_inst_mm = mat_inst.copy()
        M_inst_mm[:3, 3] *= scale_tx

        M_target_mm = mat_target.copy()
        M_target_mm[:3, 3] *= scale_tx

        self.M_inst_mm = M_inst_mm
        self.M_target_mm = M_target_mm

        try:
            inv_target = np.linalg.inv(M_target_mm)
            self.M_rel = M_inst_mm @ inv_target
        except np.linalg.LinAlgError:
            self.M_rel = np.eye(4, dtype=np.float64)

        self.transformed_meshes = []
        R_3mf = self.M_rel[:3, :3].T
        t_3mf = self.M_rel[:3, 3]
        for mesh in target_coll.meshes:
            if mesh.size:
                verts = mesh[:, :3, :]
                tx_verts = verts @ R_3mf + t_3mf
                self.transformed_meshes.append(tx_verts)

    def offset(self, offset: NDArray):
        self._offset = self._offset + offset
        for i in range(len(self.transformed_meshes)):
            self.transformed_meshes[i] = self.transformed_meshes[i] + offset

    @property
    def transform_str(self) -> str:
        T = np.eye(4, dtype=np.float64)
        T[:3, 3] = self._offset
        W_A = T @ self.M_target_mm
        W_B = T @ self.M_inst_mm
        try:
            M_rel_bed = W_B @ np.linalg.inv(W_A)
        except np.linalg.LinAlgError:
            M_rel_bed = np.eye(4, dtype=np.float64)

        M_3mf = M_rel_bed.T
        vals = [
            M_3mf[0, 0], M_3mf[0, 1], M_3mf[0, 2],
            M_3mf[1, 0], M_3mf[1, 1], M_3mf[1, 2],
            M_3mf[2, 0], M_3mf[2, 1], M_3mf[2, 2],
            M_3mf[3, 0], M_3mf[3, 1], M_3mf[3, 2],
        ]
        return " ".join(f"{round(v, 6):.6f}".rstrip('0').rstrip('.') or "0" for v in vals)

    @property
    def min_x(self) -> float | None:
        if not self.transformed_meshes: return None
        return min(m[:, :, 0].min() for m in self.transformed_meshes)

    @property
    def max_x(self) -> float | None:
        if not self.transformed_meshes: return None
        return max(m[:, :, 0].max() for m in self.transformed_meshes)

    @property
    def min_y(self) -> float | None:
        if not self.transformed_meshes: return None
        return min(m[:, :, 1].min() for m in self.transformed_meshes)

    @property
    def max_y(self) -> float | None:
        if not self.transformed_meshes: return None
        return max(m[:, :, 1].max() for m in self.transformed_meshes)

    @property
    def height(self) -> float:
        if not self.transformed_meshes: return 0.0
        return max(m[:, :, 2].max() for m in self.transformed_meshes)

def get_instance_matrices(inst_obj: Object, depsgraph: Any) -> list[tuple[NDArray[float64], str]]:
    matrices: list[tuple[NDArray[float64], str]] = []

    if depsgraph is not None:
        eval_inst = inst_obj.evaluated_get(depsgraph)
        try:
            for dup in depsgraph.object_instances:
                if dup.is_instance:
                    is_match = False
                    if dup.parent:
                        if (
                            dup.parent == eval_inst
                            or getattr(dup.parent, "original", None) == inst_obj
                            or dup.parent.name == inst_obj.name
                        ):
                            is_match = True
                    if not is_match and dup.object:
                        if (
                            dup.object == eval_inst
                            or getattr(dup.object, "original", None) == inst_obj
                            or dup.object.name == inst_obj.name
                        ):
                            is_match = True

                    if is_match:
                        mat = np.array(dup.matrix_world, dtype=np.float64)
                        name = f"{inst_obj.name}_{len(matrices) + 1}"
                        matrices.append((mat, name))
        except Exception:
            pass

    if not matrices:
        eval_inst = inst_obj.evaluated_get(depsgraph) if depsgraph is not None else inst_obj
        mat = np.array(eval_inst.matrix_world, dtype=np.float64)
        matrices.append((mat, str(inst_obj.name)))

    return matrices

class SlicingGroup():

    collections: dict[str, SlicingCollection]
    instances: list[SlicingInstance]

    # Metadata
    wipe_tower_xy: NDArray = np.array([0, 0])
    wipe_tower_rotation_deg: float = 0
    _wipe_tower_is_scene_relative: bool = True

    def __init__(self, selected_objs: list[Object], pg: Any = None) -> None:

        family = []
        for obj in selected_objs:
            family.append(obj)
            family.extend(get_all_children(obj))
        # Remove duplicates preserving order
        family = list(dict.fromkeys(family))

        non_ignored = [
            o for o in family
            if hasattr(o, TYPES_NAME) and getattr(o, TYPES_NAME).object_type != 'Ignore'
        ]

        base_objs = [
            o for o in non_ignored
            if getattr(o, TYPES_NAME).object_type != 'Instance'
        ]

        instance_objs = [
            o for o in non_ignored
            if getattr(o, TYPES_NAME).object_type == 'Instance'
        ]

        def find_top_parent(o):
            current = o
            while current.parent is not None:
                current = current.parent
            return current
        
        parents: dict[str, list[Object]] = {}
        for o in base_objs:
            parents.setdefault(find_top_parent(o).name, []).append(o)

        self.collections = {}
        self.collection_top_parent_objs: dict[str, Object] = {}
        for k, objects in parents.items():
            top_obj = find_top_parent(objects[0])
            col = SlicingCollection(objects, k)
            if col.meshes:
                self.collections[k] = col
                self.collection_top_parent_objs[k] = top_obj

        # Group instance objects by their target top parent
        # Each entry is (inst_obj, target_top_parent, mat_inst, inst_name)
        instances_by_target: dict[str, list[tuple[Object, Object, NDArray[float64], str]]] = {}
        depsgraph = bpy.context.evaluated_depsgraph_get() if bpy.context.scene else None
        scene_scale: float = bpy.context.scene.unit_settings.scale_length if bpy.context.scene else 1.0
        scale_tx: float = 1000.0 * scene_scale

        for inst_obj in instance_objs:
            inst_pg = getattr(inst_obj, TYPES_NAME, None)
            if not inst_pg:
                continue
            target_ref = getattr(inst_pg, "instance_object", None)
            if not target_ref:
                continue
            target_top_parent = find_top_parent(target_ref)
            target_name = target_top_parent.name

            inst_matrices = get_instance_matrices(inst_obj, depsgraph)
            for mat_inst, inst_name in inst_matrices:
                instances_by_target.setdefault(target_name, []).append(
                    (inst_obj, target_top_parent, mat_inst, inst_name)
                )

        self.instances = []

        for target_name, inst_list in instances_by_target.items():
            if target_name in self.collections:
                # Target object is already being sliced directly as a base object
                target_coll = self.collections[target_name]
                target_top_parent = self.collection_top_parent_objs[target_name]
                eval_target = target_top_parent.evaluated_get(depsgraph) if depsgraph else target_top_parent
                mat_target = np.array(eval_target.matrix_world, dtype=np.float64)

                for inst_obj, _, mat_inst, inst_name in inst_list:
                    self.instances.append(
                        SlicingInstance(
                            inst_obj=inst_obj,
                            target_obj=target_top_parent,
                            target_name=target_name,
                            target_coll=target_coll,
                            mat_inst=mat_inst,
                            mat_target=mat_target,
                            name=inst_name,
                        )
                    )
            else:
                # Target is NOT in self.collections (not directly sliced).
                # If there are instances but no objects, the first instance is turned into the actual object.
                first_inst_obj, target_top_parent, mat_first_inst, first_inst_name = inst_list[0]
                target_family = [target_top_parent] + get_all_children(target_top_parent)
                target_filtered = [
                    o for o in target_family
                    if hasattr(o, TYPES_NAME) and getattr(o, TYPES_NAME).object_type not in ('Ignore', 'Instance')
                ]
                if not target_filtered:
                    target_filtered = [
                        o for o in target_family
                        if not hasattr(o, TYPES_NAME) or getattr(o, TYPES_NAME).object_type != 'Instance'
                    ]

                raw_target_coll = SlicingCollection(target_filtered, target_name)
                if not raw_target_coll.meshes:
                    continue

                base_coll_name = str(first_inst_obj.name)

                # Compute relative transform from target_top_parent to first instance matrix
                eval_target = target_top_parent.evaluated_get(depsgraph) if depsgraph else target_top_parent
                mat_target = np.array(eval_target.matrix_world, dtype=np.float64)

                M_first_inst_mm = mat_first_inst.copy()
                M_first_inst_mm[:3, 3] *= scale_tx

                M_target_mm = mat_target.copy()
                M_target_mm[:3, 3] *= scale_tx

                try:
                    M_rel1 = M_first_inst_mm @ np.linalg.inv(M_target_mm)
                except np.linalg.LinAlgError:
                    M_rel1 = np.eye(4, dtype=np.float64)

                promoted_coll = SlicingCollection.from_existing_with_transform(raw_target_coll, M_rel1, base_coll_name)
                self.collections[base_coll_name] = promoted_coll
                self.collection_top_parent_objs[base_coll_name] = first_inst_obj

                # Remaining instances turn into prusaslicer instances of the promoted base object
                for rem_inst_obj, _, mat_rem_inst, rem_inst_name in inst_list[1:]:
                    self.instances.append(
                        SlicingInstance(
                            inst_obj=rem_inst_obj,
                            target_obj=first_inst_obj,
                            target_name=base_coll_name,
                            target_coll=promoted_coll,
                            mat_inst=mat_rem_inst,
                            mat_target=mat_first_inst,
                            name=rem_inst_name,
                        )
                    )

        self._extract_metadata(pg=pg)

    def instance_count_for(self, coll_name: str) -> int:
        return 1 + sum(1 for inst in self.instances if inst.target_name == coll_name)

    def _extract_metadata(self, pg: Any = None) -> None:
        import math
        depsgraph = bpy.context.evaluated_depsgraph_get()
        scene = bpy.context.scene
        scale_tx = 1000. * scene.unit_settings.scale_length if scene else 1000.0

        center = self.center_xy[0:2] if self.center_xy is not None else np.array([0.0, 0.0])
        self.wipe_tower_xy = center
        self.wipe_tower_rotation_deg = 0.0
        self._wipe_tower_is_scene_relative = True

        if pg is not None:
            mode = getattr(pg, "wipe_tower_mode", "AUTO")
            if mode == "AUTO":
                min_x = self.min_x if self.min_x is not None else 0.0
                max_y = self.max_y if self.max_y is not None else 0.0
                self.wipe_tower_xy = np.array([min_x, max_y + 20.0])
                self.wipe_tower_rotation_deg = 0.0
                self._wipe_tower_is_scene_relative = True
            elif mode == "OBJECT":
                target_obj = getattr(pg, "wipe_tower_object", None)
                if target_obj:
                    eval_obj = target_obj.evaluated_get(depsgraph)
                    loc = eval_obj.matrix_world.translation
                    rot_z = eval_obj.matrix_world.to_euler('XYZ')[2]
                    self.wipe_tower_xy = np.array([loc.x, loc.y]) * scale_tx
                    self.wipe_tower_rotation_deg = round(math.degrees(rot_z), 5)
                    self._wipe_tower_is_scene_relative = True
                else:
                    self._wipe_tower_is_scene_relative = True
            else:
                loc = getattr(pg, "wipe_tower_location", (0.17, 0.14))
                rot = getattr(pg, "wipe_tower_rotation", 0.0)
                self.wipe_tower_xy = np.array([loc[0], loc[1]]) * scale_tx
                self.wipe_tower_rotation_deg = round(math.degrees(rot), 5)
                self._wipe_tower_is_scene_relative = False

        return

    def offset(self, offset: NDArray):
        for k, so in self.collections.items(): so.offset(offset)
        for inst in self.instances: inst.offset(offset)
        if self._wipe_tower_is_scene_relative:
            self.wipe_tower_xy = self.wipe_tower_xy + offset[0:2]

    @property
    def checksum(self):
        buf = bytearray()
        for key, col in sorted(self.collections.items(), key=lambda kv: kv[0]):
            key_bytes = key.encode('utf-8')
            buf.extend(struct.pack(">I", len(key_bytes)))
            buf.extend(key_bytes)
            buf.extend(struct.pack(">I", col.checksum))

        for inst in sorted(self.instances, key=lambda x: x.name):
            inst_bytes = inst.name.encode('utf-8')
            target_bytes = inst.target_name.encode('utf-8')
            buf.extend(struct.pack(">I", len(inst_bytes)))
            buf.extend(inst_bytes)
            buf.extend(struct.pack(">I", len(target_bytes)))
            buf.extend(target_bytes)
            buf.extend(struct.pack(">I", crc32_array(inst.M_inst_mm)))

        buf.extend(struct.pack(">I", crc32_array(self.wipe_tower_xy)))
        buf.extend(struct.pack(">I", crc32_array(np.array(self.wipe_tower_rotation_deg))))

        return zlib.crc32(buf) & 0xFFFFFFFF

    @property
    def height(self) -> float:
        h_colls = [so.height for k, so in self.collections.items() if so.height]
        h_insts = [inst.height for inst in self.instances if inst.height]
        return max(h_colls + h_insts, default=0.0)

    @property
    def min_x(self) -> float:
        m_colls = [so.min_x for k, so in self.collections.items() if so.min_x is not None]
        m_insts = [inst.min_x for inst in self.instances if inst.min_x is not None]
        return min(m_colls + m_insts, default=0.0)

    @property
    def max_x(self) -> float:
        m_colls = [so.max_x for k, so in self.collections.items() if so.max_x is not None]
        m_insts = [inst.max_x for inst in self.instances if inst.max_x is not None]
        return max(m_colls + m_insts, default=0.0)

    @property
    def min_y(self) -> float:
        m_colls = [so.min_y for k, so in self.collections.items() if so.min_y is not None]
        m_insts = [inst.min_y for inst in self.instances if inst.min_y is not None]
        return min(m_colls + m_insts, default=0.0)

    @property
    def max_y(self) -> float:
        m_colls = [so.max_y for k, so in self.collections.items() if so.max_y is not None]
        m_insts = [inst.max_y for inst in self.instances if inst.max_y is not None]
        return max(m_colls + m_insts, default=0.0)

    @property
    def min_xy(self) -> NDArray:
        if self.min_x is None or self.min_y is None: return np.array([.0, .0, .0])
        return np.array([self.min_x, self.min_y, 0.0])

    @property
    def max_xy(self) -> NDArray:
        if self.max_x is None or self.max_y is None: return np.array([.0, .0, .0])
        return np.array([self.max_x, self.max_y, 0.0])

    @property
    def center_xy(self) -> NDArray:
        if self.min_xy is None or self.max_xy is None: return np.array([.0, .0, .0])
        return (self.min_xy + self.max_xy) / 2.0

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

def extract_extruder_ids_from_mesh(mesh: Mesh, length_tris: int) -> NDArray:
    attr = mesh.attributes.get("extruder_id")
    if not attr or attr.domain != "FACE":
        return np.zeros(length_tris, dtype=np.int32)

    if attr.data_type.startswith("INT"):
        raw = np.empty(len(attr.data), dtype=np.int32)
        attr.data.foreach_get("value", raw)
    elif attr.data_type.startswith("FLOAT"):
        raw_f = np.empty(len(attr.data), dtype=np.float32)
        attr.data.foreach_get("value", raw_f)
        raw = np.round(raw_f).astype(np.int32)
    else:
        return np.zeros(length_tris, dtype=np.int32)

    tri_poly_idx = np.empty(length_tris, dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", tri_poly_idx)
    return raw[tri_poly_idx]

def extract_support_states_from_mesh(mesh: Mesh, length_tris: int) -> NDArray:
    states = np.zeros(len(mesh.polygons), dtype=np.int32)
    if (attr := mesh.attributes.get("support_enforce")) and attr.domain == "FACE":
        data = np.empty(len(attr.data), dtype=bool)
        attr.data.foreach_get("value", data)
        states[data] = 1
    if (attr := mesh.attributes.get("support_block")) and attr.domain == "FACE":
        data = np.empty(len(attr.data), dtype=bool)
        attr.data.foreach_get("value", data)
        states[data] = 2

    tri_poly_idx = np.empty(length_tris, dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", tri_poly_idx)
    return states[tri_poly_idx]

def extract_fuzzy_states_from_mesh(mesh: Mesh, length_tris: int) -> NDArray:
    states = np.zeros(len(mesh.polygons), dtype=np.int32)
    if (attr := mesh.attributes.get("fuzzy_skin")) and attr.domain == "FACE":
        data = np.empty(len(attr.data), dtype=bool)
        attr.data.foreach_get("value", data)
        states[data] = 1

    tri_poly_idx = np.empty(length_tris, dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", tri_poly_idx)
    return states[tri_poly_idx]

def objects_to_tris(objects: list[Object], scale) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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

    tris_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(tris_count * 4 * 3, dtype=dtype(np.float64))
    tris: np.ndarray[tuple[int, int, int], dtype[np.float64]] = tris_flat.reshape(-1,  4,  3)
    displ_tri = tris_flat.reshape(-1,  3)
    extruder_ids: np.ndarray = np.zeros(tris_count, dtype=np.int32)
    support_states: np.ndarray = np.zeros(tris_count, dtype=np.int32)
    fuzzy_states: np.ndarray = np.zeros(tris_count, dtype=np.int32)

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

        if trimesh.mesh.attributes.get("US_displace"):
            tri_loops_flat = np.empty(trimesh.length_tris * 3, dtype=np.int32)
            trimesh.mesh.loop_triangles.foreach_get("loops", tri_loops_flat) # per-tri-corner loop index
            tri_loops = tri_loops_flat.reshape((-1, 3)) # (n_tris, 3)

            displ_attr = cast(FloatAttribute, trimesh.mesh.attributes["US_displace"])
            displ_all_loops = np.empty(len(displ_attr.data), dtype=np.float32)
            displ_attr.data.foreach_get("value", displ_all_loops)

            displ_tri: NDArray = displ_all_loops[tri_loops]

        extruder_ids[col_idx:col_idx + trimesh.length_tris] = extract_extruder_ids_from_mesh(trimesh.mesh, trimesh.length_tris)
        support_states[col_idx:col_idx + trimesh.length_tris] = extract_support_states_from_mesh(trimesh.mesh, trimesh.length_tris)
        fuzzy_states[col_idx:col_idx + trimesh.length_tris] = extract_fuzzy_states_from_mesh(trimesh.mesh, trimesh.length_tris)

        homogeneous_verts: NDArray[float64] = np.hstack((tris_verts, np.ones((tris_verts.shape[0], 1)))) # type: ignore
        tx_verts = homogeneous_verts @ trimesh.matrix_world
        tx_verts = (tx_verts[:, :3]) * scale

        homogeneous_norm: NDArray[float64] = np.hstack((tris_v_n, np.ones((tris_v_n.shape[0], 1)))) # type: ignore
        tx_norm = homogeneous_norm @ trimesh.matrix_world.T
        tx_norm = tx_norm[:, :3]
        tx_norm = tx_norm / np.linalg.norm(tx_norm, axis=1, keepdims=True)
        tx_norm = tx_norm[:, np.newaxis, :]

        tx_tris = tx_verts[tris_v_i]
        
        tris_coords_and_norm: NDArray[float64] = np.concatenate((tx_tris, tx_norm), axis=1)
        
        tris[col_idx:col_idx + trimesh.length_tris,:] = tris_coords_and_norm
        
        col_idx += trimesh.length_tris

    return tris, displ_tri, extruder_ids, support_states, fuzzy_states