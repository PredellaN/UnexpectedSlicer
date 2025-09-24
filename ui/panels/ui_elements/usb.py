from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import UILayout

    from ....props.bpy_property_groups import SlicerPropertyGroup
    from ....operators import RunSlicerOperator, UnmountUsbOperator

def draw_usb_devices(layout: UILayout, pg: SlicerPropertyGroup, sliceable: bool) -> None:
    import psutil
    from ....infra.filesystem import is_usb_device
    from ....registry import get_icon

    partitions = psutil.disk_partitions()
    usb_partitions = [p for p in partitions if is_usb_device(p)]

    if usb_partitions:
        layout.row().label(text="Detected USB Devices:")

    for partition in usb_partitions:
        row = layout.row()
        mountpoint = partition.mountpoint
        row.enabled = not pg.running

        # Unmount USB operator
        op_unmount: UnmountUsbOperator = row.operator("collection.unmount_usb", text="", icon='UNLOCKED')
        op_unmount.mountpoint = mountpoint

        # Slice USB operator
        if sliceable:
            op_slice: RunSlicerOperator = row.operator("collection.slice", text="", icon_value=get_icon('slice.png'))
            op_slice.mountpoint = mountpoint
            op_slice.mode = "slice"

        row.label(text=f"{mountpoint.split('/')[-1]} mounted at {mountpoint} ({partition.device})")