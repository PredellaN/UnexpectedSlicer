from bpy.types import Context, bpy_struct, Collection

from ..infra.blender_bridge import coll_from_selection
from .. import TYPES_NAME, PACKAGE

class FromPreferences():
    def get_pg(self, context: Context) -> bpy_struct | None:
        if not context.preferences: return None
        return context.preferences.addons[PACKAGE].preferences

class FromObject():
    def get_pg(self, context: Context) -> bpy_struct | None:
        return getattr(context.object, TYPES_NAME)

class FromCollection():
    def get_pg(self, context: Context) -> bpy_struct | None:
        collection: Collection | None= coll_from_selection()
        return getattr(collection, TYPES_NAME)