import bpy
from bpy.types import Collection

import math

from .blender_funcs import coll_from_selection
from .prusaslicer_fields import search_db
from .. import TYPES_NAME

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

class PrusaSlicerTypes():
    param_value: bpy.props.StringProperty(name='')

    ## BOOL
    def get_prop_bool(self) -> bool:
        return True if self.param_value == '1' else False

    def set_prop_bool(self, value: bool) -> None:
        self.param_value = '1' if value else '0'

    param_bool: bpy.props.BoolProperty(name='',
        get=get_prop_bool, #type: ignore
        set=set_prop_bool, #type: ignore
        default=False,
    )

    ## FLOAT
    def get_prop_float(self) -> float:
        return float(self.param_value) if self.param_value else 0

    def set_prop_float(self, value: float) -> None:
        self.param_value = str(round(value, 5))

    param_float: bpy.props.FloatProperty(name='',
        get=get_prop_float, #type: ignore
        set=set_prop_float, #type: ignore
        soft_min=0,
        step = 5,
    )

    ## INT
    def get_prop_int(self) -> int:
        return int(self.param_value) if self.param_value else 0

    def set_prop_int(self, value: int) -> None:
        self.param_value = str(value)

    param_int: bpy.props.IntProperty(name='',
        get=get_prop_int, #type: ignore
        set=set_prop_int, #type: ignore
    )

    ## PERCENT
    def get_prop_perc(self) -> float:
        if self.param_value:
            return float(self.param_value.rstrip('%')) if self.param_value else 0
        return 0

    def set_prop_perc(self, value: str) -> None:
        self.param_value = str(value)+'%'

    param_perc: bpy.props.FloatProperty(name='',
        get=get_prop_perc, #type: ignore
        set=set_prop_perc, #type: ignore
        subtype='PERCENTAGE',
        soft_min=0,
        soft_max=100,
        step = 5,
    )

    ## ANGLE
    def get_prop_angle(self) -> float:
        return (float(self.param_value) * math.pi) / 180

    def set_prop_angle(self, value: float) -> None:
        self.param_value = str(round((value * 180) / math.pi, 5))

    param_angle: bpy.props.FloatProperty(name='',
        get=get_prop_angle, #type: ignore
        set=set_prop_angle, #type: ignore
        subtype='ANGLE',
        soft_min=0,
        soft_max=360,
        step = 1,
    )

class PrusaSlicerEnums():
    param_id: bpy.props.StringProperty()

    ## ENUM
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