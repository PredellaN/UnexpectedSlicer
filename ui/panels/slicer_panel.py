from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from bpy.types import Collection, PropertyGroup, UILayout
    from ...preferences.preferences import SlicerPreferences
    from ..panels.gcode_preview_panel import StopPreviewGcodeOperator

import bpy

from ...operators import RunSlicerOperator

from ...registry import register_class
from ..panels.base import BasePanel
from ...functions.draw_gcode import drawer

from ... import TYPES_NAME, PACKAGE

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

@register_class
class SlicerPanel(BasePanel):
    bl_label = "UnexpectedSlicer"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        from ...infra.blender_bridge import coll_from_selection
        from ...functions.blender_funcs import get_inherited_slicing_props
        from ...registry import get_icon

        collection: Collection | None = coll_from_selection()
        layout = self.layout
        if not layout: return

        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore
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

        blendfile_path = Path(bpy.data.filepath)

        def slice_row():
            sr = row.row(align=True)
            workspace = bpy.context.workspace
            ws_pg = getattr(workspace, TYPES_NAME)

            if drawer.enabled:
                op_cancel: StopPreviewGcodeOperator = sr.operator("collection.stop_preview_gcode", text="", icon="X")
                op_cancel.action = 'stop'
            else:
                if ws_pg.gcode_preview_internal: sr.prop(ws_pg, 'gcode_preview_internal', icon_only=True, toggle=True, icon='BLENDER')
                else: sr.prop(ws_pg, 'gcode_preview_internal', icon_only=True, toggle=True, icon_value=get_icon('prusaslicer.png'))
            
            op: RunSlicerOperator = sr.operator(
                "collection.slice",
                text="Slice and Preview",
                icon_value=get_icon("slice_and_preview.png")
            )
            op.mode = "slice_and_preview_internal" if ws_pg.gcode_preview_internal else "slice_and_preview"
            op.mountpoint = str(blendfile_path.parent)

            op_2: RunSlicerOperator = sr.operator('collection.slice', text='', icon_value=get_icon("slice.png"))
            op_2.mode = "slice"
            op_2.mountpoint = str(blendfile_path.parent)

            op_3: RunSlicerOperator = sr.operator('collection.slice', text='', icon='FILEBROWSER')
            op_3.mode = "slice"
            op_3.mountpoint = ""

        def open_prusaslicer_row():
            op: RunSlicerOperator = row.operator(
                "collection.slice",
                text="Open with PrusaSlicer",
                icon_value=get_icon("prusaslicer.png")
            )
            op.mode = "open"
            op.mountpoint = str(blendfile_path.parent)

        slice_row()
        open_prusaslicer_row()

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

        row = layout.row()

        # USB devices detection and controls
        from .ui_elements.usb import draw_usb_devices
        draw_usb_devices(layout, pg, sliceable)