import os
from pathlib import Path
import tempfile
import bpy
from bpy.types import bpy_struct 

import math
from typing import cast

def _pv(inst: bpy_struct) -> 'PrusaSlicerTypes':
    return cast(PrusaSlicerTypes, inst)

def get_prop_bool(inst: bpy_struct) -> bool:
    return _pv(inst).param_value == '1'

def set_prop_bool(inst: bpy_struct, value: bool) -> None:
    _pv(inst).param_value = '1' if value else '0'

def get_prop_float(inst: bpy_struct) -> float:
    return float(_pv(inst).param_value) if _pv(inst).param_value else 0

def set_prop_float(inst: bpy_struct, value: float) -> None:
    _pv(inst).param_value = str(round(value, 5))

def get_prop_int(inst: bpy_struct) -> int:
    return int(_pv(inst).param_value) if _pv(inst).param_value else 0

def set_prop_int(inst: bpy_struct, value: int) -> None:
    _pv(inst).param_value = str(value)

def get_prop_perc(inst: bpy_struct) -> float:
    if _pv(inst).param_value:
        return float(_pv(inst).param_value.rstrip('%')) if _pv(inst).param_value else 0
    return 0

def set_prop_perc(inst: bpy_struct, value: float) -> None:
    _pv(inst).param_value = str(value)+'%'

def get_prop_angle(inst: bpy_struct) -> float:
    return (float(_pv(inst).param_value) * math.pi) / 180

def set_prop_angle(inst: bpy_struct, value: float) -> None:
    _pv(inst).param_value = str(round((value * 180) / math.pi, 5))

class PrusaSlicerTypes():
    param_value: bpy.props.StringProperty(name='')

    param_bool: bpy.props.BoolProperty(name='',
        get=get_prop_bool,
        set=set_prop_bool,
        default=False,
    ) 

    param_float: bpy.props.FloatProperty(name='',
        get=get_prop_float,
        set=set_prop_float,
        soft_min=0,
        step = 5,
    )

    param_int: bpy.props.IntProperty(name='',
        get=get_prop_int, 
        set=set_prop_int, 
    )

    param_perc: bpy.props.FloatProperty(name='',
        get=get_prop_perc, 
        set=set_prop_perc, 
        subtype='PERCENTAGE',
        soft_min=0,
        soft_max=100,
        step = 5,
    )

    param_angle: bpy.props.FloatProperty(name='',
        get=get_prop_angle, 
        set=set_prop_angle, 
        subtype='ANGLE',
        soft_min=0,
        soft_max=360,
        step = 1,
    )

class SlicingPaths():
    def __init__(self, config, obj_names: list[str], out_dir: str | Path) -> None:
        self.out_dir: str | Path = out_dir
        self.ext: str = ".bgcode" if config.config_dict.get('binary_gcode', '0') == '1' else ".gcode"
        self.checksum: str = ''
        
        #naming
        base_filename: str = "-".join(self.names_array_from_objects(obj_names))
        filament: str | list = config.config_dict.get('filament_type', 'Unknown filament')
        if isinstance(filament, list):
            filament = ";".join(filament)
        printer: str = config.config_dict.get('printer_model', 'Unknown printer')
        self.name: str = self.safe_filename(base_filename, f"-{filament}-{printer}")

        #3mf tempfile
        import tempfile
        temp_3mf_fd, path_3mf = tempfile.mkstemp(suffix=".3mf")
        os.close(temp_3mf_fd)
        self.path_3mf_temp = Path(path_3mf)

    @staticmethod
    def names_array_from_objects(obj_names: list[str]):
        import re
        from collections import Counter

        summarized_names = [re.sub(r'\.\d{0,3}$', '', name) for name in obj_names]
        name_counter = Counter(summarized_names)
        final_names = [f"{count}x_{name}" if count > 1 else name for name, count in name_counter.items()]
        final_names.sort()
        return final_names

    @staticmethod
    def safe_filename(base_txt: str, fixed_txt: str):
        allowed_base_length = 254 - len(fixed_txt)
        truncated_base = base_txt[:allowed_base_length]
        full_filename = f"{truncated_base}{fixed_txt}"
        return full_filename

    @property
    def blendfile_dir(self) -> Path:
        blendfile_path: str = bpy.data.filepath
        return Path(blendfile_path).parent if blendfile_path else Path('')

    @property
    def gcode_dir(self) -> Path:
        if self.out_dir: return Path(self.out_dir)
        else: return Path(tempfile.gettempdir())

    @property
    def path_gcode(self) -> Path:
        return Path(self.gcode_dir, self.name).with_suffix(self.ext)

    @property
    def path_gcode_temp(self) -> Path:
        if not self.checksum: return Path('')
        return Path(tempfile.gettempdir(), self.checksum).with_suffix(self.ext)

    @property
    def path_3mf(self) -> Path:
        return Path(tempfile.gettempdir(), self.name).with_suffix('.3mf')