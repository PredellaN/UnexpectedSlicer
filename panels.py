from typing import Any
from bpy.types import OperatorProperties, PropertyGroup
import bpy
from bpy.types import Collection, UILayout

from .operators import RunPrusaSlicerOperator, UnmountUsbOperator
from .functions.basic_functions import (
    BasePanel,
    BaseList,
    SearchList,
    ParamAddOperator,
    ParamRemoveOperator,
    is_usb_device
)
from .functions.blender_funcs import coll_from_selection, get_inherited_overrides, get_inherited_slicing_props
from . import TYPES_NAME

class PRUSASLICER_UL_SearchParamValue(SearchList):
    def draw_properties(self, row, item):
        row.label(text=item.param_id + " - " + item.param_description)

class ItemRemoveOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.list_remove_item"
    bl_label = "Remove Item"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        cx: Collection | None = coll_from_selection()
        prop_group = getattr(cx, TYPES_NAME)

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        return {'FINISHED'}

class SelectedCollRemoveOperator(ParamRemoveOperator):
    bl_idname = f"{TYPES_NAME}.selected_coll_remove_param"
    bl_label = "Remove Parameter"
    def get_pg(self):
        cx: Collection | None = coll_from_selection()
        return getattr(cx, TYPES_NAME)
    
class SelectedCollAddOperator(ParamAddOperator):
    bl_idname = f"{TYPES_NAME}.selected_coll_add_param"
    bl_label = "Add Parameter"
    def get_pg(self):
        cx: Collection | None = coll_from_selection()
        return getattr(cx, TYPES_NAME)

class PRUSASLICER_UL_OverrideValue(BaseList):
    delete_operator = f"{TYPES_NAME}.selected_coll_remove_param"
    def draw_properties(self, row, item):
        row.prop(item, "param_id")
        row.prop(item, "param_value")

class PRUSASLICER_UL_PauseValue(BaseList):
    delete_operator = f"{TYPES_NAME}.selected_coll_remove_param"
    def draw_properties(self, row, item):
        sub_row = row.row(align=True)
        sub_row.prop(item, "param_type")
        sub_row.scale_x = 0.1
        if item.param_type == "custom_gcode":
            row.prop(item, "param_cmd")
        else:
            label = "Pause" if item.param_type == "pause" else None
            label = "Color Change" if item.param_type == "color_change" else label
            row.label(text=label)

        # row.label(text="on layer")
        sub_row = row.row(align=True)
        sub_row.scale_x = 0.8  # Adjust this scale value as needed
        sub_row.prop(item, 'param_value_type')

        sub_row = row.row(align=True)
        sub_row.scale_x = 0.5  # Adjust this scale value as needed
        sub_row.prop(item, "param_value", text="")

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
        sub_row.label(text=f"Inherited: {prop['prop']}")
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
        cx_overrides: dict[str, dict[str, str | bool | int]] = get_inherited_overrides(cx, TYPES_NAME)

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

def draw_list(layout: UILayout, pg: PropertyGroup, data: list[dict[str, Any]], add_list_id = None):
    box = layout.box()

    for item in data:
        row = box.row(align=True)
        list_id = item.get('list_id', None)

        if list_id and item['editable']:
            op_remove_override: ItemRemoveOperator = row.operator(f"{TYPES_NAME}.list_remove_item", text = "", icon='X') #type: ignore
            op_remove_override.list_id = item['list_id']
            op_remove_override.item_idx = item['idx']
            
            override_list = getattr(pg, list_id)
            override_item = override_list[item['idx']]
            prop = row.prop(override_item, 'param_id', index=1, text="")
            prop = row.prop(override_item, 'param_value', index=1, text="")
        else:
            row.label(icon="ANIM_DATA")
            row.label(text=f"{item['key']}")
            row.label(text=str(item.get('value', None)))
            
    if add_list_id:
        row = box.row()
        op_add_param: SelectedCollAddOperator = row.operator(f"{TYPES_NAME}.selected_coll_add_param") #type: ignore
        op_add_param.target=f"{add_list_id}"

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
        active_list = "PRUSASLICER_UL_SearchParamValue" if pg.search_term else "PRUSASLICER_UL_OverrideValue"
        active_list_id = self.search_list_id if pg.search_term else self.list_id
        # Example dictionary

        overrides_list = getattr(pg, self.list_id)
        overrides: list[dict[str, Any]] = [
            {
                'key': o.get('param_id',''),
                'value': o.get('param_value',''),
                'editable': True,
                'list_id': self.list_id,
                'idx': e,
            }
            for e, o in enumerate(overrides_list)
        ]

        all_overrides: dict[str, dict[str, str | int]] = get_inherited_overrides(cx, TYPES_NAME)
        inherited_overrides: list[dict[str, Any]] = [{
            'key': k,
            'value': o.get('value',''),
            'editable': False,
        } for k,o in all_overrides.items() if o['inherited']]

        draw_list(layout, pg, inherited_overrides+overrides, add_list_id=self.list_id)

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
        row.template_list(f"PRUSASLICER_UL_PauseValue", f"{self.list_id}",
                pg, f"{self.list_id}",
                pg, f"{self.list_id}_index"
                )
        
        row = layout.row()
        op_add_param: SelectedCollAddOperator = row.operator(f"{TYPES_NAME}.selected_coll_add_param") #type: ignore
        op_add_param.target=f"{self.list_id}"