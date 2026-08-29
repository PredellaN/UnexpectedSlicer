from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import UILayout, bpy_prop_collection, PropertyGroup
    from ....props.bpy_property_groups import ParamslistItem

def draw_item(layout: UILayout, item: ParamslistItem):
    layout.prop(item, 'param_id', text="")

    from .props import draw_formatted_prop
    draw_formatted_prop(layout, item)

def draw_override_items(layout: UILayout, data: bpy_prop_collection, list_id: str, remove_operator: str):
    for idx, item in enumerate(data):
        row = layout.row(align=True)
        
        if remove_operator:
            from ..common import create_operator_row
            create_operator_row(row, remove_operator, list_id, idx, 'X')

        draw_item(row, item)

import bpy

_pending_adds: set[tuple[int, str]] = set()

def _add_empty_item_cb(pg_ptr: int, pg: PropertyGroup, list_id: str):
    _pending_adds.discard((pg_ptr, list_id))
    try:
        data = getattr(pg, list_id)
        if not len(data) or data[-1].param_id != "":
            data.add()
    except Exception:
        pass
    return None

def ensure_empty_end_item(pg: PropertyGroup, list_id: str) -> None:
    data: bpy_prop_collection = getattr(pg, list_id)
    if not len(data) or data[-1].param_id != "":
        pg_ptr = pg.as_pointer()
        key = (pg_ptr, list_id)
        if key not in _pending_adds:
            _pending_adds.add(key)
            bpy.app.timers.register(lambda: _add_empty_item_cb(pg_ptr, pg, list_id))

def draw_object_overrides_list(layout: UILayout, pg: PropertyGroup, list_id: str) -> None:
    ensure_empty_end_item(pg, list_id)
    box: UILayout = layout.box()
    data: bpy_prop_collection = getattr(pg, list_id)

    draw_override_items(box, data, list_id, 'object.slicer_remove_item')

def draw_overrides_list(layout: UILayout, pg: PropertyGroup, list_id: str, readonly_data: list[dict]) -> None:
    ensure_empty_end_item(pg, list_id)
    box: UILayout = layout.box()
    data: bpy_prop_collection = getattr(pg, list_id)

    draw_override_items(box, data, list_id, 'collection.slicer_remove_item')
    
    for item in readonly_data:
        row = box.row(align=True)
        row.label(icon='RNA')
        row.label(text=f"{item.get('param_id', '')}")
        row.label(text=str(item.get('param_value', '')))