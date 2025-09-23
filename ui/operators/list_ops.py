from ...registry import register_class

from .common import ParamRemoveOperator, ParamAddOperator, ParamTransferOperator, ResetSearchTerm
from ..mixins import FromObject, FromCollection 

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