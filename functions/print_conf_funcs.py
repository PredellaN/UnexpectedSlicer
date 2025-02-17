import bpy

from .blender_funcs import ConfigLoader
from .. import PACKAGE

def calc_printer_intrinsics(pg):
    prefs = bpy.context.preferences.addons[PACKAGE].preferences
    loader = ConfigLoader()
    headers = prefs.profile_cache.config_headers
    loader.load_config(pg.printer_config_file, headers)

    pg.extruder_count = len(loader.config_dict.get('wipe', 'nan').split(','))
    
    pass