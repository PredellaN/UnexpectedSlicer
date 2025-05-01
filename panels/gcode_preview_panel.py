import bpy
import os
from bpy.props import FloatVectorProperty, StringProperty
from bpy.types import Collection

from .. import TYPES_NAME
from ..functions.bpy_classes import BasePanel
from ..functions.draw_gcode import SegmentDraw
from ..functions.blender_funcs import coll_from_selection

drawer: SegmentDraw = SegmentDraw()

class PreviewGcodeOperator(bpy.types.Operator):
    bl_idname = f"collection.preview_gcode"
    bl_label = "Preview Gcode"

    action: StringProperty()
    current_gcode: StringProperty()
    transform: FloatVectorProperty()

    def execute(self, context) -> set[str]: #type: ignore

        if self.action == 'start':
            drawer.draw(self.current_gcode, self.transform)

        if self.action == 'stop':
            drawer.stop()

        return {'FINISHED'}

class SlicerPanel_2_Gcode_Preview(BasePanel):
    bl_label = "Gcode Preview"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Gcode_Preview"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        layout = self.layout
        row = layout.row()

        collection: Collection | None = coll_from_selection()
        pg = getattr(collection, TYPES_NAME)

        if os.path.exists(pg.print_gcode):
            op_preview: PreviewGcodeOperator = row.operator("collection.preview_gcode") #type: ignore
            op_preview.action = 'start'
            op_preview.current_gcode = pg.print_gcode
            op_preview.transform = pg.print_center

        op_cancel: PreviewGcodeOperator = row.operator("collection.preview_gcode", text="Clear Preview") #type: ignore
        op_cancel.action = 'stop'