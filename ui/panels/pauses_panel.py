from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..operators.common import ParamRemoveOperator, ParamAddOperator
    from bpy.types import PropertyGroup, Collection, UILayout, bpy_prop_collection

from ...registry import register_class

from ..panels.base import BasePanel

from ... import TYPES_NAME

def draw_pause_list(layout: UILayout, pg: PropertyGroup, list_id: str) -> None:
    data: bpy_prop_collection = getattr(pg, list_id)
    box: UILayout = layout.box()

    for idx, item in enumerate(data):
        row = box.row()
        # Draw remove operator for each pause/gcode entry
        op_remove: ParamRemoveOperator = row.operator("collection.slicer_remove_item", text="", icon="X")  # type: ignore
        op_remove.list_id = list_id
        op_remove.item_idx = idx

        # Draw enum for pause type
        row.prop_menu_enum(item, "param_type", icon="DOWNARROW_HLT")
        
        # Depending on the parameter type, draw corresponding UI element
        if item.param_type == "custom_gcode":
            row.prop(item, "param_cmd")
        else:
            label_map = {"pause": "Pause", "color_change": "Color Change"}
            row.label(text=label_map.get(item.param_type, ""))
        
        # Draw value type and value properties
        subrow = row.row(align=True)
        subrow.prop(item, 'param_value_type')
        subrow.prop(item, "param_float" if item.param_value_type == 'height' else "param_int", text="")

    row = box.row()
    op_add: ParamAddOperator = row.operator("collection.slicer_add_item")  # type: ignore
    op_add.list_id = list_id

@register_class
class SlicerPanel_1_Pauses(BasePanel):
    bl_label = "Pauses, Color Changes and Custom Gcode"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ...infra.blender_bridge import coll_from_selection

        collection: Collection | None = coll_from_selection()
        layout = self.layout
        if not layout: return

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)

        draw_pause_list(layout, pg, "pause_list")