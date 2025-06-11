from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..operators import RunSlicerOperator
    from bpy._typing.rna_enums import OperatorReturnItems
    
import bpy
import os

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
    def execute(self, context) -> set[OperatorReturnItems]:
        self.printer().pause_print()
        return {'FINISHED'}

@register_class
class ResumePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.resume_print"
    bl_label = ""
    def execute(self, context) -> set[OperatorReturnItems]:
        self.printer().resume_print()
        return {'FINISHED'}

@register_class
class StopPrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.stop_print"
    bl_label = ""
    def execute(self, context) -> set[OperatorReturnItems]:
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

            header, content = layout.panel(id, default_closed=True)
            
            #### HEADER
            
            ## BASIC STATE
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

            header.label(icon_value=get_icon(icon_label), text='')

            ## PRINTER STATUS AND CONTROL
            if not data.interface.state:
                prog_array = [id]

                progress = float(data.progress) if data.progress else 0.0

                job_name = os.path.basename(data.job_name) if data.job_name else ''
                job_name = '' if job_name == 'localhost' else job_name

                state_array = []
                if progress != 0: state_array.append(f"({progress:.0f}%)")
                if not job_name and data.state: state_array.append(data.state)
                if job_name: state_array.append(job_name)

                if len(state_array): prog_array.append(" ".join(state_array))

                prog_text = ' - '.join(prog_array)
            else:
                progress = 0
                prog_text = data.interface.state
            
            header.progress(factor=progress/100.0, text=prog_text)

            if data.host_type in ['prusalink', 'creality']:
                button_row = header.row(align=True)

                for op_pause in [('collection.pause_print', 'PAUSE'), ('collection.resume_print', 'PLAY'), ('collection.stop_print', 'SNAP_FACE')]:
                    op_pause: PausePrintOperator = button_row.operator(op_pause[0], icon=op_pause[1])
                    op_pause.target_key = id

                op: RunSlicerOperator = button_row.operator(
                    "collection.slice",
                    text="",
                    icon_value=get_icon("slice")
                )  # type: ignore
                op.mode = "slice"
                op.mountpoint = "/tmp/"
                op.target_key = id

                if data.interface.state: button_row.enabled = False