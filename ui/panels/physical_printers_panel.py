from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ui.operators.slicer import RunSlicerOperator
    from bpy.stub_internal.rna_enums import OperatorReturnItems

import bpy
import os

from ...registry import register_class
from ..panels.base import BasePanel

from ... import TYPES_NAME

class PrinterData():
    target_key: bpy.props.StringProperty()
    def printer(self):
        from ...services.physical_printers import printers_querier
        return printers_querier._printers[self.target_key]

@register_class
class PausePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.pause_print"
    bl_label = ""
    def execute(self, context) -> set['OperatorReturnItems']:
        self.printer().backend.pause()
        return {'FINISHED'}

@register_class
class ResumePrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.resume_print"
    bl_label = ""
    def execute(self, context) -> set['OperatorReturnItems']:
        self.printer().backend.resume()
        return {'FINISHED'}

@register_class
class StopPrintOperator(bpy.types.Operator, PrinterData):
    bl_idname = f"collection.stop_print"
    bl_label = ""
    def execute(self, context) -> set['OperatorReturnItems']:
        self.printer().backend.stop()
        return {'FINISHED'}

@register_class
class WM_OT_copy_to_clipboard(bpy.types.Operator):
    bl_idname = "wm.copy_to_clipboard"
    bl_label = ""
    bl_description = "Copy address to clipboard"
    text: bpy.props.StringProperty()

    def execute(self, context)-> set['OperatorReturnItems']:
        context.window_manager.clipboard = self.text #type: ignore
        self.report(type={'INFO'}, message="Copied to clipboard")
        return {'FINISHED'}

@register_class
class SlicerPanel_4_Printers(BasePanel):
    bl_label = "Physical Printers"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ...registry import get_icon
        from ...services.physical_printers import printers_querier

        layout = self.layout
        if not layout: return

        for id, printer in printers_querier._printers.items():
            
            header, content = layout.panel(idname=id, default_closed=True)

            if content:
                if printer.last_error:
                    row = content.row()
                    content.label(text=f"Error: {printer.last_error}")

                if (printer.last_command_time and printer.last_command_response):
                    row = content.row()
                    content.label(text=f"{printer.last_command_time.strftime('%Y-%m-%d %H:%M:%S')} - {printer.last_command_response}")
                    
                box = content.box()

                if printer.status.nozzle_temperature or printer.status.bed_temperature:
                    row = box.row()
                    row.label(icon_value=get_icon('nozzle.png'), text=f"Nozzle temperature: {printer.status.nozzle_temperature}C")
                    row = box.row()
                    row.label(icon_value=get_icon('plate.png'), text=f"Bed temperature: {printer.status.bed_temperature}C")
                
                if printer.status.nozzle_diameter:
                    row = box.row()
                    row.label(icon_value=get_icon('nozzle_size.png'), text=f"Nozzle diameter: {printer.status.nozzle_diameter}")

                row = box.row()
                addr = printer.backend.base
                op2: WM_OT_copy_to_clipboard = row.operator("wm.copy_to_clipboard", text='', icon='NETWORK_DRIVE')
                op2.text = addr + '/'
                row.label(text='Printer Address: ' + addr)
                
            #### HEADER
            
            ## BASIC STATE
            printer_state = printer.status.state
            icon_map: dict[str, str] = {
                'BUSY':      'activity_yellow.png',
                'PAUSED':    'activity_yellow.png',
                'ATTENTION': 'activity_red.png',
                'ERROR':     'activity_red.png',
                'PRINTING':  'activity_green.png',
                'IDLE':      'activity_blue.png',
                'FINISHED':  'activity_blue.png',
                'READY':     'activity_blue.png',
                'STANDBY':   'activity_blue.png',
                'STOPPED':   'activity_blue.png',
            }

            icon_label = icon_map.get(printer_state, 'activity_gray.png')

            header.label(icon_value=get_icon(icon_label), text='')

            prog_array = [id]

            ## PRINTER STATUS AND CONTROL

            job_name: str = os.path.basename(printer.status.job_name)
            job_name = '' if job_name == 'localhost' else job_name
            prog_array += [job_name] if job_name else [printer_state]

            progress: float = printer.status.progress
            if progress or job_name:
                prog_array += [f"({progress:.0f}%)"]

            header.progress(factor=progress/100.0, text=printer.backend.api_state if printer.backend.api_state else ' - '.join(prog_array))

            button_row = header.row(align=True)

            for op_pause in [('collection.pause_print', 'PAUSE'), ('collection.resume_print', 'PLAY'), ('collection.stop_print', 'SNAP_FACE')]:
                op_pause: PausePrintOperator = button_row.operator(op_pause[0], icon=op_pause[1])
                op_pause.target_key = id

            op: RunSlicerOperator = button_row.operator(
                "collection.slice",
                text="",
                icon_value=get_icon("slice.png")
            )
            op.mode = "slice"
            op.mountpoint = "/tmp/"
            op.target_key = id

            if printer.status.state == 'OFFLINE': button_row.enabled = False            