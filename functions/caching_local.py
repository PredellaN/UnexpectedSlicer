from pathlib import Path
import os
import re
from configparser import ConfigParser, MissingSectionHeaderError
from .. import ADDON_FOLDER

class LocalCache:
    def __init__(self):
        self.local_files: dict[str, dict] = {}
        self.config_headers: dict = {}
        self._has_changes: bool = False  # Flag to indicate changes in files

    def _process_ini_to_cache_dict(self, path):
        # Read the file content from the path
        with open(path, 'r') as file:
            content = file.read()

        config = ConfigParser(interpolation=None)
        try:
            # Attempt to parse the content
            config.read_string(content)
            has_header = True
        except MissingSectionHeaderError:
            # Determine category based on specific IDs in the content
            if re.search(r'^filament_settings_id', content, re.MULTILINE):
                cat = 'filament'
            elif re.search(r'^print_settings_id', content, re.MULTILINE):
                cat = 'print'
            elif re.search(r'^printer_settings_id', content, re.MULTILINE):
                cat = 'printer'
            else:
                raise ValueError(f"Unable to determine category for the INI file: {path}")

            # Extract the filename without extension
            name = os.path.splitext(os.path.basename(path))[0]
            # Create a default section with the determined category and name
            default_section = f"[{cat}:{name}]\n" + content
            config.read_string(default_section)
            has_header = False

        # Convert ConfigParser content into a dictionary
        ini_dict = {
            section: dict(sorted(config.items(section)))
            for section in sorted(config.sections())
        }

        # Flatten the dictionary for profiles and add to self.config_headers
        for key, val in ini_dict.items():
            if ":" in key:
                self.config_headers[key] = {
                    'id': key.split(':')[1] if len(key.split(':')) > 1 else key,
                    'category': key.split(':')[0] if len(key.split(':')) > 1 else None,
                    'path': path,
                    'has_header': has_header,
                    'conf_dict': val,
                }

    def process_all_files(self):
        for file_path, file_info in self.local_files.items():
            if file_info['updated']:
                # Remove existing entries associated with this file
                keys_to_remove = [key for key, val in self.config_headers.items() if val['path'] == file_path]
                for key in keys_to_remove:
                    del self.config_headers[key]
                self._process_ini_to_cache_dict(file_path)
                # Mark the file as processed
                self.local_files[file_path]['updated'] = False

    def load_ini_files(self, dirs: list[str]) -> None:

        current_files: dict[str, float] = {}
        updated_local_files: dict[str, dict] = {}
        self._has_changes = False  # Reset the change flag

        # Iterate over all provided directories
        for directory in dirs:
            sanitized_path = self._sanitize_directory(directory)
            if not sanitized_path:
                continue

            # Use os.walk with followlinks=True to ensure linked folders are processed
            for root, _, files in os.walk(sanitized_path, followlinks=True):
                for file in files:
                    if file.endswith('.ini'):
                        file_path = Path(root) / file
                        try:
                            last_modified = file_path.stat().st_mtime
                            current_files[str(file_path)] = last_modified
                        except OSError as e:
                            print(f"Error reading file {file_path}: {e}")
                            continue

        # Check for new or updated files
        for file_path, last_modified in current_files.items():
            previous_info = self.local_files.get(file_path)
            # File is new or updated if not present or its modification time is more recent
            is_updated = previous_info is None or last_modified > previous_info['last_updated']
            updated_local_files[file_path] = {
                'last_updated': last_modified,
                'updated': is_updated
            }
            if is_updated:
                self._has_changes = True

        # Detect deleted files (present in previous state but missing now)
        deleted_files = set(self.local_files.keys()) - set(current_files.keys())
        if deleted_files:
            self._has_changes = True
            for deleted_file in deleted_files:
                # Remove config header entries associated with the deleted file
                keys_to_remove = [key for key, val in self.config_headers.items() if val.get('path') == deleted_file]
                for key in keys_to_remove:
                    self.config_headers.pop(key, None)

        # Update the local_files state with the current scan
        self.local_files = updated_local_files

    def _sanitize_directory(self, dir_str: str) -> Path | None:
        if not dir_str:
            return None

        if dir_str.startswith("//"):
            sanitized = Path(ADDON_FOLDER) / Path(dir_str[2:])
        else:
            sanitized = Path(os.path.expanduser(dir_str)).resolve()

        if not sanitized.is_dir():
            print(f"Path is not a valid directory: {dir_str}")
            return None

        return sanitized

    def has_changes(self):
        """Checks if any local_files have changed since the last update."""
        return self._has_changes
