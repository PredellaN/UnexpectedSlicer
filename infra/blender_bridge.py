import bpy
from bpy.types import Collection, LayerCollection

def coll_from_selection() -> Collection | None:
    for obj in bpy.context.selected_objects:
        return obj.users_collection[0]

    if not bpy.context.view_layer: return None

    active_layer_collection: LayerCollection | None = bpy.context.view_layer.active_layer_collection

    cx: Collection | None = active_layer_collection.collection if active_layer_collection else None
    
    return cx