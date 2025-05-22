import bpy
from bpy.types import UILayout, bpy_prop_collection
from bpy.props import EnumProperty, StringProperty

from ..registry import register

from ..classes.bpy_classes import ParamRemoveOperator, ParamAddOperator
from ..classes.py_classes import FromPreferences
from ..panels.ui_elements.operators import create_operator_row

@register
class RemovePrefItemOperator(FromPreferences, ParamRemoveOperator):
    bl_idname = "preferences.printers_remove_item"
    bl_label = ""

@register
class AddPrefItemOperator(FromPreferences, ParamAddOperator):
    bl_idname = "preferences.printers_add_item"

@register
class PrintersListItem(bpy.types.PropertyGroup):
    param_id: StringProperty(name='')
    
    ip: StringProperty(name='')
    port: StringProperty(name='')
    name: StringProperty(name='')
    username: StringProperty(name='')
    password: StringProperty(name='')
    host_type: EnumProperty(name='',
        items = [(s.lower(),s,'') for s in ['PrusaLink', 'Creality', 'Moonraker', 'Mainsail']]
    )

def draw_list(layout: UILayout, data: bpy_prop_collection, list_id: str, fields = [], add_operator: str = '', remove_operator: str = ''):

    for idx, item in enumerate(data):
        row = layout.row(align=True)
        
        if remove_operator:
            create_operator_row(row, remove_operator, list_id, idx, 'X')

        for field in fields:
            row.prop(item, field, index=1, text="", placeholder = field)

    create_operator_row(layout, add_operator, list_id, icon="ADD")