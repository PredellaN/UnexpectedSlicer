from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any
    from bpy.types import Collection

from ..registry import register_class

from .. import TYPES_NAME
from ..classes.bpy_classes import BasePanel

@register_class
class SlicerPanel_0_Overrides(BasePanel):
    bl_label = "Configuration Overrides"
    bl_idname = f"COLLECTION_PT_{TYPES_NAME}_{__qualname__}"
    bl_parent_id = f"COLLECTION_PT_{TYPES_NAME}"

    def draw(self, context):
        from ..functions.blender_funcs import coll_from_selection

        collection: Collection | None = coll_from_selection()
        layout = self.layout
        if not layout: return

        if not collection:
            layout.row().label(text="Please select a collection")
            return

        pg = getattr(collection, TYPES_NAME)
        layout.row().prop(pg, "search_term")

        if getattr(pg, 'search_term', ""):
            from ..functions.prusaslicer_fields import search_in_db

            search_list: dict[str, dict[str, Any]] = search_in_db(pg.search_term)

            from .ui_elements.search_list import draw_search_list
            draw_search_list(layout, search_list, 'list', 'collection.list_transfer_item')
        else:
            from ..functions.blender_funcs import get_inherited_overrides

            all_overrides = get_inherited_overrides(collection, TYPES_NAME)
            inherited_overrides: list[dict[str, Any]] = [{
                'param_id': key,
                'param_value': override.get('value', ''),
            } for key, override in all_overrides.items() if override.get('inherited', False)]

            from .ui_elements.overrides_list import draw_overrides_list
            draw_overrides_list(layout, pg, "list", inherited_overrides)