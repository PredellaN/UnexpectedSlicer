import os

from ..preferences.config_selection import select_confs_from_json
from .. import ADDON_FOLDER

path = os.path.join(ADDON_FOLDER, 'bundled_conf.json')
if os.path.exists(path): select_confs_from_json(path)