from typing import Any
import bpy
import os

from .preferences import SlicerPreferences
from .functions.basic_functions import reset_selection
from . import ADDON_FOLDER, PACKAGE

prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore

class ParamsListItem(bpy.types.PropertyGroup):
    param_id: bpy.props.StringProperty(name='')
    param_value: bpy.props.StringProperty(name='')

class PauseListItem(bpy.types.PropertyGroup):
    param_type: bpy.props.EnumProperty(name='', items=[
        ('pause', "Pause", "Pause action"),
        ('color_change', "Color Change", "Trigger color change"),
        ('custom_gcode', "Custom Gcode", "Add a custom Gcode command"),
    ])
    param_cmd: bpy.props.StringProperty(name='')
    param_value_type: bpy.props.EnumProperty(name='', items=[
        ('layer', "on layer", "on layer"),
        ('height', "at height", "at height"),
    ])
    param_value: bpy.props.StringProperty(name='')

cached_bundle_items: list[tuple[str, str, str]] | None = None
def get_items(self, cat) -> list[tuple[str, str, str]]:
    global cached_bundle_items
    cached_bundle_items = prefs.get_filtered_bundle_items(cat)
    return cached_bundle_items

def get_enum(self, cat, attribute):
    value = prefs.get_filtered_bundle_item_index(cat, getattr(self, attribute))
    return value

def set_enum(self, value, cat, attribute):
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

class SlicerObjectPropertyGroup(bpy.types.PropertyGroup):
    object_type: bpy.props.EnumProperty(name="Part type", default="ModelPart", items=object_type_options)
    extruder: bpy.props.EnumProperty(name="Extruder", default="0", items=extruder_options)
    search_term : bpy.props.StringProperty(name="Search") #type: ignore
    modifiers: bpy.props.CollectionProperty(type=ParamsListItem)

class SlicerPropertyGroup(bpy.types.PropertyGroup):

    running: bpy.props.BoolProperty(name="is running", default=False)
    progress: bpy.props.IntProperty(name="", min=0, max=100, default=0)
    progress_text: bpy.props.StringProperty()

    config: bpy.props.StringProperty(
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

    printer_config_file: bpy.props.StringProperty()
    printer_config_file_enum: config_enum_property("Printer Configuration", 'printer', 'printer_config_file')

    filament_config_file: bpy.props.StringProperty()
    filament_config_file_enum: config_enum_property("Filament Configuration", 'filament', 'filament_config_file')

    filament_2_config_file: bpy.props.StringProperty()
    filament_2_config_file_enum: config_enum_property("E2 Filament Configuration", 'filament', 'filament_2_config_file')

    filament_3_config_file: bpy.props.StringProperty()
    filament_3_config_file_enum: config_enum_property("E3 Filament Configuration", 'filament', 'filament_3_config_file')

    filament_4_config_file: bpy.props.StringProperty()
    filament_4_config_file_enum: config_enum_property("E4 Filament Configuration", 'filament', 'filament_4_config_file')

    filament_5_config_file: bpy.props.StringProperty()
    filament_5_config_file_enum: config_enum_property("E5 Filament Configuration", 'filament', 'filament_5_config_file')

    print_config_file: bpy.props.StringProperty()
    print_config_file_enum: config_enum_property("Print Configuration", 'print', 'print_config_file')

    search_term : bpy.props.StringProperty(name="Search") #type: ignore

    list : bpy.props.CollectionProperty(type=ParamsListItem)
    list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'list_index'))

    pause_list : bpy.props.CollectionProperty(type=PauseListItem)
    pause_list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'pause_list_index'))

    print_weight : bpy.props.StringProperty()
    print_time : bpy.props.StringProperty()
    print_debug : bpy.props.StringProperty()