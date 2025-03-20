
from bpy.types import Collection
from .blender_funcs import coll_from_selection
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