import bpy
import os
from bpy.props import FloatVectorProperty, StringProperty
from bpy.types import Collection

from .. import TYPES_NAME
from ..functions.bpy_classes import BasePanel
from ..functions.draw_gcode import GcodeDraw
from ..functions.blender_funcs import coll_from_selection

drawer: GcodeDraw = GcodeDraw()

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
        workspace = bpy.context.workspace
        ws_pg = getattr(workspace, TYPES_NAME)

        if os.path.exists(pg.print_gcode):
            op_preview: PreviewGcodeOperator = row.operator("collection.preview_gcode") #type: ignore
            op_preview.action = 'start'
            op_preview.current_gcode = pg.print_gcode
            op_preview.transform = pg.print_center

        op_cancel: PreviewGcodeOperator = row.operator("collection.preview_gcode", text="Clear Preview") #type: ignore
        op_cancel.action = 'stop'

        row = layout.row()
        row.prop(ws_pg, 'gcode_preview_min_z')
        row.prop(ws_pg, 'gcode_preview_max_z')

        layout.prop(ws_pg, 'gcode_perimeter')
        layout.prop(ws_pg, 'gcode_external_perimeter')
        layout.prop(ws_pg, 'gcode_overhang_perimeter')
        layout.prop(ws_pg, 'gcode_internal_infill')
        layout.prop(ws_pg, 'gcode_solid_infill')
        layout.prop(ws_pg, 'gcode_top_solid_infill')
        layout.prop(ws_pg, 'gcode_bridge_infill')
        layout.prop(ws_pg, 'gcode_skirt_brim')
        layout.prop(ws_pg, 'gcode_custom')
        layout.prop(ws_pg, 'gcode_support_material')
        layout.prop(ws_pg, 'gcode_support_material_interface')