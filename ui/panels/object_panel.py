from bpy.types import Panel

from ...registry import register_class

from ... import TYPES_NAME

@register_class
class SlicerObjectPanel(Panel):
    bl_label = "UnexpectedSlicer"
    bl_idname = f"OBJECT_PT_{TYPES_NAME}"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    
    def draw(self, context):
        layout = self.layout
        if not layout: return
        
        obj = context.object
        
        pg = getattr(obj, TYPES_NAME)
        layout.prop(pg, "object_type", text="Object type")
        layout.prop(pg, "extruder", text="Extruder")
        if pg.object_type == 'ParameterModifier':
            
            layout.row().prop(pg, "search_term")
            if pg.search_term:
                from ...functions.prusaslicer_fields import search_in_mod_db
                search_list: dict[str, dict] = search_in_mod_db(term=pg.search_term)

                from .ui_elements.search_list import draw_search_list
                draw_search_list(layout, search_list, 'modifiers', 'object.list_transfer_item')
            else:
                from .ui_elements.overrides_list import draw_object_overrides_list
                draw_object_overrides_list(layout, pg, 'modifiers')