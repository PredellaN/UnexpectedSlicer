import os
from pathlib import Path

def ftp_upload(
    host: str,
    filepath: Path,
    storage_path: str,
    filename: str,
    overwrite: bool = False,
    timeout: float = 30,
    user: str = "",
    passwd: str = "",
):
    from ftplib import FTP, error_perm

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Local file not found: {filepath}")

    remote_name = filename or os.path.basename(filepath)

    ftp = FTP(host, timeout=timeout)
    ftp.login(user=user, passwd=passwd)

    try:
        # Change to target directory
        ftp.cwd(storage_path)

        # Check if file exists remotely
        existing = ftp.nlst()
        if remote_name in existing:
            if not overwrite:
                raise FileExistsError(f"Remote file already exists: {remote_name}")
            # delete existing file
            try:
                ftp.delete(str(remote_name))
            except error_perm as e:
                raise RuntimeError(f"Failed to delete remote file: {e}")

        # Upload new file
        with open(filepath, 'rb') as f:
            ftp.storbinary(f'STOR {remote_name}', f)

    finally:
        ftp.quit()

def ftp_wipe(
    host: str,
    storage_path: str,
    timeout: int = 30,
    user: str = "",
    passwd: str = "",
):
    from ftplib import FTP, error_perm

    ftp = FTP(host, timeout=timeout)
    ftp.login(user=user, passwd=passwd)

    try:
        ftp.cwd(storage_path)
        existing = ftp.nlst()
        for f in existing:
            try:
                ftp.delete(filename=f)
            except error_perm as e:
                raise RuntimeError(f"Failed to delete remote file: {f}")
    except error_perm as e:
        raise RuntimeError("e")
    finally:
        ftp.quit()

def ftp_get_filesize(
    host: str,
    storage_path: str,
    filename: str,
    timeout: float = 30,
    user: str = "",
    passwd: str = "",
) -> int:
    from ftplib import FTP, error_perm
    
    ftp = FTP(host, timeout=timeout)
    ftp.login(user=user, passwd=passwd)

    try:
        ftp.cwd(storage_path)
        try:
            size = ftp.size(filename)
        except error_perm as e:
            raise FileNotFoundError(f"Remote file not found or SIZE not supported: {filename}") from e

        if size is None:
            raise RuntimeError("FTP server returned no size information")

        return size

    finally:
        ftp.quit()