from __future__ import annotations

from typing import Any
import bpy
from bpy.types import Collection, LayerCollection, Object, Scene

from .. import PACKAGE

def coll_from_selection() -> Collection | None:
    for obj in bpy.context.selected_objects:
        return obj.users_collection[0]

    if not bpy.context.view_layer: return None

    active_layer_collection: LayerCollection | None = bpy.context.view_layer.active_layer_collection

    cx: Collection | None = active_layer_collection.collection if active_layer_collection else None
    
    return cx

def reset_selection(object, field):
    if getattr(object, field) > -1:
        setattr(object, field, -1)

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

def calc_printer_intrinsics(printer_config) -> dict[str, int]:
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore

    intrinsics: dict[str, Any] = {
        'extruder_count': 1,
    }

    profile_cache = prefs.profile_cache
    if not (profile := profile_cache.profiles.get(printer_config)): return intrinsics
    
    intrinsics['extruder_count'] = int(profile_cache.profiles[printer_config].all_conf_dict.get('num_extruders','1'))
    
    return intrinsics

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

def get_all_children(obj):
    children = []
    for child in obj.children:
        children += [child] + get_all_children(child)
    return children

def selected_top_level_objects() -> list[Object]:
    selected: list[Object] = bpy.context.selected_objects
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

# Addon-specific

def get_inherited_prop(pg_name: str, coll_hierarchy: list[Collection], attr: str, conf_type: str | None = None) -> dict[str, str]:
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

def get_inherited_slicing_props(cx: Collection, pg_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    conf_map: list[tuple[str, str]] = [('printer_config_file', 'printer')]

    coll_hierarchy: list[Collection] | None = get_collection_parents(target_collection=cx)
    if not coll_hierarchy: return result
    
    printer: dict[str, str] = get_inherited_prop(pg_name, coll_hierarchy, 'printer_config_file')
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