from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy._typing.rna_enums import OperatorReturnItems
    from ..preferences.preferences import SlicerPreferences
    from pathlib import Path

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ..registry import register_class

from ..functions.basic_functions import dict_from_json, dump_dict_to_json
from .. import PACKAGE

def select_confs_from_json(path: str | Path):
    prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore

    imported_prefs = dict_from_json(path)

    if imported_prefs.get('configs'):
        prefs.update_config_bundle_manifest()
        prefs.import_configs(imported_prefs['configs'])

    if imported_prefs.get('printers'):
        prefs.import_physical_printers(imported_prefs['printers'])

@register_class
class ImportConfigOperator(bpy.types.Operator, ImportHelper):
    bl_idname = f"preferences.import_slicer_configs"
    bl_label = "Import Configuration"

    filename_ext = ".json"

    def execute(self, context)-> set[OperatorReturnItems]:
        
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
    bl_label = "Export Configuration"

    filename_ext = ".json"

    def execute(self, context)-> set[OperatorReturnItems]:
        prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences # type: ignore
        prefs = {
            'configs': [t[0] for t in prefs.get_filtered_bundle_items('') if t[0]],
            'printers': [{
                    'name': p.name,
                    'host_type': p.host_type,
                    'ip': p.ip,
                    'port': p.port,
                    'username': p.username,
                    'password': p.password,
                } for p in prefs.physical_printers]
        }
        
        dump_dict_to_json(prefs, getattr(self.properties,"filepath"))
        return {'FINISHED'}