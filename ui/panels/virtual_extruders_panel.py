from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import Collection, PropertyGroup, UILayout, bpy_prop_collection

from ...registry import register_class
from ... import TYPES_NAME
from ..panels.base import BasePanel

def draw_virtual_extruders_list(layout: UILayout, pg: PropertyGroup, list_id: str, cx: Collection | None = None) -> None:
    data: bpy_prop_collection = getattr(pg, list_id)
    box: UILayout = layout.box()

    for idx, item in enumerate(data):
        row = box.row(align=True)
        
        remove_sub = row.row(align=True)
        op_remove = remove_sub.operator("collection.slicer_remove_item", text="", icon="X")
        op_remove.list_id = list_id
        op_remove.item_idx = idx

        lbl_sub = row.row(align=True)
        lbl_sub.label(text=f" E{6 + idx}")
        lbl_sub.scale_x = 0.5

        cells_row = row.row(align=True)
        for i in range(5):
            cells_row.prop(item, "ratios", index=i, text="")

    if cx is not None:
        from ...infra.blender_bridge import get_inherited_virtual_extruders
        inherited_ve = [ve for ve in get_inherited_virtual_extruders(cx, TYPES_NAME) if ve.get('inherited')]
        for ve in inherited_ve:
            row = box.row(align=True)
            lbl_ic = row.row(align=True)
            lbl_ic.label(text="", icon="RNA")
            
            lbl_sub = row.row(align=True)
            lbl_sub.label(text=f" E{ve['id']}")
            lbl_sub.scale_x = 0.5

            cells_row = row.row(align=True)
            cells_row.enabled = False
            for r in ve['ratios']:
                cells_row.label(text=f"{r:.2f}")

    row = box.row()
    op_add = row.operator("collection.slicer_add_item", text="Add Virtual Extruder", icon="ADD")
    op_add.list_id = list_id

@register_class
class SlicerPanel_2_VirtualExtruders(BasePanel):
    bl_label = "Virtual Extruders"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ...infra.blender_bridge import coll_from_selection

        collection: Collection | None = coll_from_selection()
        layout = self.layout
        if not layout: return

        if not collection:
            layout.row().label(text="Select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        draw_virtual_extruders_list(layout, pg, "virtual_extruders", cx=collection)
