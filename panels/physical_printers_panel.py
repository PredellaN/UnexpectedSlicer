import bpy

from ..functions.physical_printers.host_query import process_printers
from ..classes.bpy_classes import BasePanel

from .. import TYPES_NAME, PACKAGE

printers_data = {}

class PhysicalPrintersPollOperator(bpy.types.Operator):
    bl_idname = f"collection.poll_printers"
    bl_label = ""

    def execute(self, context) -> set[str]: #type: ignore
        prefs = bpy.context.preferences.addons[PACKAGE].preferences

        global printers_data
        printers_data = process_printers(prefs.physical_printers)

        return {'FINISHED'}

class PausePrintOperator(bpy.types.Operator):
    bl_idname = f"collection.pause_print"
    bl_label = ""

    target_key: bpy.props.StringProperty()

    def execute(self, context) -> set[str]: #type: ignore
        global printers_data
        printer = printers_data[self.target_key]
        print(printer)
        return {'FINISHED'}

class SlicerPanel_4_Printers(BasePanel):
    bl_label = "Physical Printers"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ..functions.icon_provider import icons

        layout = self.layout
        
        layout.operator("collection.poll_printers", icon = 'FILE_REFRESH')

        for id, data in printers_data.items():
            icon_label = 'activity_gray'
            if data.get('state') in ['BUSY', 'PAUSED', 'STOPPED']:
                icon_label = 'activity_gray'
            if data.get('state') in ['ATTENTION', 'ERROR']:
                icon_label = 'activity_red'
            if data.get('state') in ['PRINTING']:
                icon_label = 'activity_green'
            if data.get('state') in ['IDLE', 'FINISHED', 'READY', 'STANDBY']:
                icon_label = 'activity_blue'

            row = layout.row(align=True)
            row.label(icon_value=icons[icon_label])
            row.label(text=id)

            progress = float(data['progress']) if data['progress'] else 0.0
            prog_text = data.get('state')
            if prog_text == 'PRINTING':
                prog_text += f" ({progress:.0f}%)"

            # put only the progress bar in a sub-row and scale it
            sub = row.row(align=True)
            sub.scale_x = 2.0     # make it twice as wide
            sub.progress(factor=progress/100.0, text=prog_text)

            sub = row.row(align=True)
            op: PausePrintOperator = sub.operator("collection.pause_print", icon='PAUSE') #type: ignore
            op.target_key = id