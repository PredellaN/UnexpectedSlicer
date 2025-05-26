import bpy
from bpy.types import UILayout, bpy_prop_collection
from bpy.props import EnumProperty, StringProperty

from ..registry import register_class

from ..functions.blender_funcs import collection_to_dict_list
from ..classes.bpy_classes import ParamRemoveOperator, ParamAddOperator
from ..classes.py_classes import FromPreferences
from ..panels.ui_elements.operators import create_operator_row

from .. import PACKAGE

@register_class
class RemovePrefItemOperator(FromPreferences, ParamRemoveOperator):
    bl_idname = "preferences.printers_remove_item"
    bl_label = ""

@register_class
class AddPrefItemOperator(FromPreferences, ParamAddOperator):
    bl_idname = "preferences.printers_add_item"

@register_class
class PrintersListItem(bpy.types.PropertyGroup):
    def update_querier(self, context):
        from ..classes.physical_printer_classes import printers_querier
        prefs = bpy.context.preferences.addons[PACKAGE].preferences
        printers_seralized = collection_to_dict_list(prefs.physical_printers)
        printers_querier.set_printers(printers_seralized)
        pass

    param_id: StringProperty(name='')
    
    ip: StringProperty(name='', update=update_querier)
    port: StringProperty(name='', update=update_querier)
    name: StringProperty(name='', update=update_querier)
    username: StringProperty(name='', update=update_querier)
    password: StringProperty(name='', update=update_querier)
    host_type: EnumProperty(name='',
        items = [(s.lower(),s,'') for s in ['PrusaLink', 'Creality', 'Moonraker', 'Mainsail']],
        update=update_querier
    )

def draw_list(layout: UILayout, data: bpy_prop_collection, list_id: str, fields = [], add_operator: str = '', remove_operator: str = ''):

    for idx, item in enumerate(data):
        row = layout.row(align=True)
        
        if remove_operator:
            create_operator_row(row, remove_operator, list_id, idx, 'X')

        for field in fields:
            row.prop(item, field, index=1, text="", placeholder = field)

    create_operator_row(layout, add_operator, list_id, icon="ADD")