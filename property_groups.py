from typing import Any
import bpy
import os

from .preferences import SlicerPreferences
from .functions.basic_functions import parse_csv_to_tuples, reset_selection
from .functions.blender_funcs import calc_printer_intrinsics
from . import ADDON_FOLDER, PACKAGE

prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore

class ParamSearchListItem(bpy.types.PropertyGroup):
    param_id: bpy.props.StringProperty(name='')
    param_name: bpy.props.StringProperty(name='')
    param_description: bpy.props.StringProperty(name='')

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

def selection_to_list(object, search_term, search_list, search_index, search_field, target_list, target_list_field):
    if getattr(object, search_index) > -1:
        selection = getattr(object,search_list)[getattr(object, search_index)]
        new_item = getattr(object, target_list).add()
        setattr(new_item, search_field, getattr(selection, target_list_field))
        reset_selection(object, search_index)
        setattr(object, search_term, "")

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

class SlicerPropertyGroup(bpy.types.PropertyGroup):

    running: bpy.props.BoolProperty(name="is running", default=False)
    progress: bpy.props.IntProperty(name="", min=0, max=100, default=0)
    progress_text: bpy.props.StringProperty(name="")

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
    
    def search_param_list(self, context):
        if not self.search_term:
            return
        
        self.search_list.clear()
        self.search_list_index = -1

        search_db_path = os.path.join(ADDON_FOLDER, 'functions', 'prusaslicer_fields.csv')
        search_db: None | list[tuple[str, ...]] = parse_csv_to_tuples(search_db_path)

        if not search_db:
            return

        filtered_tuples: list[tuple[str, ...]] | None = [tup for tup in search_db if all(word in (tup[1] + ' ' + tup[2]).lower() for word in self.search_term.lower().split())]

        if len(filtered_tuples) == 0:
            return

        sorted_tuples: list[tuple[str, ...]] = sorted(filtered_tuples, key=lambda tup: tup[0])

        for tup in sorted_tuples:
            new_item = self.search_list.add()
            new_item.param_id = tup[0]
            new_item.param_name = tup[1]
            new_item.param_description = tup[2]

    search_term : bpy.props.StringProperty(name="Search", update=search_param_list) #type: ignore
    search_list : bpy.props.CollectionProperty(type=ParamSearchListItem)
    search_list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: selection_to_list(self, 'search_term', 'search_list', 'search_list_index', 'param_id', 'list', 'param_id'))

    list : bpy.props.CollectionProperty(type=ParamsListItem)
    list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'list_index'))

    pause_list : bpy.props.CollectionProperty(type=PauseListItem)
    pause_list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'pause_list_index'))

    print_weight : bpy.props.StringProperty(name="")
    print_time : bpy.props.StringProperty(name="")