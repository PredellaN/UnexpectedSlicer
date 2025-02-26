import bpy
from typing import Any, Dict, List
from bpy.types import PropertyGroup, Collection, UILayout

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
from . import TYPES_NAME


class ItemRemoveOperator(ParamRemoveOperator):
    bl_idname = f"{TYPES_NAME}.list_remove_item"
    bl_label = "Remove Item"

    def get_pg(self):
        collection: Collection | None = coll_from_selection()
        return getattr(collection, TYPES_NAME)


class AddItemOperator(ParamAddOperator):
    bl_idname = f"{TYPES_NAME}.list_add_item"
    bl_label = "Add Parameter"

    def get_pg(self):
        collection: Collection | None = coll_from_selection()
        return getattr(collection, TYPES_NAME)


class TransferItemOperator(ParamTransferOperator):
    bl_idname = f"{TYPES_NAME}.list_transfer_item"
    bl_label = "Add Parameter"

    def get_pg(self):
        collection: Collection | None = coll_from_selection()
        return getattr(collection, TYPES_NAME)

    def trigger(self):
        pg = self.get_pg()
        pg.search_term = ""


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

class SlicerObjectPanel(bpy.types.Panel):
    bl_label = "Unexpected Slicer"
    bl_idname = f"OBJECT_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    
    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        pg = getattr(obj, TYPES_NAME)
        layout.prop(pg, "extruder", text="Extruder")

class SlicerPanel(BasePanel):
    bl_label = "Unexpected Slicer"
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

        # Display print time and weight if available
        if pg.print_time:
            layout.row().label(text=f"Printing time: {pg.print_time}")
        if pg.print_weight:
            layout.row().label(text=f"Print weight: {pg.print_weight}g")

        # Progress slider (disabled)
        progress_row = layout.row()
        progress_row.prop(pg, "progress", text=pg.progress_text, slider=True)
        progress_row.enabled = False

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


def draw_list(layout: UILayout, pg: PropertyGroup, data) -> None:
    box = layout.box()

    for item in data:
        row = box.row(align=True)

        # If item is editable and linked to a list, draw operator buttons
        if not item['inherited']:
            
            op: ParamRemoveOperator = row.operator(f"{TYPES_NAME}.list_remove_item", text="", icon='X') # type: ignore
            op.list_id = item['list_id']
            op.item_idx = item['idx']

            pg_list = getattr(pg, item['list_id'])
            pg_item = pg_list[item['idx']]

            row.prop(pg_item, 'param_id', index=1, text="")
            row.prop(pg_item, 'param_value', index=1, text="")
        else:
            row.label(icon='RNA')  # type: ignore
            row.label(text=f"{item.get('key', '')}")
            row.label(text=str(item.get('value', '')))

    row = box.row()
    op_add: AddItemOperator = row.operator(f"{TYPES_NAME}.list_add_item")  # type: ignore
    op_add.list_id = 'list'

def draw_search_list(layout: UILayout, pg: PropertyGroup, search_list_id: str):
    box = layout.box()
    data = getattr(pg, search_list_id)

    for idx, item in enumerate(data):
        row = box.row()

        op: ParamTransferOperator = row.operator(f"{TYPES_NAME}.list_transfer_item", text="", icon="ADD")  # type: ignore
        op.list_id = search_list_id
        op.item_idx = idx
        op.target_list = 'list'

        row.label(text=f"{item.get('param_id', '')} : {item.get('param_description', '')}")

class SlicerPanel_0_Overrides(BasePanel):
    bl_label = "Configuration Overrides"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Overrides"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"
    search_list_id = "search_list"
    list_id = "list"

    def draw(self, context):
        collection: Collection | None = coll_from_selection()
        layout = self.layout

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        layout.row().prop(pg, "search_term")

        if pg.search_term:
            draw_search_list(layout, pg, self.search_list_id)
        else:
            overrides_list = getattr(pg, self.list_id)
            overrides = [
                {
                    'key': obj.get('param_id', ''),
                    'value': obj.get('param_value', ''),
                    'inherited': False,
                    'list_id': self.list_id,
                    'idx': idx,
                }
                for idx, obj in enumerate(overrides_list)
            ]
            all_overrides = get_inherited_overrides(collection, TYPES_NAME)
            inherited_overrides = [{
                'key': key,
                'value': override.get('value', ''),
                'inherited': True,
            } for key, override in all_overrides.items() if override.get('inherited', False)]

            draw_list(layout, pg, inherited_overrides + overrides)


def draw_pause_list(layout: UILayout, pg: PropertyGroup, list_id: str) -> None:
    items = getattr(pg, list_id)
    box = layout.box()

    for idx, item in enumerate(items):
        row = box.row()
        # Draw remove operator for each pause/gcode entry
        op_remove = row.operator(f"{TYPES_NAME}.list_remove_item", text="", icon="X")  # type: ignore
        op_remove.list_id = list_id  # type: ignore
        op_remove.item_idx = idx  # type: ignore

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
    op_add: AddItemOperator = row.operator(f"{TYPES_NAME}.list_add_item")  # type: ignore
    op_add.list_id = list_id

class SlicerPanel_1_Pauses(BasePanel):
    bl_label = "Pauses, Color Changes and Custom Gcode"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Pauses"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"
    list_id = "pause_list"

    def draw(self, context):
        collection: Collection | None = coll_from_selection()
        layout = self.layout

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        draw_pause_list(layout, pg, self.list_id)