from bpy.types import Collection


import bpy # type: ignore
from .functions.basic_functions import BasePanel, BaseList, SearchList, ParamAddOperator, ParamRemoveOperator, is_usb_device
from .functions import blender_funcs as bf
from . import TYPES_NAME

class PRUSASLICER_UL_SearchParamValue(SearchList):
    def draw_properties(self, row, item):
        row.label(text=item.param_id + " - " + item.param_description)

class SelectedCollRemoveOperator(ParamRemoveOperator):
    bl_idname = f"{TYPES_NAME}.selected_coll_remove_param"
    bl_label = "Remove Parameter"
    def get_pg(self):
        cx = bf.coll_from_selection()
        return getattr(cx, TYPES_NAME)
    
class SelectedCollAddOperator(ParamAddOperator):
    bl_idname = f"{TYPES_NAME}.selected_coll_add_param"
    bl_label = "Add Parameter"
    def get_pg(self):
        cx = bf.coll_from_selection()
        return getattr(cx, TYPES_NAME)

class PRUSASLICER_UL_IdValue(BaseList):
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

def draw_conf_dropdown(pg, layout, attribute, conf_type):
    row = layout.row()
    
    # Label row
    sub_row = row.row()
    sub_row.label(text=f"{conf_type.capitalize()}:")
    sub_row.scale_x = 0.5

    # Property row
    sub_row = row.row()
    sub_row.prop(pg, f'{attribute}_enum', text='')
    sub_row.scale_x = 2

class PrusaSlicerPanel(BasePanel):
    bl_label = "Blender to PrusaSlicer"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        cx: Collection | None = bf.coll_from_selection()

        pg = getattr(cx, TYPES_NAME)

        layout = self.layout

        # Toggle button for single or multiple configuration files
        row = layout.row()
        row.label(text=f"Slicing settings for Collection '{cx.name}'")

        draw_conf_dropdown(pg, layout, 'printer_config_file', 'printer')
        for i in ['','_2','_3','_4','_5'][:pg.extruder_count]:
            draw_conf_dropdown(pg, layout, f'filament{i}_config_file', 'filament')
        draw_conf_dropdown(pg, layout, 'print_config_file', 'print')

        row = layout.row()
        
        cx_props, cx_inherited = bf.get_inherited_slicing_props(cx, TYPES_NAME, pg.extruder_count)
        sliceable = all([v for k,v in cx_props.items()])
        if sliceable:
            op = row.operator(f"export.slice", text="Slice", icon="ALIGN_JUSTIFY")
            op.mode="slice"
            op.mountpoint=""
            op = row.operator(f"export.slice", text="Slice and Preview", icon="ALIGN_JUSTIFY")
            op.mode="slice_and_preview"
            op.mountpoint=""
            
        row.operator(f"export.slice", text="Open with PrusaSlicer").mode="open"

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
        import psutil
        partitions = psutil.disk_partitions()

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
                row.operator(f"export.unmount_usb", text="", icon='UNLOCKED').mountpoint=mountpoint
                op = row.operator(f"export.slice", text="", icon='DISK_DRIVE')
                op.mountpoint=mountpoint
                op.mode = "slice"
                row.label(text=f"{mountpoint.split('/')[-1]} mounted at {mountpoint} ({partition.device})")

class SlicerPanel_0_Overrides(BasePanel):
    bl_label = "Configuration Overrides"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Overrides"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"
    search_list_id = f"search_list"
    list_id = f"list"

    def draw(self, context):
        cx = bf.coll_from_selection()
        pg = getattr(cx, TYPES_NAME)

        layout = self.layout

        row = layout.row()
        row.prop(pg, "search_term")

        row = layout.row()
        active_list = "PRUSASLICER_UL_SearchParamValue" if pg.search_term else "PRUSASLICER_UL_IdValue"
        active_list_id = self.search_list_id if pg.search_term else self.list_id
        row.template_list(active_list, f"{active_list_id}",
                pg, f"{active_list_id}",
                pg, f"{active_list_id}_index"
                )
        
        row = layout.row()
        row.operator(f"{TYPES_NAME}.selected_coll_add_param").target=f"{self.list_id}"

class SlicerPanel_1_Pauses(BasePanel):
    bl_label = "Pauses, Color Changes and Custom Gcode"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_Pauses"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"
    list_id = f"pause_list"

    def draw(self, context):
        cx = bf.coll_from_selection()
        pg = getattr(cx, TYPES_NAME)

        layout = self.layout

        row = layout.row()
        row.template_list(f"PRUSASLICER_UL_PauseValue", f"{self.list_id}",
                pg, f"{self.list_id}",
                pg, f"{self.list_id}_index"
                )
        
        row = layout.row()
        row.operator(f"{TYPES_NAME}.selected_coll_add_param").target=f"{self.list_id}"