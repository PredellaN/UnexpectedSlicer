import bpy
from .. import TYPES_NAME

class BasePanel(bpy.types.Panel):
    bl_label = "Default Panel"
    bl_idname = "COLLECTION_PT_BasePanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        pass

class BaseOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_operator"
    bl_label = "Add Parameter"

    def execute(self, context):
        return {'FINISHED'}

    def get_pg(self, context):
        pass

    def trigger(self, context):
        pass

class ParamAddOperator(BaseOperator):
    bl_idname = f"{TYPES_NAME}.generic_add_operator"
    bl_label = "Add Parameter"

    list_id: bpy.props.StringProperty()

    def execute(self, context):
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.add()
        self.trigger(context)
        return {'FINISHED'}

class ParamRemoveOperator(BaseOperator):
    bl_idname = f"{TYPES_NAME}.generic_remove_operator"
    bl_label = "Remove Parameter"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()

    def execute(self, context): 
        prop_group = self.get_pg(context)

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        self.trigger(context)
        return {'FINISHED'}

class ParamTransferOperator(BaseOperator):
    bl_idname = f"{TYPES_NAME}.generic_transfer_operator"
    bl_label = "Transfer Parameter"

    target_key: bpy.props.StringProperty()
    target_list: bpy.props.StringProperty()

    def execute(self, context):
        prop_group = self.get_pg(context)

        target_list = getattr(prop_group, f'{self.target_list}')
        item = target_list.add()
        item.param_id = self.target_key
        self.trigger(context)
        return {'FINISHED'}