from typing import Any
import bpy

from .registry import register

from .preferences.preferences import SlicerPreferences
from .functions.basic_functions import reset_selection
from .classes.py_classes import PrusaSlicerTypes, PrusaSlicerEnums

from bpy.props import BoolProperty, FloatProperty, StringProperty

from . import PACKAGE

@register
class ParamsListItem(bpy.types.PropertyGroup, PrusaSlicerTypes, PrusaSlicerEnums):

    def clear_value(self, context) -> None:
        self.param_value = '0'

    param_id: StringProperty(name='', update=clear_value)

@register
class PauseListItem(bpy.types.PropertyGroup, PrusaSlicerTypes):
    param_type: bpy.props.EnumProperty(name='', items=[
        ('pause', "Pause", "Pause action"),
        ('color_change', "Color Change", "Trigger color change"),
        ('custom_gcode', "Custom Gcode", "Add a custom Gcode command"),
    ])
    param_cmd: StringProperty(name='')
    param_value_type: bpy.props.EnumProperty(name='', items=[
        ('layer', "on layer", "on layer"),
        ('height', "at height", "at height"),
    ])

cached_bundle_items: list[tuple[str, str, str]] | None = None
def get_items(self, cat) -> list[tuple[str, str, str]]:
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
    global cached_bundle_items
    cached_bundle_items = prefs.get_filtered_bundle_items(cat)
    return cached_bundle_items

def get_enum(self, cat, attribute) -> int:
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
    value = prefs.get_filtered_bundle_item_index(cat, getattr(self, attribute))
    return value

def set_enum(self, value, cat, attribute) -> None:
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
    val: Any | tuple[str, str, str] = prefs.get_filtered_bundle_item_by_index(cat, value)
    setattr(self, attribute, val[0] if val else "")

extruder_options: list[tuple[str, str, str]] = [
        ("0", "Default Extruder", "Default Extruder"),
        ("1", "Extruder 1", "Extruder 1"),
        ("2", "Extruder 2", "Extruder 2"),
        ("3", "Extruder 3", "Extruder 3"),
        ("4", "Extruder 4", "Extruder 4"),
        ("5", "Extruder 5", "Extruder 5"),
]

object_type_options: list[tuple[str, str, str]] = [
        ("ModelPart", "Part", "Model Part"),
        ("NegativeVolume", "Negative Volume", "Negative Volume"),
        ("ParameterModifier", "Modifier", "Modifier"),
        ("SupportBlocker", "Support Blocker", "Support Blocker"),
        ("SupportEnforcer", "Support Enforcer", "Support Enforcer"),
]

@register
class SlicerObjectPropertyGroup(bpy.types.PropertyGroup):
    object_type: bpy.props.EnumProperty(name="Part type", default="ModelPart", items=object_type_options)
    extruder: bpy.props.EnumProperty(name="Extruder", default="0", items=extruder_options)
    search_term : StringProperty(name="Search") #type: ignore
    modifiers: bpy.props.CollectionProperty(type=ParamsListItem)

@register
class SlicerPropertyGroup(bpy.types.PropertyGroup):

    running: bpy.props.BoolProperty(name="is running", default=False)
    progress: bpy.props.IntProperty(name="", min=0, max=100, default=0)
    progress_text: StringProperty()

    config: StringProperty(
        name="PrusaSlicer Configuration (.ini)", 
        subtype='FILE_PATH'
    )

    use_single_config: bpy.props.BoolProperty(
        name="Single Configuration",
        description="Use a single .ini configuration file",
        default=True
    )

    @staticmethod
    def config_enum_property(name, cat, attribute):
        return bpy.props.EnumProperty(
            name=name,
            items=lambda self, context: get_items(self, cat),
            get=lambda self: get_enum(self, cat, attribute),
            set=lambda self, value: set_enum(self, value, cat, attribute),
        )

    printer_config_file: StringProperty()
    printer_config_file_enum: config_enum_property("Printer Configuration", 'printer', 'printer_config_file')

    filament_config_file: StringProperty()
    filament_config_file_enum: config_enum_property("Filament Configuration", 'filament', 'filament_config_file')

    filament_2_config_file: StringProperty()
    filament_2_config_file_enum: config_enum_property("E2 Filament Configuration", 'filament', 'filament_2_config_file')

    filament_3_config_file: StringProperty()
    filament_3_config_file_enum: config_enum_property("E3 Filament Configuration", 'filament', 'filament_3_config_file')

    filament_4_config_file: StringProperty()
    filament_4_config_file_enum: config_enum_property("E4 Filament Configuration", 'filament', 'filament_4_config_file')

    filament_5_config_file: StringProperty()
    filament_5_config_file_enum: config_enum_property("E5 Filament Configuration", 'filament', 'filament_5_config_file')

    print_config_file: StringProperty()
    print_config_file_enum: config_enum_property("Print Configuration", 'print', 'print_config_file')

    search_term : StringProperty(name="Search") #type: ignore

    list : bpy.props.CollectionProperty(type=ParamsListItem)
    list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'list_index'))

    pause_list : bpy.props.CollectionProperty(type=PauseListItem)
    pause_list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'pause_list_index'))

    print_weight : StringProperty()
    print_time : StringProperty()
    print_stderr : StringProperty()
    print_stdout : StringProperty()

@register
class SlicerWorkspacePropertyGroup(bpy.types.PropertyGroup):
    def update_drawer(self, context):
        from .panels.gcode_preview_panel import drawer
        drawer.update()

    gcode_preview_internal : BoolProperty(name="Use internal gcode preview")

    gcode_preview_min_z : FloatProperty(name="Gcode preview minimum Z", min = 0, max = 1000, update=update_drawer)
    gcode_preview_max_z : FloatProperty(name="Gcode preview maximum Z", min = 0, max = 1000, update=update_drawer)

    gcode_perimeter: BoolProperty(name="Perimeter", default=True, update=update_drawer)
    gcode_external_perimeter: BoolProperty(name="External Perimeter", default=True, update=update_drawer)
    gcode_overhang_perimeter: BoolProperty(name="Overhang Perimeter", default=True, update=update_drawer)
    gcode_internal_infill: BoolProperty(name="Internal Infill", default=True, update=update_drawer)
    gcode_solid_infill: BoolProperty(name="Solid Infill", default=True, update=update_drawer)
    gcode_top_solid_infill: BoolProperty(name="Top Solid Infill", default=True, update=update_drawer)
    gcode_bridge_infill: BoolProperty(name="Bridge Infill", default=True, update=update_drawer)
    gcode_skirt_brim: BoolProperty(name="Skirt / Brim", default=True, update=update_drawer)
    gcode_custom: BoolProperty(name="Custom G-Code", default=True, update=update_drawer)
    gcode_support_material: BoolProperty(name="Support Material", default=True, update=update_drawer)
    gcode_support_material_interface: BoolProperty(name="Support Material Interface", default=True, update=update_drawer)
    gcode_gap_fill: BoolProperty(name="Gap Fill", default=True, update=update_drawer)