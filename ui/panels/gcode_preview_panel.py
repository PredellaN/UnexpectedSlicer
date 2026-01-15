from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Collection
    from bpy.stub_internal.rna_enums import OperatorReturnItems
    
import bpy
import os
from bpy.props import FloatVectorProperty, StringProperty

from ...registry import register_class

from ... import TYPES_NAME
from ..panels.base import BasePanel
from ..gcode_preview import drawer
from ...infra.blender_bridge import coll_from_selection

metadata = {}

@register_class
class StopPreviewGcodeOperator(bpy.types.Operator):
    bl_idname = f"collection.stop_preview_gcode"
    bl_label = "Preview Gcode"

    action: StringProperty()
    current_gcode: StringProperty()
    transform: FloatVectorProperty()

    def execute(self, context) -> set['OperatorReturnItems']:
        drawer.stop()

        return {'FINISHED'}

@register_class
class SlicerPanel_2_Gcode_Preview(BasePanel):
    bl_label = "Gcode Preview"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):

        layout = self.layout
        if not layout: return
        
        row = layout.row()

        collection: Collection | None = coll_from_selection()
        pg = getattr(collection, TYPES_NAME)
        workspace = bpy.context.workspace
        ws_pg = getattr(workspace, TYPES_NAME)

        if pg_metadata := pg.get('metadata'):
            if os.path.exists(pg_metadata['gcode_path']):
                global metadata
                metadata = pg_metadata
                
                if '.bgcode' in pg_metadata['gcode_path']:
                    row.label(text="Preview is only supported with non-binary gcode!")
                    row = layout.row()

        row = layout.row()

        row.prop(ws_pg, 'gcode_preview_view')
        
        row.prop(ws_pg, 'gcode_preview_min_z', slider=True)
        row.prop(ws_pg, 'gcode_preview_max_z', slider=True)

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
        layout.prop(ws_pg, 'gcode_gap_fill')