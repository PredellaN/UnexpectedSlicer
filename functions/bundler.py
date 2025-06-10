import os

from ..preferences.config_selection import select_confs_from_json
from .. import ADDON_FOLDER

select_confs_from_json(os.path.join(ADDON_FOLDER, 'bundled_conf.json'))