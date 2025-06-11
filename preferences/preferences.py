import bpy, os, sys

from ..registry import register_class

from ..functions.basic_functions import reset_selection
from ..classes.caching_classes import LocalCache

from .. import PACKAGE

# Configuration Lists
@register_class
class PRUSASLICER_UL_ConfListBase(bpy.types.UIList):
    filter_conf_cat = None  # Set this in subclasses
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, **kwargs) -> None:
        row = layout.row()
        row.prop(item, 'conf_enabled')
        
        # Set icon based on conf_cat
        icon = 'OUTPUT' if item.conf_cat == 'print' else ('RENDER_ANIMATION' if item.conf_cat == 'filament' else 'STATUSBAR')
        
        # Display conf_cat with icon
        sub_row = row.row(align=True)
        sub_row.label(text=item.conf_cat, icon=icon)
        sub_row.scale_x = 0.3
        
        # Display conf_label
        sub_row = row.row(align=True)
        sub_row.label(text=item.conf_label)

@register_class
class ConfListItem(bpy.types.PropertyGroup):
    def evaluate_compatibility(self, context):
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences
        prefs.evaluate_compatibility()

    conf_id: bpy.props.StringProperty(name='') # type: ignore
    conf_label: bpy.props.StringProperty(name='') # type: ignore
    conf_enabled: bpy.props.BoolProperty(name='', update=evaluate_compatibility) # type: ignore
    conf_cat: bpy.props.StringProperty(name='') # type: ignore
    conf_cache_path: bpy.props.StringProperty(name='') # type: ignore

def guess_prusaslicer_path():
    if sys.platform.startswith("win"):
        return r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe"
    elif sys.platform.startswith("darwin"):  # macOS
        return "/Applications/Original Prusa Drivers/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
    elif sys.platform.startswith("linux"):  # Linux
        return os.path.expanduser("flatpak run com.prusa3d.PrusaSlicer")

    return ''

class FrozenEval:
    def __init__(self):
        self.enabled = False

    def __enter__(self):
        self.enabled = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.enabled = False
        return False

    def __bool__(self):
        return self.enabled

frozen_eval = FrozenEval()

@register_class
class SlicerPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE
    profile_cache: LocalCache = LocalCache()

    def evaluate_compatibility(self):
        if not frozen_eval:
            self.profile_cache.evaluate_compatibility(self.enabled_printers)

    def get_filtered_printers(self) -> list[tuple[str, str, str, int]]:
        enabled_printers = [p.conf_id for p in self.prusaslicer_bundle_list if (p.conf_cat == 'printer') and p.conf_enabled]
        enum: list[tuple[str, str, str, int]] = [("","","", 0)] + sorted([(p, p.split(':')[1], p, i+1) for i, p in enumerate(enabled_printers)], key=lambda x: x[1])
        return enum

    def get_filtered_filaments(self, printer_id):
        enum: list[tuple[str, str, str, int]] = [("","","", 0)]
        if not printer_id: return enum
        compat_profiles = self.profile_cache.profiles[printer_id].compatible_profiles
        compatible_filaments = [p for p in compat_profiles if p.startswith('filament:')]
        enum += sorted([(p, p.split(':')[1].strip(), p, i+1) for i, p in enumerate(compatible_filaments)], key=lambda x: x[1])
        return enum

    def get_filtered_prints(self, printer_id):
        enum: list[tuple[str, str, str, int]] = [("","","", 0)]
        if not printer_id: return enum
        compat_profiles = self.profile_cache.profiles[printer_id].compatible_profiles
        compatible_prints = [p for p in compat_profiles if p.startswith('print:')]
        enum += sorted([(p, p.split(':')[1].strip(), p, i+1) for i, p in enumerate(compatible_prints)], key=lambda x: x[1])
        return enum

    def import_configs(self, configs):
        global frozen_eval
        with frozen_eval:
            for key, item in self.prusaslicer_bundle_list.items():
                item.conf_enabled = True if item.name in configs else False
        self.evaluate_compatibility()

    def import_physical_printers(self, physical_printers):
        for printer in physical_printers:
            item = self.physical_printers.add()
            for attr in ['ip', 'port', 'name', 'username', 'password']:
                setattr(item, attr, str(printer[attr]))
            item.host_type = printer['host_type']

    def update_config_bundle_manifest(self, context=None):
        changed, added, deleted = self.profile_cache.load([self.prusaslicer_bundles_folder, "//profiles"])

        if not changed | added | deleted: return

        old_confs = [k.conf_id for k in self.prusaslicer_bundle_list]

        for conf in old_confs:
            if conf not in self.profile_cache.profiles:
                idx = old_confs.index(conf)
                self.prusaslicer_bundle_list.remove(idx)

        for k, conf in self.profile_cache.profiles.items():
            if '*' in k: continue
            if conf.category not in ['printer']: continue
            if k in old_confs: continue

            new_item = self.prusaslicer_bundle_list.add()
            new_item.conf_id = k
            new_item.name = k
            new_item.conf_label = conf.id
            new_item.conf_cat = conf.category
            global frozen_eval
            with frozen_eval:
                new_item.conf_enabled = not conf.has_header

        self.evaluate_compatibility()
    
    default_bundles_added: bpy.props.BoolProperty()

    prusaslicer_path: bpy.props.StringProperty(
        name="PrusaSlicer path",
        description="Path or command for the PrusaSlicer executable",
        subtype='FILE_PATH',
        default=guess_prusaslicer_path(),
    )

    prusaslicer_bundles_folder: bpy.props.StringProperty(
        name="PrusaSlicer .ini bundles path",
        description="Path to the folder containing the PrusaSlicer configurations (recursive)",
        subtype='FILE_PATH',
        default="",
        update=update_config_bundle_manifest, #type: ignore
    ) 

    prusaslicer_bundle_list: bpy.props.CollectionProperty(type=ConfListItem)
    prusaslicer_bundle_list_index: bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'prusaslicer_bundle_list_index'))

    @property
    def enabled_printers(self):
        return [p.conf_id for p in self.prusaslicer_bundle_list if (p.conf_cat == 'printer') and p.conf_enabled]

    from .physical_printers import PrintersListItem
    physical_printers: bpy.props.CollectionProperty(type=PrintersListItem)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "prusaslicer_path")
        row = layout.row()
        row.prop(self, "prusaslicer_bundles_folder")

        layout.separator(type="LINE")

        row = layout.row()
        row.label(text="Configurations:")
        row = layout.row()
        active_list_id = 'prusaslicer_bundle_list'
        row.template_list('PRUSASLICER_UL_ConfListBase', f"{active_list_id}",
                self, f"{active_list_id}",
                self, f"{active_list_id}_index"
                )
        
        layout = self.layout
        row = layout.row()
        row.operator("preferences.export_slicer_configs")
        row.operator("preferences.import_slicer_configs")

        layout.separator(type="LINE")

        row = layout.row()
        row.label(text="Physical Printers:")
        row = layout.row()
        from .physical_printers import draw_list
        draw_list(layout, self.physical_printers, 'physical_printers', fields = ['ip', 'port', 'name', 'username', 'password', 'host_type'], add_operator="preferences.printers_add_item", remove_operator="preferences.printers_remove_item")

        self.update_config_bundle_manifest()