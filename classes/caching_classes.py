from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from pathlib import Path
import os
import tempfile
import math

from .. import ADDON_FOLDER
from .expression_parser_classes import Parser
from ..functions.ini_funcs import ini_to_dict, ini_content_to_dict
from ..functions.basic_functions import profiler

class Profile():
    def __init__(self, key: str, category: str, path: Path, has_header: bool, conf_dict: dict):
        self.id: str = key.split(':')[1] if len(key.split(':')) > 1 else key
        self.key: str = key
        self.category: str = category
        self.vendor: str = ''
        self.path: Path = path
        self.has_header: bool = has_header
        self.conf_dict: dict = conf_dict
        self.all_conf_dict: dict = {}
        self.compatible_profiles: list[str] = []
        self.compatibility_expression = None
    
    def evaluate_compatibility(self, compats):
        self.compatible_profiles = []
        if self.category.startswith('printer:'): return
        for key, compat in compats.items():
            if not compat: self.compatible_profiles.append(key); continue
            if compat.eval(self.all_conf_dict): self.compatible_profiles.append(key)
            pass
        print(f'Evaled {self.id}')

    def generate_inherited_confs(self, all_confs_dict: dict = {}):
        self.all_conf_dict = generate_conf(all_confs_dict, self.key)
        self.vendor = self.all_conf_dict.get('filament_vendor', '')

        if exp := self.all_conf_dict.get('compatible_printers_condition'):
            try:
                self.compatibility_expression = Parser(exp).parse()
            except:
                print(f'Expression parsing failed: {exp}')
        
class LocalCache:
    profiles: dict[str, Profile] = {}
    
    files_metadata: dict[str, Any] = {}

    @property
    def display_profiles(self) -> dict[str, Profile]:
        return {k: profile for k, profile in self.profiles.items() if '*' not in profile.id}

    @property
    def printers_profiles(self) -> dict[str, Profile]:
        return {k: profile for k, profile in self.display_profiles.items() if profile.category == 'printer'}

    @property
    def print_profiles(self) -> dict[str, Profile]:
        return {k: profile for k, profile in self.display_profiles.items() if profile.category == 'print'}

    @property
    def filament_profiles(self) -> dict[str, Profile]:
        return {k: profile for k, profile in self.display_profiles.items() if profile.category == 'filament'}

    def load(self, dirs: list[str])  -> tuple[dict[str, tuple[Any, Any]], dict[str, Any], dict[str, Any]]:

        old = self.files_metadata.copy()
        self._fetch_files_metadata(dirs)
        new = self.files_metadata

        changed = {k: (old[k], new[k]) for k in old.keys() & new.keys() if old[k] != new[k]}
        added = {k: new[k] for k in new.keys() - old.keys()}
        deleted = {k: old[k] for k in old.keys() - new.keys()}

        if len(changed | added | deleted) == 0: return {}, {}, {}

        for deleted_file in deleted:
            keys_to_remove = [key for key, val in self.profiles.items() if str(val.path) == deleted_file]
            for key in keys_to_remove:
                self.profiles.pop(key, None)

        for file_path in (changed | added):
            self._process_ini_to_cache_dict(file_path)

        self.files_metadata = new
        
        for k, profile in self.display_profiles.items():
            profile.generate_inherited_confs(self.profiles)

        return changed, added, deleted

    @property
    def vendors(self):
        return sorted({ p.vendor for p in self.filament_profiles.values() })

    def evaluate_compatibility(self, enabled_printers, enabled_vendors):
        for k, profile in self.printers_profiles.items():
            if k not in enabled_printers: continue
            # if profile.compatible_profiles: continue
            enabled_vendors.add("")
            enabled_filament_profiles = {k: p for k, p in self.filament_profiles.items() if p.vendor in enabled_vendors | {''}}
            profile.evaluate_compatibility({k: pp.compatibility_expression for k, pp in (enabled_filament_profiles | self.print_profiles).items()})

    def _fetch_files_metadata(self, dirs):
        self.files_metadata = {}
        # Iterate over all provided directories
        for directory in dirs:
            sanitized_path = self._sanitize_directory(directory)
            if not sanitized_path:
                continue

            # Use os.walk with followlinks=True to ensure linked folders are processed
            for root, _, files in os.walk(sanitized_path, followlinks=True):
                for file in files:
                    if file.endswith('.ini'):
                        file_path = Path(root) / file
                        try:
                            last_modified = file_path.stat().st_mtime
                            self.files_metadata[str(file_path)] = last_modified
                        except OSError as e:
                            print(f"Error reading file {file_path}: {e}")
                            continue

    def _sanitize_directory(self, dir_str: str) -> Path | None:
        if not dir_str:
            return None

        if dir_str.startswith("//"):
            sanitized = Path(ADDON_FOLDER) / Path(dir_str[2:])
        else:
            sanitized = Path(os.path.expanduser(dir_str)).resolve()

        if not sanitized.is_dir():
            print(f"Path is not a valid directory: {dir_str}")
            return None

        return sanitized

    def _process_ini_to_cache_dict(self, path: str):
        # Convert ConfigParser content into a dictionary
        has_header, ini_dict = ini_to_dict(path)

        # Flatten the dictionary for profiles and add to self.config_headers
        for key, conf_dict in ini_dict.items():
            if ":" in key:
                self.profiles[key] = Profile(
                    key,
                    key.split(':')[0] if len(key.split(':')) > 1 else '',
                    Path(path),
                    has_header,
                    conf_dict
                )

        return

    def generate_conf_writer(self, printer_profile, filament_profile, print_profile, overrides, pauses_and_changes):
        from ..functions.prusaslicer_fields import search_db
        conf = {}

        # add printer and print profile
        conf.update(self.profiles[printer_profile].all_conf_dict)
        conf.update(self.profiles[print_profile].all_conf_dict)

        # add filament profiles per extruder
        filament_merged_conf = {}
        filament_confs = [self.profiles[profile].all_conf_dict for profile in filament_profile]
        common_keys = set().union(*filament_confs)
        for key in common_keys:
            key_props = search_db.get(key)
            if not key_props: continue
            key_type: str = key_props['type']
            separator = ',' if key_type in ['coPercents', 'coFloats', 'coFloatsOrPercents', 'coInts', 'coIntsNullable', 'coBools', 'coPoints'] else ';'
            
            values = [
                d.get(key, key_props['default'])
                for d in filament_confs
            ]

            joined = separator.join(values)
            filament_merged_conf[key] = joined

        conf.update(filament_merged_conf)

        # overwrite with overrides
        conf.update({k: o['value'] for k, o in overrides.items()})

        # add pauses and changes
        conf['layer_gcode'] = self._pauses_and_changes(conf, pauses_and_changes)

        # add profile names
        conf.update({
            'printer_settings_id': printer_profile.split(":")[1],
            'filament_settings_id': ";".join(p.split(":")[1] for p in filament_profile),
            'print_settings_id': print_profile.split(":")[1],
        })

        # remove unusable keys
        # for k in ['compatible_prints', 'compatible_printers', 'compatible_printers_condition']:
        #     if k in conf: conf.pop(k)

        return ConfigWriter(conf)

    def _pauses_and_changes(self, conf, list):
        colors: list[str] = [
            "#79C543", "#E01A4F", "#FFB000", "#8BC34A", "#808080",
            "#ED1C24", "#A349A4", "#B5E61D", "#26A69A", "#BE1E2D",
            "#39B54A", "#CCCCCC", "#5A4CA2", "#D90F5A", "#A4E100",
            "#B97A57", "#3F48CC", "#F9E300", "#FFFFFF", "#00A2E8"
        ]
        combined_layer_gcode = conf.get('layer_gcode', '')
        pause_gcode = "\\n;PAUSE_PRINT\\n" + (conf.get('pause_print_gcode') or 'M0')
    
        for item in list:
            try:
                if item.param_value_type == "layer":
                    layer_num = int(item.param_value) - 1
                else:
                    layer_num = int(math.ceil(float(item.param_value) / float(conf['layer_height'])) - 1)
            except:
                continue

            if item.param_type == 'pause':
                item_gcode = pause_gcode
            elif item.param_type == 'color_change':
                color_change_gcode = f"\\n;COLOR_CHANGE,T0,{colors[0]}\\n" + (conf.get('color_change_gcode') or 'M600')
                item_gcode = color_change_gcode
                colors.append(colors.pop(0))
            elif item.param_type == 'custom_gcode' and item.param_cmd:
                custom_gcode = f"\\n;CUSTOM GCODE\\n{item.param_cmd}"
                item_gcode = custom_gcode
            else:
                continue
        
            combined_layer_gcode += f"{{if layer_num=={layer_num}}}{item_gcode}{{endif}}"

        return combined_layer_gcode 

class ConfigWriter:
    def __init__(self, conf) -> None:
        self.config_dict = conf
        self.temp_dir = tempfile.gettempdir()
    
    def write_ini_3mf(self, config_local_path):
        with open(config_local_path, 'w') as file:
            for key, val in dict(sorted(self.config_dict.items())).items():
                file.write(f"; {key} = {val}\n")

    def get(self, key, default=None):
        return self.config_dict[key]

def generate_conf(profiles, id: str):
    if not (profile := profiles.get(id)): return {}
    if not profile.conf_dict: return {}
    conf_current = profiles[id].conf_dict  # Copy to avoid modifying the original config
    if conf_current.get('inherits', False):
        curr_category = id.split(":")[0]
        inherited_ids = [curr_category + ":" + inherit_id.strip() for inherit_id in conf_current['inherits'].split(';')]  # Split on semicolon for multiple inheritance
        merged_conf = {}
        for inherit_id in inherited_ids:
            if inherit_id in profiles:
                inherited_conf = generate_conf(profiles, inherit_id)  # Recursive call for each inherited config
                merged_conf.update(inherited_conf)  # Merge each inherited config
        merged_conf.update(conf_current)  # Update with current config values (overriding inherited)
        conf_current = merged_conf
    conf_current.pop('inherits', None)
    # conf_current.pop('compatible_printers_condition', None)
    conf_current.pop('renamed_from', None)
    return conf_current