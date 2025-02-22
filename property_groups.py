from typing import Any
import bpy
import os

from .preferences import PrusaSlicerPreferences
from .functions.basic_functions import parse_csv_to_tuples, reset_selection
from .functions.print_conf_funcs import calc_printer_intrinsics
from . import ADDON_FOLDER, PACKAGE

prefs: PrusaSlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore

class ParamSearchListItem(bpy.types.PropertyGroup):
    param_id: bpy.props.StringProperty(name='') # type: ignore
    param_name: bpy.props.StringProperty(name='') # type: ignore
    param_description: bpy.props.StringProperty(name='') # type: ignore

class ParamsListItem(bpy.types.PropertyGroup):
    param_id: bpy.props.StringProperty(name='') # type: ignore
    param_value: bpy.props.StringProperty(name='') # type: ignore

class PauseListItem(bpy.types.PropertyGroup):
    param_type: bpy.props.EnumProperty(name='', items=[
        ('pause', "Pause", "Pause action"),
        ('color_change', "Color Change", "Trigger color change"),
        ('custom_gcode', "Custom Gcode", "Add a custom Gcode command"),
    ]) # type: ignore
    param_cmd: bpy.props.StringProperty(name='') # type: ignore
    param_value_type: bpy.props.EnumProperty(name='', items=[
        ('layer', "on layer", "on layer"),
        ('height', "at height", "at height"),
    ]) # type: ignore
    param_value: bpy.props.StringProperty(name='') # type: ignore

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
    calc_printer_intrinsics(self)

class PrusaSlicerPropertyGroup(bpy.types.PropertyGroup):

    running: bpy.props.BoolProperty(name="is running", default=0) # type: ignore
    progress: bpy.props.IntProperty(name="", min=0, max=100, default=0) # type: ignore
    progress_text: bpy.props.StringProperty(name="") # type: ignore

    config: bpy.props.StringProperty(
        name="PrusaSlicer Configuration (.ini)", 
        subtype='FILE_PATH'
    ) # type: ignore

    use_single_config: bpy.props.BoolProperty(
        name="Single Configuration",
        description="Use a single .ini configuration file",
        default=True
    ) # type: ignore

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

    search_term : bpy.props.StringProperty(name="Search", update=search_param_list) # type: ignore
    search_list : bpy.props.CollectionProperty(type=ParamSearchListItem) # type: ignore
    search_list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: selection_to_list(self, 'search_term', 'search_list', 'search_list_index', 'param_id', 'list', 'param_id')) # type: ignore

    list : bpy.props.CollectionProperty(type=ParamsListItem) # type: ignore
    list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'list_index')) # type: ignore

    pause_list : bpy.props.CollectionProperty(type=PauseListItem) # type: ignore
    pause_list_index : bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'pause_list_index')) # type: ignore

    print_weight : bpy.props.StringProperty(name="") # type: ignore
    print_time : bpy.props.StringProperty(name="") # type: ignore

    ### UI Parameters
    extruder_count : bpy.props.IntProperty(default=1)