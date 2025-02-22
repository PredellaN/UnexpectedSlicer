import os
import re
from configparser import ConfigParser, MissingSectionHeaderError
from .. import ADDON_FOLDER

class LocalCache:
    def __init__(self):
        self.directory: str | None = None
        self.local_files: dict = {}
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
        """Processes updated or new files and updates self.config_headers."""
        for file_path, file_info in self.local_files.items():
            if file_info['updated']:
                # Remove existing entries associated with this file
                keys_to_remove = [key for key, val in self.config_headers.items() if val['path'] == file_path]
                for key in keys_to_remove:
                    del self.config_headers[key]
                self._process_ini_to_cache_dict(file_path)
                # Mark the file as processed
                self.local_files[file_path]['updated'] = False

    def load_ini_files(self):
        # Sanitize and normalize the path
        if not self.directory:
            self.local_files = {}
            self.config_headers = {}
            return

        sanitized_path = os.path.abspath(os.path.expanduser(self.directory))

        if sanitized_path.startswith("//"):
            sanitized_path = os.path.normpath(
                os.path.join(ADDON_FOLDER, sanitized_path.lstrip("/"))
            )

        # Verify if the path exists and is a directory
        if not os.path.isdir(sanitized_path):
            print(f"Error: {sanitized_path} is not a valid directory.")
            return

        # List all .ini files in the directory and subdirectories
        current_files = {}
        for root, _, files in os.walk(sanitized_path, followlinks=True):
            for file in files:
                if file.endswith('.ini'):
                    file_path = os.path.join(root, file)
                    last_modified = os.path.getmtime(file_path)
                    current_files[file_path] = last_modified

        # Determine files that are new or updated
        updated_local_files = {}
        self._has_changes = False  # Reset the change flag

        for file_path, last_modified in current_files.items():
            if file_path in self.local_files:
                prev_last_modified = self.local_files[file_path]['last_updated']
                is_updated = last_modified > prev_last_modified
                if is_updated:
                    self._has_changes = True
                updated_local_files[file_path] = {
                    'last_updated': last_modified,
                    'updated': is_updated
                }
            else:
                # New file detected
                updated_local_files[file_path] = {
                    'last_updated': last_modified,
                    'updated': True
                }
                self._has_changes = True

        # Detect deleted files
        deleted_files = set(self.local_files.keys()) - set(current_files.keys())
        if deleted_files:
            self._has_changes = True
            # Remove entries associated with deleted files
            for deleted_file in deleted_files:
                keys_to_remove = [key for key, val in self.config_headers.items() if val['path'] == deleted_file]
                for key in keys_to_remove:
                    del self.config_headers[key]

        # Update local_files with the current state
        self.local_files = updated_local_files

    def has_changes(self):
        """Checks if any local_files have changed since the last update."""
        return self._has_changes
