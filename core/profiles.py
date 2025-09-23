from pathlib import Path
from typing import Any

from .expression_parser import Parser, ExprNode

class Profile():
    def __init__(self, key: str, category: str, path: Path, has_header: bool, conf_dict: dict[str, Any]):
        self.id: str = key.split(':')[1] if len(key.split(':')) > 1 else key
        self.key: str = key
        self.category: str = category
        self.vendor: str = ''
        self.path: Path = path
        self.has_header: bool = has_header
        self.conf_dict: dict[str, Any] = conf_dict
        self.all_conf_dict: dict[str, Any] = {}
        self.compatible_profiles: list[str] = []
        self.compatibility_expression: ExprNode | None = None
    
    def evaluate_compatibility(self, compats: dict[str, ExprNode | None]):
        self.compatible_profiles = []
        if self.category.startswith('printer:'): return
        for key, compat in compats.items():
            if not compat: self.compatible_profiles.append(key); continue
            if compat.eval(self.all_conf_dict): self.compatible_profiles.append(key)
            pass
        print(f'Evaled {self.id}')

    def generate_inherited_confs(self, all_confs_dict: dict[str, Any] = {}):
        self.all_conf_dict = generate_conf(all_confs_dict, self.key)
        if self.category == 'printer': self.all_conf_dict['num_extruders'] = str(len(self.all_conf_dict['nozzle_diameter'].split(',')))
        self.vendor = self.all_conf_dict.get('filament_vendor', '')

        if exp := self.all_conf_dict.get('compatible_printers_condition'):
            try:
                self.compatibility_expression = Parser(exp).parse()
            except:
                print(f'Expression parsing failed: {exp}')

def generate_conf(profiles: dict[str, Any], id: str) -> dict[str, str]:
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
    conf_current.pop('renamed_from', None)
    return conf_current