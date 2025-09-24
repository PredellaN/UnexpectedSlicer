import os
import subprocess

def unmount_usb(mountpoint: str) -> bool:
    try:
        if os.name == 'nt':
            # On Windows we use mountvol /D to delete the drive letter
            result = os.system(f"mountvol {mountpoint} /D")
            # os.system returns the exit status; 0 means success
            return result == 0
        else:
            # On POSIX systems use the umount command
            result = subprocess.run(
                ["umount", mountpoint],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
    except Exception:
        return False