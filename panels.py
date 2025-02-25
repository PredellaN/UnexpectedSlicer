from typing import Any
from bpy.types import PropertyGroup, Collection, UILayout
import bpy

from .operators import RunPrusaSlicerOperator, UnmountUsbOperator
from .functions.basic_functions import (
    BasePanel,
    ParamRemoveOperator,
    ParamAddOperator,
    ParamRemoveOperator,
    ParamTransferOperator,
    is_usb_device
)
from .functions.blender_funcs import coll_from_selection, get_inherited_overrides, get_inherited_slicing_props
from . import TYPES_NAME

class ItemRemoveOperator(ParamRemoveOperator):
    bl_idname = f"{TYPES_NAME}.list_remove_item"
    bl_label = "Remove Item"
    def get_pg(self):
        cx: Collection | None = coll_from_selection()
        return getattr(cx, TYPES_NAME)

class AddItemOperator(ParamAddOperator):
    bl_idname = f"{TYPES_NAME}.list_add_item"
    bl_label = "Add Parameter"
    def get_pg(self):
        cx: Collection | None = coll_from_selection()
        return getattr(cx, TYPES_NAME)

class TransferItemOperator(ParamTransferOperator):
    bl_idname = f"{TYPES_NAME}.list_transfer_item"
    bl_label = "Add Parameter"
    def get_pg(self):
        cx: Collection | None = coll_from_selection()
        return getattr(cx, TYPES_NAME)

    def trigger(self):
        pg = self.get_pg()
        pg.search_term = ""

def draw_conf_dropdown(pg, layout, key, prop):
    row = layout.row()
    
    # Label row
    sub_row = row.row()
    sub_row.label(text=f"{prop['type'].capitalize()}:")
    sub_row.scale_x = 0.5

    # Property row
    sub_row = row.row()
    sub_row.prop(pg, f'{key}_enum', text='')
    sub_row.scale_x = 2 if not prop['inherited'] else 0.1

    if prop['inherited']:
        sub_row = row.row()
        sub_row.label(text=f"Inherited: {prop['prop'].split(':')[1]}")
        sub_row.scale_x = 1.9

class PrusaSlicerPanel(BasePanel):
    bl_label = "Blender to PrusaSlicer"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        cx: Collection | None = coll_from_selection()

        pg = getattr(cx, TYPES_NAME)

        layout = self.layout
        row = layout.row()

        if not cx:
            row.label(text=f"Please select a collection")
            return

        row.label(text=f"Slicing settings for Collection '{cx.name}'")

        cx_props: dict[str, [str, bool]] = get_inherited_slicing_props(cx, TYPES_NAME)

        for key, prop in cx_props.items():
            draw_conf_dropdown(pg, layout, key, prop)

        row = layout.row()
        
        sliceable = all([v.get('prop') for k,v in cx_props.items()])
        slice_buttons: list[tuple[str, str]] = [("Slice", "slice"), ("Slice and Preview", "slice_and_preview")] + [("Open with PrusaSlicer", "open")] if sliceable else []
        if sliceable:
            for label, idx in slice_buttons:
                op: RunPrusaSlicerOperator = row.operator(f"export.slice", text=label, icon="ALIGN_JUSTIFY") #type: ignore
                op.mode=idx
                op.mountpoint=""

        if pg.print_time:
            row = layout.row()
            row.label(text=f"Printing time: {pg.print_time}")
        if pg.print_weight:
            row = layout.row()
            row.label(text=f"Print weight: {pg.print_weight}g")

        row = layout.row()
        row.prop(pg, "progress", text=pg.progress_text, slider=True)
        row.enabled = False

        ### USB Devices
        import psutil #type: ignore
        partitions= psutil.disk_partitions()

        for partition in partitions:
            if is_usb_device(partition):
                row = layout.row()
                row.label(text="Detected USB Devices:")
                break

        for partition in partitions:
            if is_usb_device(partition):
                row = layout.row()
                mountpoint = partition.mountpoint
                row.enabled = False if pg.running else True

                op_unmount_usb: UnmountUsbOperator = row.operator(f"export.unmount_usb", text="", icon='UNLOCKED') #type: ignore
                op_unmount_usb.mountpoint=mountpoint

                op_slice_usb: RunPrusaSlicerOperator = row.operator(f"export.slice", text="", icon='DISK_DRIVE') #type: ignore
                op_slice_usb.mountpoint=mountpoint
                op_slice_usb.mode = "slice"
                
                row.label(text=f"{mountpoint.split('/')[-1]} mounted at {mountpoint} ({partition.device})")

def draw_list(layout: UILayout, pg: PropertyGroup, data: list[dict[str, Any]], icon = None, add_list_id = None, operators: list[dict[str, [str, str]]] = []):
    box = layout.box()

    for item in data:
        row = box.row(align=True)
        list_id = item.get('list_id', None)

        if list_id and not item['readonly']:
            for op in operators:
                current_op = row.operator(f"{TYPES_NAME}.{op['id']}", text = "", icon=op['icon']) #type: ignore
                current_op.list_id = item['list_id'] #type: ignore
                current_op.item_idx = item['idx'] #type: ignore
                if params := op.get('params'):
                    for key, param in params.items():
                        setattr(current_op, key, param)
            
            item_list = getattr(pg, list_id)
            item_id = item_list[item['idx']]
            prop = row.prop(item_id, 'param_id', index=1, text="")
            prop = row.prop(item_id, 'param_value', index=1, text="")
        else:
            if icon:
                row.label(icon=icon) #type: ignore
            row.label(text=f"{item['key']}")
            row.label(text=str(item.get('value', None)))
            
    if add_list_id:
        row = box.row()
        op_add_param: AddItemOperator = row.operator(f"{TYPES_NAME}.list_add_item") #type: ignore
        op_add_param.list_id=f"{add_list_id}"

class SlicerPanel_0_Overrides(BasePanel):
    bl_label = "Configuration Overrides"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Overrides"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"
    search_list_id = f"search_list"
    list_id = f"list"

    def draw(self, context):
        cx: Collection | None = coll_from_selection()
        pg = getattr(cx, TYPES_NAME)

        layout = self.layout

        row = layout.row()
        row.prop(pg, "search_term")

        row = layout.row()
        if pg.search_term:
            search_list = getattr(pg, self.search_list_id)
            search_results: list[dict[str, Any]] = [
                {
                    'key': o.get('param_id',''),
                    'value': o.get('param_value',''),
                    'readonly': False,
                    'list_id': self.search_list_id,
                    'idx': e,
                }
                for e, o in enumerate(search_list)
            ]
            draw_list(layout, pg, search_results, operators=[
                { 'id': 'list_transfer_item', 'icon': 'ADD', 'params': {'target_list': self.list_id} }
            ])
        else:
            overrides_list = getattr(pg, self.list_id)
            overrides: list[dict[str, Any]] = [
                {
                    'key': o.get('param_id',''),
                    'value': o.get('param_value',''),
                    'readonly': False,
                    'list_id': self.list_id,
                    'idx': e,
                }
                for e, o in enumerate(overrides_list)
            ]

            all_overrides: dict[str, dict[str, str | int]] = get_inherited_overrides(cx, TYPES_NAME)
            inherited_overrides: list[dict[str, Any]] = [{
                'key': k,
                'value': o.get('value',''),
                'readonly': True,
            } for k,o in all_overrides.items() if o['inherited']]

            draw_list(layout, pg, inherited_overrides+overrides, icon="RNA", add_list_id=self.list_id, operators=[
                { 'id': 'list_remove_item', 'icon': 'X'}
            ])

def draw_pause_list(layout, pg, list_id):
    data = getattr(pg, list_id)
    box = layout.box()
    
    for e, item in enumerate(data):
        row = box.row()
        
        current_op = row.operator(f"{TYPES_NAME}.list_remove_item", text = "", icon="X") #type: ignore
        current_op.list_id = list_id #type: ignore
        current_op.item_idx = e #type: ignore

        row.prop_menu_enum(item, "param_type", icon="DOWNARROW_HLT")
        
        if item.param_type == "custom_gcode":
            row.prop(item, "param_cmd")
        else:
            label = "Pause" if item.param_type == "pause" else None
            label = "Color Change" if item.param_type == "color_change" else label
            row.label(text=label)

        subrow = row.row(align=True)
        subrow.prop(item, 'param_value_type')
        subrow.prop(item, "param_value", text="")

class SlicerPanel_1_Pauses(BasePanel):
    bl_label = "Pauses, Color Changes and Custom Gcode"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Pauses"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"
    list_id = f"pause_list"

    def draw(self, context):
        cx: Collection | None = coll_from_selection()
        pg = getattr(cx, TYPES_NAME)

        layout = self.layout

        row = layout.row()
        draw_pause_list(layout, pg, self.list_id)

        row = layout.row()
        op_add_param: AddItemOperator = row.operator(f"{TYPES_NAME}.list_add_item") #type: ignore
        op_add_param.list_id=f"{self.list_id}"