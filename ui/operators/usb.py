from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.stub_internal.rna_enums import OperatorReturnItems

import bpy

from ...registry import register_class
from ...infra.usb import unmount_usb

@register_class
class UnmountUsbOperator(bpy.types.Operator):
    bl_idname = "collection.unmount_usb"
    bl_label = "Unmount USB"

    mountpoint: bpy.props.StringProperty()

    def execute(self, context) -> set['OperatorReturnItems']:
        if unmount_usb(self.mountpoint):
            self.report({"INFO"}, f"Unmounted {self.mountpoint}")
            return {"FINISHED"}
        else:
            self.report(
                {"ERROR"},
                f"Failed to unmount {self.mountpoint}",
            )
            return {"CANCELLED"}