import bpy
import os

from ..operators import RunSlicerOperator

from ..registry import register
from ..functions.physical_printers.host_functions import pause_print, resume_print, stop_print
from ..classes.bpy_classes import BasePanel

from .. import TYPES_NAME

class PrinterData():
    target_key: bpy.props.StringProperty()
    def printer(self):
        from ..functions.physical_printers.host_query import printers_querier
        return printers_querier.data[self.target_key]

@register
class PausePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.pause_print"
    bl_label = ""
    def execute(self, context) -> set[str]: #type: ignore
        pause_print(self.printer())
        return {'FINISHED'}

@register
class ResumePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.resume_print"
    bl_label = ""
    def execute(self, context) -> set[str]: #type: ignore
        resume_print(self.printer())
        return {'FINISHED'}

@register
class StopPrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.stop_print"
    bl_label = ""
    def execute(self, context) -> set[str]: #type: ignore
        stop_print(self.printer())
        return {'FINISHED'}

@register
class SlicerPanel_4_Printers(BasePanel):
    bl_label = "Physical Printers"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ..functions.icon_provider import icons
        from ..functions.physical_printers.host_query import printers_querier

        layout = self.layout

        for id, data in printers_querier.data.items():
            icon_label = 'activity_gray'
            if data.get('state') in ['BUSY', 'PAUSED', 'STOPPED']:
                icon_label = 'activity_gray'
            if data.get('state') in ['ATTENTION', 'ERROR']:
                icon_label = 'activity_red'
            if data.get('state') in ['PRINTING']:
                icon_label = 'activity_green'
            if data.get('state') in ['IDLE', 'FINISHED', 'READY', 'STANDBY', 'STOPPED']:
                icon_label = 'activity_blue'

            row = layout.row(align=True)

            row.label(icon_value=icons[icon_label])
            row.label(text=id)

            progress = float(data['progress']) if data['progress'] else 0.0

            raw = data.get('job_name', '') or ''
            job_name = os.path.basename(raw) if raw else ''
            job_name = '' if job_name == 'localhost' else job_name

            prog_label = '' if progress == 0 else f"({progress:.0f}%) "
            state_label = data.get('state', '') if not job_name else f" {job_name}"

            prog_text = prog_label + state_label

            # put only the progress bar in a sub-row and scale it
            sub = row.row(align=True)
            sub.scale_x = 2.5     # make it twice as wide
            sub.progress(factor=progress/100.0, text=prog_text)

            if data['host_type'] in ['prusalink', 'creality']:
                sub = row.row(align=True)
                op: PausePrintOperator = row.operator("collection.pause_print", icon='PAUSE') #type: ignore
                op.target_key = id

                sub = row.row(align=True)
                op: PausePrintOperator = row.operator("collection.resume_print", icon='PLAY') #type: ignore
                op.target_key = id

                sub = row.row(align=True)
                op: StopPrintOperator = row.operator("collection.stop_print", icon='SNAP_FACE') #type: ignore
                op.target_key = id

                op: RunSlicerOperator = row.operator(
                    "collection.slice",
                    text="",
                    icon_value=icons["slice"]
                )  # type: ignore
                op.mode = "slice"
                op.mountpoint = "/tmp/"
                op.target_key = id

        printers_querier.query()