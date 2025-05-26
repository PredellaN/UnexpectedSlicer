import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ..registry import register_class

from ..functions.basic_functions import dict_from_json, dump_dict_to_json
from .. import PACKAGE

def select_confs_from_json(path):
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
    configs = dict_from_json(path)
    for key, item in prefs.prusaslicer_bundle_list.items():
        item.conf_enabled = True if item.name in configs else False

@register_class
class ImportConfigOperator(bpy.types.Operator, ImportHelper):
    bl_idname = f"preferences.import_slicer_configs"
    bl_label = "Import Selected Configurations list"

    filename_ext = ".json"

    def execute(self, context): #type: ignore
        
        path = getattr(self.properties, "filepath")
        
        try:
            select_confs_from_json(path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load configurations: {str(e)}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

@register_class
class ExportConfigOperator(bpy.types.Operator, ExportHelper):
    bl_idname = f"preferences.export_slicer_configs"
    bl_label = "Export Selected Configurations list"

    filename_ext = ".json"

    def execute(self, context): #type: ignore
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
        configs = [t[0] for t in prefs.get_filtered_bundle_items('') if t[0]]
        dump_dict_to_json(configs, getattr(self.properties,"filepath"))
        return {'FINISHED'}