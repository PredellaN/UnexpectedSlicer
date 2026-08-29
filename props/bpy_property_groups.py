import bpy

from typing import Literal
from bpy.types import Context

from ..registry import register_class

from ..preferences.preferences import SlicerPreferences
from ..props.enums import PrusaSlicerEnums
from ..props.property_groups import PrusaSlicerTypes

from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty, FloatVectorProperty, PointerProperty

from .. import PACKAGE, TYPES_NAME

def update_param_id(ref, context: Context) -> None:
    if " — " in ref.param_id:
        ref.param_id = ref.param_id.split(" — ")[0]
    ref.param_value = '0'

    id_data = getattr(ref, "id_data", None)
    if id_data:
        for attr in ['list', 'modifiers']:
            if hasattr(id_data, TYPES_NAME):
                pg = getattr(id_data, TYPES_NAME)
                if hasattr(pg, attr):
                    data = getattr(pg, attr)
                    if ref in list(data):
                        if not len(data) or data[-1].param_id != "":
                            data.add()
                        break

def search_param_id(self, context, edit_text: str) -> list[str]:
    from ..services.prusaslicer_fields import search_in_db, search_in_mod_db

    id_data = getattr(self, "id_data", None)
    if isinstance(id_data, bpy.types.Object):
        matches = search_in_mod_db(edit_text)
    else:
        matches = search_in_db(edit_text)

    items: list[str] = []
    for k, v in matches.items():
        label: str = v.get('label') or ''
        
        if label:
            item_str = f"{k} — {label}"
        else:
            item_str = k
            
        items.append(item_str)

    if edit_text:
        return [item for item in items if edit_text.lower() in item.lower()]
    return items

@register_class
class ParamslistItem(bpy.types.PropertyGroup, PrusaSlicerTypes, PrusaSlicerEnums):
    param_id: StringProperty(name='', update=update_param_id, search=search_param_id)

@register_class
class PauselistItem(bpy.types.PropertyGroup, PrusaSlicerTypes):
    param_type: bpy.props.EnumProperty(name='', items=[
        ('pause', "Pause", "Pause action"),
        ('color_change', "Color Change", "Trigger color change"),
        ('custom_gcode', "Custom Gcode", "Add a custom Gcode command"),
    ])
    
    param_cmd: StringProperty(name='')
    param_color: FloatVectorProperty(
        name='Color',
        subtype='COLOR',
        size=3, # R, G, B
        min=0.0, max=1.0,
        default=(1.0, 0.0, 0.0),
    )

    param_value_type: bpy.props.EnumProperty(name='', items=[
        ('layer', "on layer", "on layer"),
        ('height', "at height", "at height"),
    ])

def update_virtual_extruder(self, context):
    ratios = list(self.ratios)
    
    non_zero_indices = [i for i, r in enumerate(ratios) if r > 0.0]
    if len(non_zero_indices) > 3:
        sorted_indices = sorted(non_zero_indices, key=lambda i: ratios[i], reverse=True)
        for i in sorted_indices[3:]:
            ratios[i] = 0.0

    changed = False
    for i in range(5):
        if abs(self.ratios[i] - ratios[i]) > 1e-5:
            changed = True
            break
            
    if changed:
        for i in range(5):
            self.ratios[i] = ratios[i]

@register_class
class VirtualExtruderItem(bpy.types.PropertyGroup):
    ratios: FloatVectorProperty(
        name="Extruder Ratios",
        size=5,
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0, 0.0, 0.0),
        update=update_virtual_extruder,
    )

object_type_options: list[tuple[str, str, str, int]] = [
    ("ModelPart", "Part", "Model Part", 0),
    ("NegativeVolume", "Negative Volume", "Negative Volume", 1),
    ("ParameterModifier", "Modifier", "Modifier", 2),
    ("SupportBlocker", "Support Blocker", "Support Blocker", 3),
    ("SupportEnforcer", "Support Enforcer", "Support Enforcer", 4),
    ("Ignore", "Ignore", "Ignore", 6),
]

@register_class
class SlicerObjectPropertyGroup(bpy.types.PropertyGroup):
    object_type: bpy.props.EnumProperty(name="Part type", default="ModelPart", items=object_type_options)
    extruder: bpy.props.IntProperty(name="Extruder", default=0, min=0)
    modifiers: bpy.props.CollectionProperty(type=ParamslistItem)

def get_effective_printer_id(pg) -> str:
    if pg.printer_config_file:
        return pg.printer_config_file

    id_data = getattr(pg, "id_data", None)
    if isinstance(id_data, bpy.types.Collection):
        from ..infra.blender_bridge import get_collection_parents, get_inherited_prop
        coll_hierarchy = get_collection_parents(id_data)
        if coll_hierarchy:
            printer_info = get_inherited_prop(TYPES_NAME, coll_hierarchy, 'printer_config_file')
            return printer_info.get('prop', '')
    return ''

def search_printer_profiles(self, context, edit_text: str) -> list[str]:
    prefs: SlicerPreferences = context.preferences.addons[PACKAGE].preferences  # type: ignore
    printers = prefs.get_filtered_printers()
    if edit_text:
        return [p for p in printers if edit_text.lower() in p.lower()]
    return printers

def search_filament_profiles(self, context, edit_text: str) -> list[str]:
    prefs: SlicerPreferences = context.preferences.addons[PACKAGE].preferences  # type: ignore
    printer_id = get_effective_printer_id(self)
    filaments = prefs.get_filtered_filaments(printer_id)
    if edit_text:
        return [f for f in filaments if edit_text.lower() in f.lower()]
    return filaments

def search_print_profiles(self, context, edit_text: str) -> list[str]:
    prefs: SlicerPreferences = context.preferences.addons[PACKAGE].preferences  # type: ignore
    printer_id = get_effective_printer_id(self)
    prints = prefs.get_filtered_prints(printer_id)
    if edit_text:
        return [p for p in prints if edit_text.lower() in p.lower()]
    return prints

@register_class
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

    printer_config_file: StringProperty(
        name="Printer Configuration",
        search=search_printer_profiles
    )

    filament_config_file: StringProperty(
        name="Filament Configuration",
        search=search_filament_profiles
    )
    filament_color: FloatVectorProperty(name='Color', subtype='COLOR_GAMMA', size=3, min=0.0, max=1.0, default=(1., 0.501961, 0.))

    filament_2_config_file: StringProperty(
        name="E2 Filament Configuration",
        search=search_filament_profiles
    )
    filament_2_color: FloatVectorProperty(name='Color', subtype='COLOR_GAMMA', size=3, min=0.0, max=1.0, default=(0.858824, 0.317647, 0.509804))

    filament_3_config_file: StringProperty(
        name="E3 Filament Configuration",
        search=search_filament_profiles
    )
    filament_3_color: FloatVectorProperty(name='Color', subtype='COLOR_GAMMA', size=3, min=0.0, max=1.0, default=(0.243137, 0.752941, 1.))

    filament_4_config_file: StringProperty(
        name="E4 Filament Configuration",
        search=search_filament_profiles
    )
    filament_4_color: FloatVectorProperty(name='Color', subtype='COLOR_GAMMA', size=3, min=0.0, max=1.0, default=(1., 0.309804, 0.309804))

    filament_5_config_file: StringProperty(
        name="E5 Filament Configuration",
        search=search_filament_profiles
    )
    filament_5_color: FloatVectorProperty(name='Color', subtype='COLOR_GAMMA', size=3, min=0.0, max=1.0, default=(0.984314, 0.921569, 0.490196))

    print_config_file: StringProperty(
        name="Print Configuration",
        search=search_print_profiles
    )

    # configuration
    list: bpy.props.CollectionProperty(type=ParamslistItem)
    list_index: bpy.props.IntProperty(default=-1, set=lambda self, value: None, get=lambda self: -1)

    # pauses
    pause_list: bpy.props.CollectionProperty(type=PauselistItem)
    pause_list_index: bpy.props.IntProperty(default=-1, set=lambda self, value: None, get=lambda self: -1)

    # virtual extruders
    virtual_extruders: bpy.props.CollectionProperty(type=VirtualExtruderItem)

    # wipe tower
    wipe_tower_mode: EnumProperty(
        name="Source",
        items=[
            ("AUTO", "Auto", "Place wipe tower 2cm above the top-left of the model"),
            ("COORDINATES", "Coordinates", "Set printbed XY position and rotation"),
            ("OBJECT", "Object Picker", "Take location and rotation from an object"),
        ],
        default="AUTO",
    )
    wipe_tower_location: FloatVectorProperty(
        name="Location",
        description="Wipe tower XY position on the printbed",
        size=2,
        default=(0.17, 0.14),
        unit='LENGTH',
    )
    wipe_tower_rotation: FloatProperty(
        name="Rotation",
        description="Wipe tower rotation angle",
        default=0.0,
        unit='ROTATION',
    )
    wipe_tower_object: PointerProperty(
        type=bpy.types.Object,
        name="Object",
    )

    # output
    print_gcode: StringProperty()
    print_weight: StringProperty()
    print_time: StringProperty()
    print_stderr: StringProperty()
    print_stdout: StringProperty()

def update_drawer(ref, context):
    from ..ui.gcode_preview import drawer
    if drawer.gcode:
        drawer.update()

@register_class
class SlicerWorkspacePropertyGroup(bpy.types.PropertyGroup):
    ## GCODE PREVIEW
    gcode_preview_internal : BoolProperty(name="Enable to use internal gcode preview\nBinary gcode not currently supported")

    gcode_preview_view: EnumProperty(name='', items=[
        ("feature_type", "Feature Type", ""),
        ("height", "Height (mm)", ""),
        ("width", "Width (mm)", ""),
        ("fan_speed", "Fan speed (%)", ""),
        ("temperature", "Temperature (C)", ""),
        ("tool", "Tool", ""),
        ("color", "Color", ""),
    ], default=0, update=update_drawer)

    gcode_preview_min_z: FloatProperty(name="Gcode preview minimum Z", min = 0, max = 1000, update=update_drawer)
    gcode_preview_max_z: FloatProperty(name="Gcode preview maximum Z", min = 0, max = 1000, update=update_drawer)

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