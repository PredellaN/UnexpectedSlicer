import bpy, os, sys

from ..registry import register_class

from ..functions.basic_functions import reset_selection
from ..classes.caching_classes import LocalCache

from .. import PACKAGE

# Configuration Lists
@register_class
class PRUSASLICER_UL_ConfListBase(bpy.types.UIList):
    filter_conf_cat = None  # Set this in subclasses

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag) -> None: #type: ignore
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
    conf_id: bpy.props.StringProperty(name='') # type: ignore
    conf_label: bpy.props.StringProperty(name='') # type: ignore
    conf_enabled: bpy.props.BoolProperty(name='') # type: ignore
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

@register_class
class SlicerPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE
    profile_cache: LocalCache = LocalCache()

    def get_filtered_bundle_items(self, cat) -> list[tuple[str, str, str]]:
        items: list[tuple[str, str, str]] = [("","","")] + sorted(
            [
                (item.conf_id, item.conf_label, "")
                for item in self.prusaslicer_bundle_list
                if (item.conf_cat == cat or not cat) and item.conf_enabled
            ],
            key=lambda x: x[1]
        )
        return items

    def get_filtered_bundle_item_index(self, cat, id):
        items: list[tuple[str, str, str]] = self.get_filtered_bundle_items(cat)
        for idx, (conf_id, _, _) in enumerate(items):
            if conf_id == id:
                return idx
        return 0

    def get_filtered_bundle_item_by_index(self, cat, idx):
        items: list[tuple[str, str, str]] = self.get_filtered_bundle_items(cat)
        return items[idx] if idx < len(items) else ("", "", "")

    def update_config_bundle_manifest(self, context=None):
        has_changes = self.profile_cache.load([self.prusaslicer_bundles_folder, "//profiles"])
    
        if has_changes:
            existing_confs = [c.conf_id for c in self.prusaslicer_bundle_list]
            cache_conf_ids = set(self.profile_cache.profiles.keys())

            for idx in reversed(range(len(self.prusaslicer_bundle_list))):
                item = self.prusaslicer_bundle_list[idx]
                if item.conf_id not in cache_conf_ids:
                    self.prusaslicer_bundle_list.remove(idx)

            for key, config in self.profile_cache.profiles.items():
                if '*' in key: continue
                if config.category not in ['printer', 'filament', 'print']: continue
                if key in existing_confs: continue

                new_item = self.prusaslicer_bundle_list.add()
                new_item.conf_id = key
                new_item.name = key
                new_item.conf_label = config.id
                new_item.conf_cat = config.category
                new_item.conf_enabled = not config.has_header

        print("Profiles Reloaded")

        return
    
    default_bundles_added: bpy.props.BoolProperty() #type: ignore

    prusaslicer_path: bpy.props.StringProperty(
        name="PrusaSlicer path",
        description="Path or command for the PrusaSlicer executable",
        subtype='FILE_PATH',
        default=guess_prusaslicer_path(),
    ) #type: ignore

    prusaslicer_bundles_folder: bpy.props.StringProperty(
        name="PrusaSlicer .ini bundles path",
        description="Path to the folder containing the PrusaSlicer configurations (recursive)",
        subtype='FILE_PATH',
        default="",
        # update=update_config_bundle_manifest, #type: ignore
    ) #type: ignore

    prusaslicer_bundle_list: bpy.props.CollectionProperty(type=ConfListItem) # type: ignore
    prusaslicer_bundle_list_index: bpy.props.IntProperty(default=-1, update=lambda self, context: reset_selection(self, 'prusaslicer_bundle_list_index')) # type: ignore

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