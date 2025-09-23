import bpy

from typing import Literal
from bpy.types import Context

from .registry import register_class

from .preferences.preferences import SlicerPreferences
from .props.enums import PrusaSlicerEnums
from .props.property_groups import PrusaSlicerTypes

from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty

from . import PACKAGE

def clear_value(ref, context: Context) -> None:
    ref.param_value = '0'

@register_class
class ParamslistItem(bpy.types.PropertyGroup, PrusaSlicerTypes, PrusaSlicerEnums):
    param_id: StringProperty(name='', update=clear_value) # pyright: ignore[reportInvalidTypeForm]

@register_class
class PauselistItem(bpy.types.PropertyGroup, PrusaSlicerTypes):
    param_type: bpy.props.EnumProperty(name='', items=[
        ('pause', "Pause", "Pause action"),
        ('color_change', "Color Change", "Trigger color change"),
        ('custom_gcode', "Custom Gcode", "Add a custom Gcode command"),
    ]) # pyright: ignore[reportInvalidTypeForm]
    
    param_cmd: StringProperty(name='') # pyright: ignore[reportInvalidTypeForm]

    param_value_type: bpy.props.EnumProperty(name='', items=[
        ('layer', "on layer", "on layer"),
        ('height', "at height", "at height"),
    ]) # pyright: ignore[reportInvalidTypeForm]

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
    ("WipeTower", "Wipe Tower", "Wipe Tower"),
    ("Ignore", "Ignore", "Ignore"),
]

@register_class
class SlicerObjectPropertyGroup(bpy.types.PropertyGroup):
    object_type: bpy.props.EnumProperty(name="Part type", default="ModelPart", items=object_type_options) # pyright: ignore[reportInvalidTypeForm]
    extruder: bpy.props.EnumProperty(name="Extruder", default="0", items=extruder_options) # pyright: ignore[reportInvalidTypeForm]
    search_term: StringProperty(name="Search") # pyright: ignore[reportInvalidTypeForm]
    modifiers: bpy.props.CollectionProperty(type=ParamslistItem) # pyright: ignore[reportInvalidTypeForm]

def get_enum(ref, cat, attribute) -> int:
    if not (cat_dd := ref.dd_items.get(cat)): return -1
    bundle = {b[0]: b[3] for b in cat_dd}
    return bundle.get(getattr(ref, attribute), -1)

def set_enum(ref, value, cat, attribute) -> None:
    if not (cat_dd := ref.dd_items.get(cat)): return
    bundle = {b[3]: b[0] for b in cat_dd}
    setattr(ref, attribute, bundle[value])
    pass

@register_class
class SlicerPropertyGroup(bpy.types.PropertyGroup):

    running: bpy.props.BoolProperty(name="is running", default=False) # pyright: ignore[reportInvalidTypeForm]
    progress: bpy.props.IntProperty(name="", min=0, max=100, default=0) # pyright: ignore[reportInvalidTypeForm]
    progress_text: StringProperty() # pyright: ignore[reportInvalidTypeForm]

    config: StringProperty(
        name="PrusaSlicer Configuration (.ini)", 
        subtype='FILE_PATH'
    ) # pyright: ignore[reportInvalidTypeForm]

    use_single_config: bpy.props.BoolProperty(
        name="Single Configuration",
        description="Use a single .ini configuration file",
        default=True
    ) # pyright: ignore[reportInvalidTypeForm]

    dd_items: dict[str, list[tuple[Literal['printer'], Literal['print'], Literal['filament']]]] = { 'printer': [], 'print': [], 'filament': [] } ## There is a known bug with using a callback, Python must keep a reference to the strings returned by the callback or Blender will misbehave or even crash.

    def get_printers(self) -> list[tuple[str, str, str]]:
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore
        self.dd_items['printer'] = prefs.get_filtered_printers()
        return self.dd_items['printer']
    
    def get_filament(self) -> list[tuple[str, str, str]]:
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore
        self.dd_items['filament'] = prefs.get_filtered_filaments(self.printer_config_file)
        return self.dd_items['filament']

    def get_print(self) -> list[tuple[str, str, str]]:
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore
        self.dd_items['print'] = prefs.get_filtered_prints(self.printer_config_file)
        return self.dd_items['print']

    @staticmethod
    def config_enum_property(name, cat: str, attribute):
        if cat == 'printer': func = 'get_printers'
        elif cat == 'filament': func = 'get_filament'
        else: func = 'get_print'
        return bpy.props.EnumProperty(
            name=name,
            items=lambda self, context: getattr(self, func)(),
            get=lambda self: get_enum(self, cat, attribute),
            set=lambda self, value: set_enum(self, value, cat, attribute),
        )

    printer_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    printer_config_file_enum: config_enum_property("Printer Configuration", 'printer', 'printer_config_file') # pyright: ignore[reportInvalidTypeForm]

    filament_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    filament_config_file_enum: config_enum_property("Filament Configuration", 'filament', 'filament_config_file') # pyright: ignore[reportInvalidTypeForm]

    filament_2_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    filament_2_config_file_enum: config_enum_property("E2 Filament Configuration", 'filament', 'filament_2_config_file') # pyright: ignore[reportInvalidTypeForm]

    filament_3_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    filament_3_config_file_enum: config_enum_property("E3 Filament Configuration", 'filament', 'filament_3_config_file') # pyright: ignore[reportInvalidTypeForm]

    filament_4_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    filament_4_config_file_enum: config_enum_property("E4 Filament Configuration", 'filament', 'filament_4_config_file') # pyright: ignore[reportInvalidTypeForm]

    filament_5_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    filament_5_config_file_enum: config_enum_property("E5 Filament Configuration", 'filament', 'filament_5_config_file') # pyright: ignore[reportInvalidTypeForm]

    print_config_file: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    print_config_file_enum: config_enum_property("Print Configuration", 'print', 'print_config_file') # pyright: ignore[reportInvalidTypeForm]

    search_term: StringProperty(name="Search") # pyright: ignore[reportInvalidTypeForm]

    # configuration
    list: bpy.props.CollectionProperty(type=ParamslistItem) # pyright: ignore[reportInvalidTypeForm]
    list_index: bpy.props.IntProperty(default=-1, set=lambda self, value: None) # pyright: ignore[reportInvalidTypeForm]

    # pauses
    pause_list: bpy.props.CollectionProperty(type=PauselistItem) # pyright: ignore[reportInvalidTypeForm]
    pause_list_index: bpy.props.IntProperty(default=-1, set=lambda self, value: None) # pyright: ignore[reportInvalidTypeForm]

    # output
    print_gcode: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    print_weight: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    print_time: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    print_stderr: StringProperty() # pyright: ignore[reportInvalidTypeForm]
    print_stdout: StringProperty() # pyright: ignore[reportInvalidTypeForm]

def update_drawer(ref, context):
    from .ui.gcode_preview import drawer
    if drawer.batch:
        drawer.update()

@register_class
class SlicerWorkspacePropertyGroup(bpy.types.PropertyGroup):
    ## GCODE PREVIEW
    gcode_preview_internal : BoolProperty(name="Enable to use internal gcode preview\nBinary gcode not currently supported") # pyright: ignore[reportInvalidTypeForm]

    gcode_preview_view: EnumProperty(name='', items=[
        ("feature_type", "Feature Type", ""),
        ("height", "Height (mm)", ""),
        ("width", "Width (mm)", ""),
        ("fan_speed", "Fan speed (%)", ""),
        ("temperature", "Temperature (C)", ""),
        ("tool", "Tool", ""),
        ("color", "Color", ""),
    ], default=0, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]

    gcode_preview_min_z: FloatProperty(name="Gcode preview minimum Z", min = 0, max = 1000, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_preview_max_z: FloatProperty(name="Gcode preview maximum Z", min = 0, max = 1000, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]

    gcode_perimeter: BoolProperty(name="Perimeter", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_external_perimeter: BoolProperty(name="External Perimeter", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_overhang_perimeter: BoolProperty(name="Overhang Perimeter", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_internal_infill: BoolProperty(name="Internal Infill", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_solid_infill: BoolProperty(name="Solid Infill", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_top_solid_infill: BoolProperty(name="Top Solid Infill", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_bridge_infill: BoolProperty(name="Bridge Infill", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_skirt_brim: BoolProperty(name="Skirt / Brim", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_custom: BoolProperty(name="Custom G-Code", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_support_material: BoolProperty(name="Support Material", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_support_material_interface: BoolProperty(name="Support Material Interface", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]
    gcode_gap_fill: BoolProperty(name="Gap Fill", default=True, update=update_drawer) # pyright: ignore[reportInvalidTypeForm]