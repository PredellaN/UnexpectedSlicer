from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from bpy.types import Collection, Object, Scene, LayerCollection
    from ..preferences.preferences import SlicerPreferences

from _hashlib import HASH
from numpy import dtype, ndarray, int32, float64
from numpy.typing import NDArray

import bpy
import re
import hashlib
import numpy as np
import struct

from collections import Counter

from .. import PACKAGE

def redraw():
    if not bpy.context.workspace: return
    for screen in bpy.context.workspace.screens:
        for area in screen.areas:
            area.tag_redraw()

def show_progress(ref, progress, progress_text = ""):
    setattr(ref, 'progress', progress)
    setattr(ref, 'progress_text', progress_text)
    redraw()
    return None

def names_array_from_objects(obj_names):
    summarized_names = [re.sub(r'\.\d{0,3}$', '', name) for name in obj_names]
    name_counter = Counter(summarized_names)
    final_names = [f"{count}x_{name}" if count > 1 else name for name, count in name_counter.items()]
    final_names.sort()
    return final_names

def calc_printer_intrinsics(printer_config) -> dict[str, int]:
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore

    intrinsics: dict[str, Any] = {
        'extruder_count': 1,
    }

    profile_cache = prefs.profile_cache
    if not (profile := profile_cache.profiles.get(printer_config)): return intrinsics
    
    intrinsics['extruder_count'] = int(profile_cache.profiles[printer_config].all_conf_dict.get('num_extruders','1'))
    
    return intrinsics

def calculate_md5(file_paths) -> str:
    md5_hash: HASH = hashlib.md5()
    for file_path in file_paths:
        with open(file=file_path, mode="rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def coll_from_selection() -> Collection | None:
    for obj in bpy.context.selected_objects:
        return obj.users_collection[0]

    if not bpy.context.view_layer: return None

    active_layer_collection: LayerCollection | None = bpy.context.view_layer.active_layer_collection

    cx: Collection | None = active_layer_collection.collection if active_layer_collection else None
    
    return cx
        
def get_collection_parents(target_collection: Collection) -> list[Collection] | None:
    if not bpy.context.scene: raise Exception('No scene currently open!')
    scene: Scene = bpy.context.scene

    def recursive_find(coll: Collection, path: list[Collection]) -> list[Collection] | None:
        if coll == target_collection:
            return path + [coll]
        for child in coll.children:
            result: list[Collection] | None = recursive_find(coll=child, path=path + [coll])
            if result is not None:
                return result
        return None

    return recursive_find(coll=scene.collection, path=[])

def get_inherited_prop(pg_name: str, coll_hierarchy: list[Collection], attr: str, conf_type: str | None = None) -> dict[str, str | bool]:
    res = {}
    is_set = False
    config = ''
    source: None | int = None
    for idx, coll in enumerate(coll_hierarchy):
        pg = getattr(coll, pg_name)
        config: str = getattr(pg, attr, '')
        if config:
            is_set = True
            source = idx
            res['prop'] = config

    final_index = len(coll_hierarchy) - 1
    res['inherited'] = is_set and not (source == final_index)

    if conf_type:
        res['type'] = conf_type

    return res

def get_inherited_slicing_props(cx: Collection, pg_name: str) -> dict[str, dict[str, str | bool]]:
    result: dict[str, dict[str, str | bool]] = {}
    conf_map: list[tuple[str, str]] = [('printer_config_file', 'printer')]

    coll_hierarchy: list[Collection] | None = get_collection_parents(target_collection=cx)
    if not coll_hierarchy: return result
    
    printer: dict[str, str | bool] = get_inherited_prop(pg_name, coll_hierarchy, 'printer_config_file')
    extruder_count: int = calc_printer_intrinsics(printer['prop'])['extruder_count'] if printer.get('prop') else 1
    
    for i in ['','_2','_3','_4','_5'][:extruder_count]:
        key: str = f'filament{i}_config_file'
        conf_map.append((key, 'filament'))
    
    conf_map.append(('print_config_file', 'print'))
    
    for attr, conf_type in conf_map:
        result[attr] = get_inherited_prop(pg_name, coll_hierarchy, attr, conf_type)
    
    return result

def get_inherited_overrides(cx, pg_name) -> dict[str, dict[str, str | bool | int]]:
    result: dict[str, dict[str, str | int]] = {}
    coll_hierarchy: list[Collection] | None = get_collection_parents(target_collection=cx)

    if not coll_hierarchy:
        return {}

    for idx, coll in enumerate(coll_hierarchy):
        pg = getattr(coll, pg_name)
        overrides: dict[str, dict[str, str | int]] = {
            o['param_id']: {
                'value': str(o.get('param_value', None)), 
                'source': idx
            }
            for o in pg.list if o.get('param_id')
        }
        for o in pg.list:
            pass
        result.update(overrides)

    final_index = len(coll_hierarchy) - 1
    for param, data in result.items():
        data['inherited'] = data['source'] != final_index
        del data['source']

    return result


def objects_to_tris(objects, scale) -> np.ndarray[tuple[int, int, int], dtype[np.float64]]:
    tris_count: int = sum(len(obj.data.loop_triangles) for obj in objects)
    tris_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(tris_count * 4 * 3, dtype=dtype(np.float64))
    tris: np.ndarray[tuple[int, int, int], dtype[np.float64]] = tris_flat.reshape(-1,  4,  3)

    col_idx = 0
    for obj in objects:
        mesh = obj.data
        curr_tris_count: int = len(mesh.loop_triangles)
        curr_vert_count: int = len(mesh.vertices)

        tris_v_i_flat: np.ndarray[tuple[int], dtype[np.int32]] = np.empty(curr_tris_count * 3, dtype=dtype(np.int32))
        mesh.loop_triangles.foreach_get("vertices", tris_v_i_flat)
        tris_v_i: np.ndarray[tuple[int, int], dtype[np.int32]] = tris_v_i_flat.reshape((-1, 3))

        tris_v_n_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(curr_tris_count * 3, dtype=dtype(np.float64))
        mesh.loop_triangles.foreach_get("normal", tris_v_n_flat)
        tris_v_n: np.ndarray[tuple[int, int], dtype[np.float64]] = tris_v_n_flat.reshape((-1, 3))

        tris_verts_flat: np.ndarray[tuple[int], dtype[np.float64]] = np.empty(curr_vert_count * 3, dtype=dtype(np.float64))
        mesh.vertices.foreach_get("co", tris_verts_flat)
        tris_verts: np.ndarray[tuple[int, int], dtype[np.float64]] = tris_verts_flat.reshape((-1, 3))
        
        world_matrix = np.array(obj.matrix_world.transposed())

        homogeneous_verts = np.hstack((tris_verts, np.ones((tris_verts.shape[0], 1)))) # type: ignore
        tx_verts = homogeneous_verts @ world_matrix
        tx_verts = (tx_verts[:, :3]) * scale

        homogeneous_norm = np.hstack((tris_v_n, np.ones((tris_v_n.shape[0], 1)))) # type: ignore
        tx_norm = homogeneous_norm @ world_matrix.T
        tx_norm = tx_norm[:, :3]
        tx_norm = tx_norm / np.linalg.norm(tx_norm, axis=1, keepdims=True)
        tx_norm = tx_norm[:, np.newaxis, :]

        tx_tris = tx_verts[tris_v_i]
        
        tris_coords_and_norm = np.concatenate((tx_tris, tx_norm), axis=1)
        
        tris[col_idx:col_idx + curr_tris_count,:] = tris_coords_and_norm
        
        col_idx += curr_tris_count

    return tris

def save_stl(tris, filename):
    header = b'\0' * 80 + struct.pack('<I', tris.shape[0])

    with open(filename, 'wb') as f:
        f.write(header)
        for tri in tris:
            v1, v2, v3, normal = tri
            data = struct.pack('<12fH', *normal, *v1, *v2, *v3, 0)
            f.write(data)

def get_all_children(obj):
    children = []
    for child in obj.children:
        children += [child] + get_all_children(child)
    return children

def selected_object_family() -> tuple[list[Object], dict[str, str]]:
    selected = bpy.context.selected_objects
    # Collect all selected objects and their descendants
    family = []
    for obj in selected:
        family.append(obj)
        family.extend(get_all_children(obj))
    # Remove duplicates
    family = list(set(family))

    # Helper to find the top-level ancestor
    def find_top_parent(o):
        current = o
        while current.parent is not None:
            current = current.parent
        return current

    # Build mapping
    parent_map = {}
    for obj in family:
        if obj.parent is None:
            parent_map[obj.name] = obj.name
        else:
            top = find_top_parent(obj)
            parent_map[obj.name] = top.name

    return family, parent_map

def selected_top_level_objects():
    selected = bpy.context.selected_objects
    top_level_objects = []

    for obj in selected:
        if obj.parent is None or obj.parent not in selected:
            top_level_objects += [obj]

    return top_level_objects

def collection_to_dict_list(coll) -> list[dict[str, Any]]:
    return [
        {p.identifier: getattr(item, p.identifier)
         for p in item.bl_rna.properties
         if not p.is_readonly and p.identifier != "rna_type"}
        for item in coll
    ]