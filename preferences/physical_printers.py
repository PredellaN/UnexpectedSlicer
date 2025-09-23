from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..preferences.preferences import SlicerPreferences
    from bpy.types import UILayout, bpy_prop_collection
    from typing import Any

import bpy
from bpy.props import EnumProperty, StringProperty

from ..registry import register_class

from ..functions.blender_funcs import collection_to_dict_list
from ..ui.operators.common import ParamRemoveOperator, ParamAddOperator
from ..ui.mixins import FromPreferences
from ..ui.panels.common import create_operator_row

from .. import PACKAGE

@register_class
class RemovePrefItemOperator(FromPreferences, ParamRemoveOperator):
    bl_idname = "preferences.printers_remove_item"
    bl_label = ""

@register_class
class AddPrefItemOperator(FromPreferences, ParamAddOperator):
    bl_idname = "preferences.printers_add_item"

def update_querier(ref: Any = None, context: Any = None):
    from .preferences import frozen_eval
    if not frozen_eval:
        from ..services.physical_printers import printers_querier
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore
        printers_seralized = collection_to_dict_list(prefs.physical_printers)
        printers_querier.set_printers(printers_seralized)

@register_class
class PrintersListItem(bpy.types.PropertyGroup):
    param_id: StringProperty(name='') # pyright: ignore[reportInvalidTypeForm]
    
    ip: StringProperty(name='', update=update_querier) # pyright: ignore[reportInvalidTypeForm]
    port: StringProperty(name='', update=update_querier) # pyright: ignore[reportInvalidTypeForm]
    prefix: StringProperty(name='', update=update_querier) # pyright: ignore[reportInvalidTypeForm]
    name: StringProperty(name='', update=update_querier) # pyright: ignore[reportInvalidTypeForm]
    username: StringProperty(name='', update=update_querier) # pyright: ignore[reportInvalidTypeForm]
    password: StringProperty(name='', update=update_querier) # pyright: ignore[reportInvalidTypeForm]
    host_type: EnumProperty(name='',
        items = [(s.lower(),s,'') for s in ['PrusaLink', 'Creality', 'Moonraker', 'Mainsail']],
        update=update_querier
    ) # pyright: ignore[reportInvalidTypeForm]

def draw_list(layout: UILayout, data: bpy_prop_collection, list_id: str, fields = [], add_operator: str = '', remove_operator: str = ''):

    for idx, item in enumerate(data):
        row = layout.row(align=True)
        
        if remove_operator:
            create_operator_row(row, remove_operator, list_id, idx, 'X')

        for field in fields:
            row.prop(item, field, index=1, text="", placeholder = field)

    create_operator_row(layout, add_operator, list_id, icon="ADD")