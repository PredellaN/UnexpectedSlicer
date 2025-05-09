print('DEVELOPMENT MODE')

import bpy

from .preferences.preferences import SlicerPreferences
from .preferences.config_selection import select_confs_from_json
from . import PACKAGE

from .preferences.preferences import are_profiles_loaded

prefs: SlicerPreferences = bpy.context.preferences.addons[PACKAGE].preferences #type: ignore
prefs.prusaslicer_path = 'switcherooctl -g 1 flatpak run com.prusa3d.PrusaSlicer'


if not are_profiles_loaded:
    prefs.update_config_bundle_manifest()

select_confs_from_json('/home/nicolas/Antek Latvia/Workspace/Design Projects/MOS-Project-Files/exported_conf.json')

from .constants import PRINTERS
printers = [p for p in PRINTERS]
for printer in printers:
    item = prefs.physical_printers.add()
    for attr in ['ip', 'port', 'name', 'username', 'password', 'host_type']:
        item[attr] = str(printer[attr])