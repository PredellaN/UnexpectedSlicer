import bpy

from ..services.prusaslicer_fields import search_db

class PrusaSlicerEnums():
    param_id: bpy.props.StringProperty()
    param_value: bpy.props.StringProperty(name='')

    def get_prop_enums(self) -> list[tuple[str, str, str]]:
        if not (param := search_db.get(self.param_id)):
            return [('','','')]
        if not (enums := param.get('enum')):
            return [('','','')]
        return [('','','')] + [(id, enum['label'], '') for id, enum in enums.items()]

    def prop_enums(self, context) -> list[tuple[str, str, str]]:
        return self.get_prop_enums()

    def get_prop_enum(self) -> int:
        if not (param := search_db.get(self.param_id)): return 0
        if not (enums := param.get('enum')): return 0
        return list(enums).index(self.param_value)+1 if self.param_value in enums else 0

    def set_prop_enum(self, value) -> None:
        self.param_value = self.get_prop_enums()[value][0]

    param_enum: bpy.props.EnumProperty(name='',
        items=prop_enums, #type: ignore
        get=get_prop_enum, #type: ignore
        set=set_prop_enum #type: ignore
    ) 