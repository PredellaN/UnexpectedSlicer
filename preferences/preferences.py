from typing import Any
from bpy.types import Context, UILayout

import bpy, os, sys

from ..preferences.physical_printers import PrintersListItem
from ..registry import register_class
from ..classes.caching_classes import LocalCache
from .. import PACKAGE

# Configuration lists
@register_class
class PRUSASLICER_UL_ConfListBase(bpy.types.UIList):
    def draw_item(self, context: Context, layout: UILayout, data: Any, item: Any, icon: int | None, active_data: Any, active_property: str | None, index: int | None, flt_flag: int | None) -> None:
        row = layout.row()
        row.prop(item, 'conf_enabled')
        
        # Set icon based on conf_cat
        ico: str = 'OUTPUT' if item.conf_cat == 'print' else ('RENDER_ANIMATION' if item.conf_cat == 'filament' else 'STATUSBAR')
        
        # Display conf_cat with icon
        sub_row = row.row(align=True)
        sub_row.label(text=item.conf_cat, icon=ico)
        sub_row.scale_x = 0.3
        
        # Display conf_label
        sub_row = row.row(align=True)
        sub_row.label(text=item.conf_label)

@register_class
class PRUSASLICER_UL_FilamentVendorList(bpy.types.UIList):
    def draw_item(self, context: Context, layout: UILayout, data: Any, item: Any, icon: int | None, active_data: Any, active_property: str | None, index: int | None, flt_flag: int | None) -> None:
        row = layout.row()
        row.prop(item, 'conf_enabled')
        
        sub_row = row.row(align=True)
        sub_row.label(text=item.conf_id)

def evaluate_compatibility(ref: Any, context: Context) -> None:
    if not bpy.context.preferences: return
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences
    prefs.evaluate_compatibility()

@register_class
class ConflistItem(bpy.types.PropertyGroup):
    conf_id: bpy.props.StringProperty(name='')
    conf_label: bpy.props.StringProperty(name='')
    conf_enabled: bpy.props.BoolProperty(name='', update=evaluate_compatibility)
    conf_cat: bpy.props.StringProperty(name='')
    conf_cache_path: bpy.props.StringProperty(name='')

@register_class
class FilamentVendorItem(bpy.types.PropertyGroup):
    conf_id: bpy.props.StringProperty(name='')
    conf_enabled: bpy.props.BoolProperty(name='', update=evaluate_compatibility)

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
            self.profile_cache.evaluate_compatibility(self.enabled_printers, self.enabled_vendors)

    def get_filtered_printers(self) -> list[tuple[str, str, str, int]]:
        enabled_printers: list[str] = [p.conf_id for p in self.prusaslicer_bundle_list if (p.conf_cat == 'printer') and p.conf_enabled]
        enum: list[tuple[str, str, str, int]] = [("","","", 0)] + sorted([(p, p.split(':')[1], p, i+1) for i, p in enumerate(enabled_printers)], key=lambda x: x[1])
        return enum

    def get_filtered_filaments(self, printer_id: str):
        enum: list[tuple[str, str, str, int]] = [("","","", 0)]
        if not printer_id: return enum
        compat_profiles = self.profile_cache.profiles[printer_id].compatible_profiles
        compatible_filaments = [p for p in compat_profiles if p.startswith('filament:')]
        enum += sorted([(p, p.split(':')[1].strip(), p, i+1) for i, p in enumerate(compatible_filaments)], key=lambda x: x[1])
        return enum

    def get_filtered_prints(self, printer_id: str):
        enum: list[tuple[str, str, str, int]] = [("","","", 0)]
        if not printer_id: return enum
        compat_profiles = self.profile_cache.profiles[printer_id].compatible_profiles
        compatible_prints = [p for p in compat_profiles if p.startswith('print:')]
        enum += sorted([(p, p.split(':')[1].strip(), p, i+1) for i, p in enumerate(compatible_prints)], key=lambda x: x[1])
        return enum

    def import_configs(self, configs: list[str]):
        global frozen_eval
        with frozen_eval:
            for key, item in self.prusaslicer_bundle_list.items():
                item.conf_enabled = True if item.name in configs else False
        self.evaluate_compatibility()

    def import_physical_printers(self, physical_printers: list[dict[str, str]]):
        global frozen_eval
        with frozen_eval:
            for printer in physical_printers:
                item: PrintersListItem = self.physical_printers.add()
                for attr in ['ip', 'port', 'prefix', 'name', 'username', 'password']:
                    if val := printer.get(attr):
                        setattr(item, attr, str(val))
                item.host_type = printer['host_type']
                
        from .physical_printers import update_querier
        update_querier()

    def update_config_bundle_manifest(self, context=None): 
        global frozen_eval
        
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

            bundle_item = self.prusaslicer_bundle_list.add()
            bundle_item.conf_id = k
            bundle_item.name = k
            bundle_item.conf_label = conf.id
            bundle_item.conf_cat = conf.category
           
            with frozen_eval:
                bundle_item.conf_enabled = not conf.has_header


        vendors = self.profile_cache.vendors
        old_vendors = [k.conf_id for k in self.prusaslicer_filament_vendor_list]

        for conf in old_vendors:
            if conf not in vendors:
                idx = old_vendors.index(conf)
                self.prusaslicer_filament_vendor_list.remove(idx)

        for v in vendors:
            if v in old_vendors: continue

            vendor_item = self.prusaslicer_filament_vendor_list.add()
            vendor_item.conf_id = v
            vendor_item.name = v
            
            if v == 'Generic':
                with frozen_eval:
                    vendor_item.conf_enabled = True

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

    prusaslicer_filament_vendor_list: bpy.props.CollectionProperty(type=FilamentVendorItem)
    prusaslicer_filament_vendor_list_index: bpy.props.IntProperty(default=-1, set=lambda self, value: None)

    @property
    def enabled_vendors(self) -> set[str]:
        return {p.conf_id for p in self.prusaslicer_filament_vendor_list if p.conf_enabled}

    prusaslicer_bundle_list: bpy.props.CollectionProperty(type=ConflistItem)
    prusaslicer_bundle_list_index: bpy.props.IntProperty(default=-1, set=lambda self, value: None)

    @property
    def enabled_printers(self) -> set[str]:
        return {p.conf_id for p in self.prusaslicer_bundle_list if (p.conf_cat == 'printer') and p.conf_enabled}

    from .physical_printers import PrintersListItem
    physical_printers: bpy.props.CollectionProperty(type=PrintersListItem)

    def draw(self, context) -> None:
        layout = self.layout
        row = layout.row()
        row.prop(self, "prusaslicer_path")
        row = layout.row()
        row.prop(self, "prusaslicer_bundles_folder")

        layout.separator(type="LINE")

        row = layout.row()
        row.label(text="Filament Vendors:")
        row = layout.row()
        active_list_id = 'prusaslicer_filament_vendor_list'
        row.template_list('PRUSASLICER_UL_FilamentVendorList', f"{active_list_id}",
                self, f"{active_list_id}",
                self, f"{active_list_id}_index"
                )

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
        draw_list(layout, self.physical_printers, 'physical_printers', fields = ['ip', 'port', 'prefix', 'name', 'username', 'password', 'host_type'], add_operator="preferences.printers_add_item", remove_operator="preferences.printers_remove_item")

        self.update_config_bundle_manifest()