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
    param_value: bpy.props.StringProperty(name='') # pyright: ignore[reportInvalidTypeForm]

    param_bool: bpy.props.BoolProperty(name='',
        get=get_prop_bool,
        set=set_prop_bool,
        default=False,
    ) # pyright: ignore[reportInvalidTypeForm]

    param_float: bpy.props.FloatProperty(name='',
        get=get_prop_float,
        set=set_prop_float,
        soft_min=0,
        step = 5,
    ) # pyright: ignore[reportInvalidTypeForm]

    param_int: bpy.props.IntProperty(name='',
        get=get_prop_int, 
        set=set_prop_int, 
    ) # pyright: ignore[reportInvalidTypeForm]

    param_perc: bpy.props.FloatProperty(name='',
        get=get_prop_perc, 
        set=set_prop_perc, 
        subtype='PERCENTAGE',
        soft_min=0,
        soft_max=100,
        step = 5,
    ) # pyright: ignore[reportInvalidTypeForm]

    param_angle: bpy.props.FloatProperty(name='',
        get=get_prop_angle, 
        set=set_prop_angle, 
        subtype='ANGLE',
        soft_min=0,
        soft_max=360,
        step = 1,
    ) # pyright: ignore[reportInvalidTypeForm]