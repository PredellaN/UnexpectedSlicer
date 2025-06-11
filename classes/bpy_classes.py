from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy._typing.rna_enums import OperatorReturnItems

import bpy

from ..registry import register_class
from ..classes.py_classes import FromObject, FromCollection, ResetSearchTerm

class BasePanel(bpy.types.Panel):
    bl_label = "Default Panel"
    bl_idname = "COLLECTION_PT_BasePanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        pass

class BaseOperator(bpy.types.Operator):
    bl_idname = f"none.generic_operator"
    bl_label = ""

    def execute(self, context)-> set[OperatorReturnItems]:
        return {'FINISHED'}

    def get_pg(self, context):
        pass

    def trigger(self, context):
        pass

class ParamAddOperator(BaseOperator):
    bl_idname = f"none.generic_add_operator"
    bl_label = "Add Parameter"

    list_id: bpy.props.StringProperty()

    def execute(self, context)-> set[OperatorReturnItems]:
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.add()
        self.trigger(context)
        return {'FINISHED'}

class ParamRemoveOperator(BaseOperator):
    bl_idname = f"none.generic_remove_operator"
    bl_label = "Remove Parameter"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()

    def execute(self, context) -> set[OperatorReturnItems]: 
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        self.trigger(context)
        return {'FINISHED'}

class ParamTransferOperator(BaseOperator):
    bl_idname = f"none.generic_transfer_operator"
    bl_label = "Transfer Parameter"

    target_key: bpy.props.StringProperty()
    target_list: bpy.props.StringProperty()

    def execute(self, context) -> set[OperatorReturnItems]:
        prop_group = self.get_pg(context)

        target_list = getattr(prop_group, f'{self.target_list}')
        item = target_list.add()
        item.param_id = self.target_key
        self.trigger(context)
        return {'FINISHED'}

@register_class
class RemoveObjectItemOperator(FromObject, ParamRemoveOperator):
    bl_idname = "object.slicer_remove_item"
    bl_label = ""

@register_class
class AddObjectItemOperator(FromObject, ParamAddOperator):
    bl_idname = "object.slicer_add_item"

@register_class
class RemoveItemOperator(FromCollection, ParamRemoveOperator):
    bl_idname = f"collection.slicer_remove_item"
    bl_label = ""

@register_class
class AddItemOperator(FromCollection, ParamAddOperator):
    bl_idname = f"collection.slicer_add_item"

@register_class
class TransferModItemOperator(FromObject, ResetSearchTerm, ParamTransferOperator):
    bl_idname = f"object.list_transfer_item"

@register_class
class TransferItemOperator(FromCollection, ResetSearchTerm, ParamTransferOperator):
    bl_idname = f"collection.list_transfer_item"