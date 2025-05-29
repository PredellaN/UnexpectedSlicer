import bpy
import os

from ..operators import RunSlicerOperator

from ..registry import register_class
from ..classes.bpy_classes import BasePanel

from .. import TYPES_NAME

class PrinterData():
    target_key: bpy.props.StringProperty()
    def printer(self):
        from ..classes.physical_printer_classes import printers_querier
        return printers_querier.printers[self.target_key]

@register_class
class PausePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.pause_print"
    bl_label = ""
    def execute(self, context) -> set[str]: #type: ignore
        self.printer().pause_print()
        return {'FINISHED'}

@register_class
class ResumePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.resume_print"
    bl_label = ""
    def execute(self, context) -> set[str]: #type: ignore
        self.printer().resume_print()
        return {'FINISHED'}

@register_class
class StopPrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.stop_print"
    bl_label = ""
    def execute(self, context) -> set[str]: #type: ignore
        self.printer().stop_print()
        return {'FINISHED'}

@register_class
class SlicerPanel_4_Printers(BasePanel):
    bl_label = "Physical Printers"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ..registry import get_icon
        from ..classes.physical_printer_classes import printers_querier

        layout = self.layout

        for id, data in printers_querier.printers.items():
            
            state = data.state
            icon_map = {
                'BUSY':      'activity_yellow',
                'PAUSED':    'activity_yellow',
                'ATTENTION': 'activity_red',
                'ERROR':     'activity_red',
                'PRINTING':  'activity_green',
                'IDLE':      'activity_blue',
                'FINISHED':  'activity_blue',
                'READY':     'activity_blue',
                'STANDBY':   'activity_blue',
                'STOPPED':   'activity_blue',
            }

            icon_label = icon_map.get(state, 'activity_gray')

            row = layout.row(align=True)

            row.label(icon_value=get_icon(icon_label))
            row.label(text=id)

            progress = float(data.progress) if data.progress else 0.0

            raw = data.job_name or ''
            job_name = os.path.basename(raw) if raw else ''
            job_name = '' if job_name == 'localhost' else job_name

            prog_label = '' if progress == 0 else f"({progress:.0f}%) "
            state_label = data.state if not job_name else f" {job_name}"

            prog_text = prog_label + state_label if not data.interface.state else data.interface.state

            sub = row.row(align=True)
            sub.scale_x = 2.5
            sub.progress(factor=progress/100.0, text=prog_text)

            if data.host_type in ['prusalink', 'creality']:
                sub = row.row(align=True)

                for op in [('collection.pause_print', 'PAUSE'), ('collection.resume_print', 'PLAY'), ('collection.stop_print', 'SNAP_FACE')]:
                    op: PausePrintOperator = sub.operator(op[0], icon=op[1]) #type: ignore
                    op.target_key = id

                op: RunSlicerOperator = sub.operator(
                    "collection.slice",
                    text="",
                    icon_value=get_icon("slice")
                )  # type: ignore
                op.mode = "slice"
                op.mountpoint = "/tmp/"
                op.target_key = id

                if data.interface.state: sub.enabled = False