from typing import Any

import bpy
from bpy.types import Collection, PropertyGroup, UILayout

from ..registry import register

from ..classes.bpy_classes import BasePanel
from ..operators import RunSlicerOperator
from ..preferences.preferences import SlicerPreferences

from .. import TYPES_NAME, PACKAGE

from ..functions.draw_gcode import drawer

def draw_conf_dropdown(pg: PropertyGroup, layout: UILayout, key: str, prop: dict[str, Any]) -> None:
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

def draw_debug_box(layout: UILayout, pg: PropertyGroup):
    errs = getattr(pg, 'print_stderr')
    if not errs:
        return
    box: UILayout = layout.box()
    for err in errs.split("\n"):
        if err:
            row = box.row()
            row.label(text=err)

@register
class SlicerPanel(BasePanel):
    bl_label = "UnexpectedSlicer"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        from ..functions.blender_funcs import coll_from_selection, get_inherited_slicing_props
        from ..functions.icon_provider import icons

        collection: Collection | None = coll_from_selection()
        layout = self.layout

        from ..preferences.preferences import are_profiles_loaded
        if not are_profiles_loaded:
            prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
            prefs.update_config_bundle_manifest()

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        layout.row().label(text=f"Slicing settings for Collection '{collection.name}'")

        # Draw slicing property dropdowns
        cx_props: dict[str, dict[str, Any]] = get_inherited_slicing_props(collection, TYPES_NAME)
        for key, prop in cx_props.items():
            draw_conf_dropdown(pg, layout, key, prop)

        # Slice buttons row
        row = layout.row()

        sliceable = all(prop.get('prop') for prop in cx_props.values())

        # Slice
        op: RunSlicerOperator = row.operator(
            "collection.slice",
            text="Slice",
            icon_value=icons["slice"]
        )  # type: ignore
        op.mode = "slice"
        op.mountpoint = ""

        # Slice and Preview
        workspace = bpy.context.workspace
        ws_pg = getattr(workspace, TYPES_NAME)
        sr = row.row(align=True)
        op = sr.operator(
            "collection.slice",
            text="Slice and Preview",
            icon_value=icons["slice_and_preview_prusaslicer"]
        )  # type: ignore
        op.mode = "slice_and_preview_internal" if ws_pg.gcode_preview_internal else "slice_and_preview"
        op.mountpoint = ""
        
        if drawer.enabled:
            op_cancel: PreviewGcodeOperator = sr.operator("collection.stop_preview_gcode", text="", icon="X") #type: ignore
            op_cancel.action = 'stop'
        else:
            icon_dict: dict[str, str] | dict[str, int] = {'icon': 'BLENDER'} if ws_pg.gcode_preview_internal else {'icon_value': icons['prusaslicer']}
            sr.prop(ws_pg, 'gcode_preview_internal', icon_only=True, toggle=True, **icon_dict)

        # Open with PrusaSlicer
        op = row.operator(
            "collection.slice",
            text="Open with PrusaSlicer",
            icon_value=icons["prusaslicer"]
        )  # type: ignore
        op.mode = "open"
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
        from .ui_elements.usb import draw_usb_devices
        draw_usb_devices(layout, pg, sliceable)