from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.stub_internal.rna_enums import OperatorReturnItems

from bpy.types import Context, bpy_struct, Panel, Operator
from bpy.props import StringProperty, IntProperty

from ..registry import register_class
from ..classes.py_classes import FromObject, FromCollection, ResetSearchTerm

class BasePanel(Panel):
    bl_label = "Default Panel"
    bl_idname = "COLLECTION_PT_BasePanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context: Context):
        pass

class BaseOperator(Operator):
    bl_idname = f"none.generic_operator"
    bl_label = ""

    def execute(self, context: Context)-> set[OperatorReturnItems]:
        return {'FINISHED'}

    def get_pg(self, context: Context) -> bpy_struct | None:
        pass

    def trigger(self, context: Context) -> None:
        pass

class ParamAddOperator(BaseOperator):
    bl_idname = f"none.generic_add_operator"
    bl_label = "Add Parameter"

    list_id: StringProperty()

    def execute(self, context: Context)-> set[OperatorReturnItems]:
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.add()
        self.trigger(context)
        return {'FINISHED'}
class ParamRemoveOperator(BaseOperator):
    bl_idname = f"none.generic_remove_operator"
    bl_label = "Remove Parameter"

    item_idx: IntProperty()
    list_id: StringProperty()

    def execute(self, context: Context) -> set[OperatorReturnItems]: 
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        self.trigger(context)
        return {'FINISHED'}

class ParamTransferOperator(BaseOperator):
    bl_idname = f"none.generic_transfer_operator"
    bl_label = "Transfer Parameter"

    target_key: StringProperty()
    target_list: StringProperty()

    def execute(self, context: Context) -> set[OperatorReturnItems]:
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