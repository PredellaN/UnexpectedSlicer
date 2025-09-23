from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any
    from bpy.types import UILayout
    from ....property_groups import ParamslistItem

def type_to_prop(param: dict[str, Any]) -> str:
    if param['type'] in ['coBool', 'coBools']:
        return 'param_bool'

    if param['type'] in ['coFloat', 'coFloats']:
        if param.get('min') == 0 and param.get('max') in [359, 360]:
            return 'param_angle'
        return 'param_float'

    if param['type'] in ['coEnum', 'coEnums']:
        return 'param_enum'

    if param['type'] in ['coInt', 'coInts']:
        return 'param_int'

    if param['type'] in ['coPercent', 'coPercents']:
        return 'param_perc'

    return 'param_value'

def draw_formatted_prop(layout: UILayout, item: ParamslistItem) -> None:
    from ....functions.prusaslicer_fields import search_db

    if not item.param_id:
        return

    if not (param := search_db.get(item.param_id)):
        layout.label(text = 'Parameter not found!')
        return

    param_prop = type_to_prop(param)

    if param_prop == 'param_bool':
        sr = layout.row()
        sr.scale_x = 0.66
        sr.label(text="")
        sr.prop(item, param_prop, index=1, text="")
        sr.label(text="")
        return

    layout.prop(item, param_prop, index=1, text="")