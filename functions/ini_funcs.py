import re
import os
from configparser import ConfigParser, MissingSectionHeaderError

def ini_to_dict(path: str) -> tuple[bool, dict[str, dict[str, str]]]:
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
    return has_header, {
        section: dict(sorted(config.items(section)))
        for section in sorted(config.sections())
    }

def ini_content_to_dict(path: str) -> dict[str, str]:
    # Read the file content from the path
    with open(path, 'r') as file:
        content = file.read()

    config = ConfigParser(interpolation=None)

    default_section = f"[default:default]\n" + content
    config.read_string(default_section)

    return dict(sorted(config.items(config.sections()[0])))