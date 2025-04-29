from bpy.types import UILayout

from ...property_groups import SlicerPropertyGroup
from ...operators import RunSlicerOperator, UnmountUsbOperator

def draw_usb_devices(layout: UILayout, pg: SlicerPropertyGroup, sliceable: bool) -> None:
    import psutil  # type: ignore
    from ...functions.basic_functions import is_usb_device

    partitions = psutil.disk_partitions()
    usb_partitions = [p for p in partitions if is_usb_device(p)]

    if usb_partitions:
        layout.row().label(text="Detected USB Devices:")

    for partition in usb_partitions:
        row = layout.row()
        mountpoint = partition.mountpoint
        row.enabled = not pg.running

        # Unmount USB operator
        op_unmount: UnmountUsbOperator = row.operator("collection.unmount_usb", text="", icon='UNLOCKED')  # type: ignore
        op_unmount.mountpoint = mountpoint

        # Slice USB operator
        if sliceable:
            op_slice: RunSlicerOperator = row.operator("collection.slice", text="", icon='DISK_DRIVE')  # type: ignore
            op_slice.mountpoint = mountpoint
            op_slice.mode = "slice"

        row.label(text=f"{mountpoint.split('/')[-1]} mounted at {mountpoint} ({partition.device})")