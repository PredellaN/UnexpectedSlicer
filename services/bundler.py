import os
from pathlib import Path

from ..preferences.config_selection import select_confs_from_json
from .. import ADDON_FOLDER

path: Path = Path(os.path.join(ADDON_FOLDER, 'bundled_conf.json')) #This overrides the current configuration on registration
if os.path.exists(path): select_confs_from_json(path)