
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.stub_internal.rna_enums import OperatorReturnItems

from bpy.types import Context, bpy_struct, Operator
from bpy.props import StringProperty, IntProperty

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

    list_id: StringProperty() # pyright: ignore[reportInvalidTypeForm]

    def execute(self, context: Context)-> set[OperatorReturnItems]:
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.add()
        self.trigger(context)
        return {'FINISHED'}
class ParamRemoveOperator(BaseOperator):
    bl_idname = f"none.generic_remove_operator"
    bl_label = "Remove Parameter"

    item_idx: IntProperty() # pyright: ignore[reportInvalidTypeForm]
    list_id: StringProperty() # pyright: ignore[reportInvalidTypeForm]

    def execute(self, context: Context) -> set[OperatorReturnItems]: 
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        self.trigger(context)
        return {'FINISHED'}

class ParamTransferOperator(BaseOperator):
    bl_idname = f"none.generic_transfer_operator"
    bl_label = "Transfer Parameter"

    target_key: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    target_list: StringProperty() # pyright: ignore[reportInvalidTypeForm]

    def execute(self, context: Context) -> set[OperatorReturnItems]:
        prop_group = self.get_pg(context)

        target_list = getattr(prop_group, f'{self.target_list}')
        item = target_list.add()
        item.param_id = self.target_key
        self.trigger(context)
        return {'FINISHED'}

class ResetSearchTerm():
    def trigger(self, context: Context):
        pg = getattr(self, 'get_pg')(context)
        pg.search_term = ""