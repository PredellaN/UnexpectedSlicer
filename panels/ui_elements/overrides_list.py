from bpy.types import UILayout, bpy_prop_collection, PropertyGroup

from ...property_groups import ParamsListItem


def draw_item(layout: UILayout, item: ParamsListItem):
    layout.prop(item, 'param_id', index=1, text="")

    from .props import draw_formatted_prop
    draw_formatted_prop(layout, item)

def draw_override_items(layout: UILayout, data: bpy_prop_collection, list_id: str, remove_operator: str):
    for idx, item in enumerate(data):
        row = layout.row(align=True)
        
        if remove_operator:
            from .operators import create_operator_row
            create_operator_row(row, remove_operator, list_id, idx, 'X')

        draw_item(row, item)

def draw_object_overrides_list(layout: UILayout, pg: PropertyGroup, list_id) -> None:
    box: UILayout = layout.box()
    data: bpy_prop_collection = getattr(pg, list_id)

    draw_override_items(box, data, list_id, 'object.slicer_remove_item')

    from .operators import create_operator_row
    create_operator_row(box, "object.slicer_add_item", list_id)

def draw_overrides_list(layout: UILayout, pg: PropertyGroup, list_id: str, readonly_data: list[dict]) -> None:
    box: UILayout = layout.box()
    data: bpy_prop_collection = getattr(pg, list_id)

    draw_override_items(box, data, list_id, 'collection.slicer_remove_item')
    
    for item in readonly_data:
        row = box.row(align=True)
        row.label(icon='RNA')  # type: ignore
        row.label(text=f"{item.get('param_id', '')}")
        row.label(text=str(item.get('param_value', '')))

    from .operators import create_operator_row
    create_operator_row(box, "collection.slicer_add_item", list_id)