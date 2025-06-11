from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import Collection

import bpy
import math

from ..functions.blender_funcs import coll_from_selection
from ..functions.prusaslicer_fields import search_db
from .. import TYPES_NAME, PACKAGE

class FromPreferences():
    def get_pg(self, context):
        return context.preferences.addons[PACKAGE].preferences

class FromObject():
    def get_pg(self, context):
        return getattr(context.object, TYPES_NAME)

class FromCollection():
    def get_pg(self, context):
        collection: Collection | None= coll_from_selection()
        return getattr(collection, TYPES_NAME)

class ResetSearchTerm():
    def trigger(self, context):
        pg = getattr(self, 'get_pg')(context)
        pg.search_term = ""

def get_prop_bool(ref) -> bool:
    return True if ref.param_value == '1' else False

def set_prop_bool(ref, value: bool) -> None:
    ref.param_value = '1' if value else '0'

def get_prop_float(ref) -> float:
    return float(ref.param_value) if ref.param_value else 0

def set_prop_float(ref, value: float) -> None:
    ref.param_value = str(round(value, 5))

def get_prop_int(ref) -> int:
    return int(ref.param_value) if ref.param_value else 0

def set_prop_int(ref, value: int) -> None:
    ref.param_value = str(value)

def get_prop_perc(ref) -> float:
    if ref.param_value:
        return float(ref.param_value.rstrip('%')) if ref.param_value else 0
    return 0

def set_prop_perc(ref, value: float) -> None:
    ref.param_value = str(value)+'%'

def get_prop_angle(ref) -> float:
    return (float(ref.param_value) * math.pi) / 180

def set_prop_angle(ref, value: float) -> None:
    ref.param_value = str(round((value * 180) / math.pi, 5))

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

class PrusaSlicerEnums():
    param_id: bpy.props.StringProperty()

    def get_prop_enums(self) -> list[tuple[str, str, str]]:
        if not (param := search_db.get(self.param_id)):
            return [('','','')]
        if not (enums := param.get('enum')):
            return [('','','')]
        return [('','','')] + [(id, enum['label'], '') for id, enum in enums.items()]

    def prop_enums(self, context) -> list[tuple[str, str, str]]:
        return self.get_prop_enums()

    def get_prop_enum(self) -> int:
        if not (param := search_db.get(self.param_id)):
            return 0
        if not (enums := param.get('enum')):
            return 0
        return list(enums).index(self.param_value)+1 if self.param_value in enums else 0

    def set_prop_enum(self, value) -> None:
        self.param_value = self.get_prop_enums()[value][0]

    param_enum: bpy.props.EnumProperty(name='',
        items=prop_enums,
        get=get_prop_enum,
        set=set_prop_enum
    )