from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import Collection

import bpy
from ...registry import register_class
from ... import TYPES_NAME
from ..panels.base import BasePanel

@register_class
class SlicerPanel_3_WipeTower(BasePanel):
    bl_label = "Wipe Tower"
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

        layout.prop(pg, "wipe_tower_mode", text="Source")

        if pg.wipe_tower_mode == 'AUTO':
            layout.label(text="Places wipe tower 2cm above top-left of object", icon='INFO')
        elif pg.wipe_tower_mode == 'COORDINATES':
            col = layout.column(align=True)
            col.prop(pg, "wipe_tower_location", text="Location")
            col.prop(pg, "wipe_tower_rotation", text="Rotation")
        elif pg.wipe_tower_mode == 'OBJECT':
            layout.prop(pg, "wipe_tower_object", text="Object")
            if pg.wipe_tower_object:
                box = layout.box()
                col = box.column(align=True)
                col.enabled = False
                col.label(text=f"Target: {pg.wipe_tower_object.name}", icon='OBJECT_DATA')
                col.prop(pg.wipe_tower_object, "location", index=0, text="Location X")
                col.prop(pg.wipe_tower_object, "location", index=1, text="Location Y")
                col.prop(pg.wipe_tower_object, "rotation_euler", index=2, text="Rotation Z")
