from __future__ import annotations

from ...registry import register_class
from ..panels.base import BasePanel
from ... import TYPES_NAME

from typing import TypeAlias
import bpy

Collection: TypeAlias = "bpy.types.Collection"
UILayout:    TypeAlias = "bpy.types.UILayout"
Context:     TypeAlias = "bpy.types.Context"

@register_class
class SlicerPanel_3_Stdout(BasePanel):
    bl_label = "Prusaslicer Output"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    # no run-time import; Pyright resolves the string
    def draw(self, context: "bpy.types.Context") -> None:          # or 'bpy.types.Context'
        from ...infra.blender_bridge import coll_from_selection

        collection: Collection | None = coll_from_selection()
        if not collection:
            return

        pg = getattr(collection, TYPES_NAME)
        layout = self.layout
        if not layout:
            return

        output: str | None = getattr(pg, "print_stdout", None)
        if not output:
            return

        box: UILayout = layout.box()
        for line in output.splitlines():
            if line:
                box.row().label(text=line)
