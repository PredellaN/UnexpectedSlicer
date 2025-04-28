import bpy
from typing import Any, Dict, List
from bpy.types import PropertyGroup, Collection, UILayout, bpy_prop_collection

from .functions.py_classes import FromCollection, FromObject, ResetSearchTerm

from .preferences import SlicerPreferences
from .property_groups import ParamsListItem, SlicerPropertyGroup
from .operators import RunSlicerOperator, UnmountUsbOperator

from .functions.bpy_classes import (
    BasePanel,
    ParamRemoveOperator,
    ParamAddOperator,
    ParamTransferOperator,
)
from .functions.blender_funcs import coll_from_selection, get_inherited_overrides, get_inherited_slicing_props
from .functions.prusaslicer_fields import search_db, search_in_mod_db, search_in_db
from . import TYPES_NAME, PACKAGE

class RemoveObjectItemOperator(FromObject, ParamRemoveOperator):
    bl_idname = "object.slicer_remove_item"
    bl_label = ""

class AddObjectItemOperator(FromObject, ParamAddOperator):
    bl_idname = "object.slicer_add_item"

def create_operator_row(row, operator_id: str, list_id: str = '', idx: int | None = None, icon: str = 'NONE', text = None) -> ParamRemoveOperator:
    op: ParamRemoveOperator = row.operator(operator_id, text=text, icon=icon)  # type: ignore
    if list_id:
        op.list_id = list_id
    if idx:
        op.item_idx = idx
    return op

def draw_formatted_prop(layout: UILayout, item: ParamsListItem) -> None:
    if not item.param_id:
        return

    if not (param := search_db.get(item.param_id)):
        layout.label(text = 'Parameter not found!')
        return

    if param['type'] in ['coEnum', 'coEnums']:
        layout.prop(item, 'param_enum', index=1, text="")
        return

    if param['type'] in ['coBool', 'coBools']:
        sr = layout.row()
        sr.scale_x = 0.66
        sr.label(text=" ")
        sr.prop(item, 'param_bool', index=1, text="")
        sr.label(text=" ")
        return

    if param['type'] in ['coFloat', 'coFloats']:
        if param.get('min') == 0 and param.get('max') in [359, 360]:
            layout.prop(item, 'param_angle', index=1, text="")
            return

        layout.prop(item, 'param_float', index=1, text="")
        return

    if param['type'] in ['coInt', 'coInts']:
        layout.prop(item, 'param_int', index=1, text="")
        return

    if param['type'] in ['coPercent', 'coPercents']:
        layout.prop(item, 'param_perc', index=1, text="")
        return

    layout.prop(item, 'param_value', index=1, text="")

def draw_debug_box(layout: UILayout, pg: PropertyGroup):
    errs = getattr(pg, 'print_debug')
    if not errs:
        return
    box: UILayout = layout.box()
    for err in errs.split("\n"):
        if err:
            row = box.row()
            row.label(text=err)

def draw_item(layout: UILayout, item: ParamsListItem):
    layout.prop(item, 'param_id', index=1, text="")
    draw_formatted_prop(layout, item)

def draw_override_items(layout: UILayout, data: bpy_prop_collection, list_id: str, remove_operator: str):
    for idx, item in enumerate(data):
        row = layout.row(align=True)
        if remove_operator:
            create_operator_row(row, remove_operator, list_id, idx, 'X')
        draw_item(row, item)

def draw_search_item(row, item, transfer_operator: str, target_list: str, key: str):
    op: ParamTransferOperator = row.operator(f"collection.{transfer_operator}", text="", icon="ADD")  # type: ignore
    op.target_key = key
    op.target_list = target_list
    row.label(text=f"{item['label']} : {item['tooltip']}")

def draw_object_overrides_list(layout: UILayout, pg: PropertyGroup, list_id) -> None:
    box: UILayout = layout.box()
    data: bpy_prop_collection = getattr(pg, list_id)

    draw_override_items(box, data, list_id, 'object.slicer_remove_item')
    create_operator_row(box, "object.slicer_add_item", list_id)

def draw_search_list(layout: UILayout, search_list_id: dict[str, dict], target_list: str, transfer_operator: str):
    box: UILayout = layout.box()

    for key, item in search_list_id.items():
        row = box.row()
        draw_search_item(row, item, transfer_operator, target_list, key)

def draw_overrides_list(layout: UILayout, pg: PropertyGroup, list_id: str, readonly_data: list[dict[str, Any]]) -> None:
    box: UILayout = layout.box()
    data: bpy_prop_collection = getattr(pg, list_id)

    draw_override_items(box, data, list_id, 'collection.slicer_remove_item')
    
    for item in readonly_data:
        row = box.row(align=True)
        row.label(icon='RNA')  # type: ignore
        row.label(text=f"{item.get('param_id', '')}")
        row.label(text=str(item.get('param_value', '')))

    create_operator_row(box, "collection.slicer_add_item", list_id)

def draw_pause_list(layout: UILayout, pg: PropertyGroup, list_id: str) -> None:
    data: bpy_prop_collection = getattr(pg, list_id)
    box: UILayout = layout.box()

    for idx, item in enumerate(data):
        row = box.row()
        # Draw remove operator for each pause/gcode entry
        op_remove: ParamRemoveOperator = row.operator("collection.slicer_remove_item", text="", icon="X")  # type: ignore
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
        subrow.prop(item, "param_float" if item.param_value_type == 'height' else "param_int", text="")

    row = box.row()
    op_add: ParamAddOperator = row.operator("collection.slicer_add_item")  # type: ignore
    op_add.list_id = list_id

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
                search_list: dict[str, dict] = search_in_mod_db(term=pg.search_term)
                draw_search_list(layout, search_list, 'modifiers', 'mod_list_transfer_item')
            else:
                draw_object_overrides_list(layout, pg, 'modifiers')

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

are_profiles_loaded = False
class SlicerPanel(BasePanel):
    bl_label = "UnexpectedSlicer"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        from .functions.icon_provider import icons

        collection: Collection | None = coll_from_selection()
        layout = self.layout

        global are_profiles_loaded
        if not are_profiles_loaded:
            prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
            prefs.update_config_bundle_manifest()
            are_profiles_loaded = True

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
        if sliceable:
            slice_buttons: List[tuple[str, str, str]] = [("Slice", "slice", 'slice'), ("Slice and Preview", "slice_and_preview", 'slice_and_preview'), ("Open with PrusaSlicer", "open", 'prusaslicer')]
            for label, mode, icon in slice_buttons:
                op: RunSlicerOperator = row.operator("collection.slice", text=label, icon_value=icons[icon])  # type: ignore
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
        self.draw_usb_devices(layout, pg, sliceable)

    def draw_usb_devices(self, layout: UILayout, pg: SlicerPropertyGroup, sliceable: bool) -> None:
        import psutil  # type: ignore
        from .functions.basic_functions import is_usb_device

        partitions = psutil.disk_partitions()
        usb_partitions = [p for p in partitions if is_usb_device(p)]

        if usb_partitions:
            layout.row().label(text="Detected USB Devices:")

        for partition in usb_partitions:
            row = layout.row()
            mountpoint = partition.mountpoint
            row.enabled = not pg.running

            # Unmount USB operator
            op_unmount: UnmountUsbOperator = row.operator("collection.unmount_usb", text="", icon='UNLOCKED')  # type: ignore
            op_unmount.mountpoint = mountpoint

            # Slice USB operator
            if sliceable:
                op_slice: RunSlicerOperator = row.operator("collection.slice", text="", icon='DISK_DRIVE')  # type: ignore
                op_slice.mountpoint = mountpoint
                op_slice.mode = "slice"

            row.label(text=f"{mountpoint.split('/')[-1]} mounted at {mountpoint} ({partition.device})")


class RemoveItemOperator(FromCollection, ParamRemoveOperator):
    bl_idname = f"collection.slicer_remove_item"
    bl_label = ""

class AddItemOperator(FromCollection, ParamAddOperator):
    bl_idname = f"collection.slicer_add_item"

class TransferModItemOperator(FromObject, ResetSearchTerm, ParamTransferOperator):
    bl_idname = f"collection.mod_list_transfer_item"

class TransferItemOperator(FromCollection, ResetSearchTerm, ParamTransferOperator):
    bl_idname = f"collection.list_transfer_item"

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
            search_list: dict[str, dict[str, Any]] = search_in_db(pg.search_term)
            draw_search_list(layout, search_list, 'list', 'list_transfer_item')
        else:
            all_overrides = get_inherited_overrides(collection, TYPES_NAME)
            inherited_overrides: list[dict[str, Any]] = [{
                'param_id': key,
                'param_value': override.get('value', ''),
            } for key, override in all_overrides.items() if override.get('inherited', False)]

            draw_overrides_list(layout, pg, "list", inherited_overrides)

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