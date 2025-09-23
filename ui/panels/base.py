from bpy.types import Context, Panel

class BasePanel(Panel):
    bl_label = "Default Panel"
    bl_idname = "COLLECTION_PT_BasePanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context: Context):
        pass