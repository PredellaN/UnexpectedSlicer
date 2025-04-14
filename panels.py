import bpy
from typing import Any, Dict, List
from bpy.types import PropertyGroup, Collection, UILayout

from .functions.py_classes import FromCollection, FromObject, ResetSearchTerm

from .property_groups import SlicerPropertyGroup
from .operators import RunSlicerOperator, UnmountUsbOperator
from .functions.basic_functions import is_usb_device
from .functions.bpy_classes import (
    BasePanel,
    ParamRemoveOperator,
    ParamAddOperator,
    ParamTransferOperator,
)
from .functions.blender_funcs import coll_from_selection, get_inherited_overrides, get_inherited_slicing_props
from .functions.prusaslicer_fields import search_in_mod_db, search_in_db
from . import TYPES_NAME

class RemoveObjectItemOperator(FromObject, ParamRemoveOperator):
    bl_idname = f"{TYPES_NAME}.list_obj_remove_item"

class AddObjectItemOperator(FromObject, ParamAddOperator):
    bl_idname = f"{TYPES_NAME}.list_obj_add_item"

def draw_item_row(row, item, idx, list_id):
    # Draw the remove button
    remove_op = row.operator(f"{TYPES_NAME}.list_obj_remove_item", text="", icon='X')
    remove_op.list_id = list_id
    remove_op.item_idx = idx
    # Draw the item properties
    row.prop(item, 'param_id', index=1, text="")
    row.prop(item, 'param_value', index=1, text="")

def draw_object_modifiers_list(layout: UILayout, pg: PropertyGroup, list_id) -> None:
    box = layout.box()
    data = getattr(pg, list_id)

    for idx, item in enumerate(data):
        row = box.row(align=True)
        draw_item_row(row, item, idx, list_id)
        
    row = box.row()
    op_add: AddObjectItemOperator = row.operator(f"{TYPES_NAME}.list_obj_add_item") #type: ignore
    op_add.list_id = list_id

def draw_debug_box(layout: UILayout, pg: PropertyGroup):
    errs = getattr(pg, 'print_debug')
    if not errs:
        return
    box = layout.box()
    for err in errs.split("\n"):
        if err:
            row = box.row()
            row.label(text=err)

class SlicerObjectPanel(bpy.types.Panel):
    bl_label = "UnexpectedSlicer"
    bl_idname = f"OBJECT_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    
    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        pg = getattr(obj, TYPES_NAME)
        layout.prop(pg, "object_type", text="Object type")
        layout.prop(pg, "extruder", text="Extruder")
        if pg.object_type == 'ParameterModifier':
            
            layout.row().prop(pg, "search_term")
            if pg.search_term:
                search_list: dict[str, list[str]] = search_in_mod_db(term=pg.search_term)
                draw_search_list(layout, search_list, 'modifiers', 'mod_list_transfer_item')
            else:
                draw_object_modifiers_list(layout, pg, 'modifiers')

def draw_conf_dropdown(pg: PropertyGroup, layout: UILayout, key: str, prop: Dict[str, Any]) -> None:
    row = layout.row()
    
    # Draw type label
    type_row = row.row()
    type_row.label(text=f"{prop['type'].capitalize()}:")
    type_row.scale_x = 0.5

    # Draw property dropdown
    prop_row = row.row()
    prop_row.prop(pg, f'{key}_enum', text='')
    prop_row.scale_x = 2 if not prop.get('inherited', False) else 0.1

    # If inherited, display inherited details
    if prop.get('inherited', False):
        inherited_row = row.row()
        inherited_text = f"Inherited: {prop.get('prop','').split(':')[1]}"
        inherited_row.label(text=inherited_text)
        inherited_row.scale_x = 1.9

class SlicerPanel(BasePanel):
    bl_label = "UnexpectedSlicer"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        collection: Collection | None = coll_from_selection()
        layout = self.layout

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        layout.row().label(text=f"Slicing settings for Collection '{collection.name}'")

        # Draw slicing property dropdowns
        cx_props: Dict[str, Dict[str, Any]] = get_inherited_slicing_props(collection, TYPES_NAME)
        for key, prop in cx_props.items():
            draw_conf_dropdown(pg, layout, key, prop)

        # Slice buttons row
        row = layout.row()
        sliceable = all(prop.get('prop') for prop in cx_props.values())
        slice_buttons: List[tuple[str, str]] = []
        if sliceable:
            slice_buttons = [("Slice", "slice"), ("Slice and Preview", "slice_and_preview"), ("Open with PrusaSlicer", "open")]
            for label, mode in slice_buttons:
                op: RunSlicerOperator = row.operator(f"export.slice", text=label, icon="ALIGN_JUSTIFY")  # type: ignore
                op.mode = mode
                op.mountpoint = ""

        # Progress slider
        progress_row = layout.row()
        progress_row.prop(pg, "progress", text=pg.progress_text, slider=True)
        progress_row.enabled = False

        draw_debug_box(layout, pg)

        # Display print time and weight if available
        if pg.print_time:
            layout.row().label(text=f"Printing time: {pg.print_time}")
        if pg.print_weight:
            layout.row().label(text=f"Print weight: {pg.print_weight}g")

        # USB devices detection and controls
        self.draw_usb_devices(layout, pg)

    def draw_usb_devices(self, layout: UILayout, pg: SlicerPropertyGroup) -> None:
        import psutil  # type: ignore
        partitions = psutil.disk_partitions()
        usb_partitions = [p for p in partitions if is_usb_device(p)]

        if usb_partitions:
            layout.row().label(text="Detected USB Devices:")

        for partition in usb_partitions:
            row = layout.row()
            mountpoint = partition.mountpoint
            row.enabled = not pg.running

            # Unmount USB operator
            op_unmount: UnmountUsbOperator = row.operator(f"export.unmount_usb", text="", icon='UNLOCKED')  # type: ignore
            op_unmount.mountpoint = mountpoint

            # Slice USB operator
            op_slice: RunSlicerOperator = row.operator(f"export.slice", text="", icon='DISK_DRIVE')  # type: ignore
            op_slice.mountpoint = mountpoint
            op_slice.mode = "slice"

            row.label(text=f"{mountpoint.split('/')[-1]} mounted at {mountpoint} ({partition.device})")


class RemoveItemOperator(FromCollection, ParamRemoveOperator):
    bl_idname = f"{TYPES_NAME}.list_remove_item"

class AddItemOperator(FromCollection, ParamAddOperator):
    bl_idname = f"{TYPES_NAME}.list_add_item"

def draw_overrides_list(layout: UILayout, pg: PropertyGroup, list_id, ro_data) -> None:

    def button():
        op: ParamRemoveOperator = row.operator(f"{TYPES_NAME}.list_remove_item", text="", icon='X') # type: ignore
        op.list_id = list_id
        op.item_idx = idx

    box = layout.box()
    data = getattr(pg, list_id)

    for idx, item in enumerate(data):
        row = box.row(align=True)
        button()

        row.prop(item, 'param_id', index=1, text="")
        row.prop(item, 'param_value', index=1, text="")
    
    for item in ro_data:
        row = box.row(align=True)
        row.label(icon='RNA')  # type: ignore
        row.label(text=f"{item.get('param_id', '')}")
        row.label(text=str(item.get('param_value', '')))

    row = box.row()
    op_add: ParamAddOperator = row.operator(f"{TYPES_NAME}.list_add_item")  # type: ignore
    op_add.list_id = list_id

class TransferModItemOperator(FromObject, ResetSearchTerm, ParamTransferOperator):
    bl_idname = f"{TYPES_NAME}.mod_list_transfer_item"

class TransferItemOperator(FromCollection, ResetSearchTerm, ParamTransferOperator):
    bl_idname = f"{TYPES_NAME}.list_transfer_item"

def draw_search_list(layout: UILayout, search_list_id: dict[str, list[str]], target_list: str, transfer_operator: str):
    box = layout.box()

    for key, item in search_list_id.items():
        row = box.row()

        op: ParamTransferOperator = row.operator(f"{TYPES_NAME}.{transfer_operator}", text="", icon="ADD")  # type: ignore
        op.target_key = key
        op.target_list = target_list

        row.label(text=f"{item[0]} : {item[1]}")

class SlicerPanel_0_Overrides(BasePanel):
    bl_label = "Configuration Overrides"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Overrides"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        collection: Collection | None = coll_from_selection()
        layout = self.layout

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        layout.row().prop(pg, "search_term")

        if getattr(pg, 'search_term', ""):
            search_list: dict[str, list[str]] = search_in_db(pg.search_term)
            draw_search_list(layout, search_list, 'list', 'list_transfer_item')
        else:
            all_overrides = get_inherited_overrides(collection, TYPES_NAME)
            inherited_overrides = [{
                'param_id': key,
                'param_value': override.get('value', ''),
            } for key, override in all_overrides.items() if override.get('inherited', False)]

            draw_overrides_list(layout, pg, "list", inherited_overrides)


def draw_pause_list(layout: UILayout, pg: PropertyGroup, list_id: str) -> None:
    items = getattr(pg, list_id)
    box = layout.box()

    for idx, item in enumerate(items):
        row = box.row()
        # Draw remove operator for each pause/gcode entry
        op_remove: ParamRemoveOperator = row.operator(f"{TYPES_NAME}.list_remove_item", text="", icon="X")  # type: ignore
        op_remove.list_id = list_id
        op_remove.item_idx = idx

        # Draw enum for pause type
        row.prop_menu_enum(item, "param_type", icon="DOWNARROW_HLT")
        
        # Depending on the parameter type, draw corresponding UI element
        if item.param_type == "custom_gcode":
            row.prop(item, "param_cmd")
        else:
            label_map = {"pause": "Pause", "color_change": "Color Change"}
            row.label(text=label_map.get(item.param_type, ""))
        
        # Draw value type and value properties
        subrow = row.row(align=True)
        subrow.prop(item, 'param_value_type')
        subrow.prop(item, "param_value", text="")

    row = box.row()
    op_add: ParamAddOperator = row.operator(f"{TYPES_NAME}.list_add_item")  # type: ignore
    op_add.list_id = list_id

class SlicerPanel_1_Pauses(BasePanel):
    bl_label = "Pauses, Color Changes and Custom Gcode"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Pauses"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        collection: Collection | None = coll_from_selection()
        layout = self.layout

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        draw_pause_list(layout, pg, "pause_list")