from bpy.types import Collection, UILayout

from ..registry import register
from ..classes.bpy_classes import BasePanel

from .. import TYPES_NAME

@register
class SlicerPanel_3_Stdout(BasePanel):
    bl_label = "Prusaslicer Output"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ..functions.blender_funcs import coll_from_selection

        collection: Collection | None= coll_from_selection()
        pg = getattr(collection, TYPES_NAME)

        layout = self.layout
        
        if not (output := getattr(pg, 'print_stdout')):
            return

        box: UILayout = layout.box()
        for out in output.split("\n"):
            if out:
                row = box.row()
                row.label(text=out)