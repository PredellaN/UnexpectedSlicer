import bpy
from .. import TYPES_NAME

class BasePanel(bpy.types.Panel):
    bl_label = "Default Panel"
    bl_idname = "COLLECTION_PT_BasePanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"
    def populate_ui(self, layout, property_group, item_rows):
            for item_row in item_rows:
                row = layout.row()
                if type(item_row) == list:
                    for item in item_row:
                        row.prop(property_group, item)
                elif type(item_row) == str:
                    if ';' in item_row:
                        text, icon = item_row.split(';')
                    else:
                        text, icon = item_row, '',
                    row.label(text=text, icon=icon)

    def draw(self, context):
        pass

class ParamAddOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_add_operator"
    bl_label = "Add Parameter"
    list_id: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        prop_group = self.get_pg()

        list = getattr(prop_group, f'{self.list_id}')
        list.add()
        return {'FINISHED'}
    
    def get_pg(self):
        pass

    def trigger(self):
        pass

class ParamRemoveOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_remove_operator"
    bl_label = "Generic Remove Operator"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        prop_group = self.get_pg()

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        return {'FINISHED'}

    def get_pg(self):
        pass

    def trigger(self):
        pass

class ParamTransferOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_transfer_operator"
    bl_label = "Transfer Parameter"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()
    target_list: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        prop_group = self.get_pg()

        source_list = getattr(prop_group, f'{self.list_id}')
        source_item = source_list[self.item_idx]

        target_list = getattr(prop_group, f'{self.target_list}')
        item = target_list.add()
        item.param_id = source_item.param_id
        self.trigger()
        return {'FINISHED'}
    
    def get_pg(self):
        pass

    def trigger(self):
        pass