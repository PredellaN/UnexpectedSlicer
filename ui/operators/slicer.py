import bpy
from bpy_extras.io_utils import ExportHelper

from ...infra.prusaslicer_bridge import SlicerService
from ...preferences.preferences import SlicerPreferences
from ... import PACKAGE

from ...registry import register_class

@register_class
class RunSlicerOperator(bpy.types.Operator, ExportHelper):  # type: ignore
    bl_idname = "collection.slice"
    bl_label = "Run PrusaSlicer"

    mode: bpy.props.StringProperty(name="", default="slice")
    mountpoint: bpy.props.StringProperty(name="", default="")
    target_key: bpy.props.StringProperty(name="", default="")
    filename_ext = ''

    @classmethod
    def description(cls, context, properties: "RunSlicerOperator") -> str:
        if properties.mode == 'slice_and_preview':
            return "Slice and show the generated GCode in the PrusaSlicer GCode viewer"
        elif properties.mode == 'slice_and_preview_internal':
            return "Slice and show the generated GCode within blender"
        elif properties.mode == 'slice' and properties.mountpoint:
            return "Slice to the blendfile folder"
        elif properties.mode == 'slice' and not properties.mountpoint:
            return "Slice to a target folder"
        elif properties.mode == 'open':
            return "Open the selection in PrusaSlicer"
        else:
            return ""

    def invoke(self, context, event) -> set['OperatorReturnItems']: #type: ignore
        if not self.mountpoint:
            return super().invoke(context, event)
        else:
            return self.execute(context)

    def execute(self, context) -> set['OperatorReturnItems']: #type: ignore
        assert bpy.context.preferences

        prefs: SlicerPreferences
        if not (prefs := bpy.context.preferences.addons[PACKAGE].preferences): return {'CANCELLED'}
            
        service = SlicerService(prefs.prusaslicer_path, prefs.profile_cache)
        service.execute(
            context=context,
            operator_props=self.properties,
            mode=self.mode,
            mountpoint=self.mountpoint,
            target_key=self.target_key,
        )
        return {'FINISHED'}