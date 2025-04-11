## Overview
This Blender add-on integrates PrusaSlicer directly within Blender, allowing for seamless 3D model slicing and export to G-code without leaving the Blender environment.

![image](https://github.com/user-attachments/assets/8269545b-3449-4700-8057-9de52e4281b0)

## Features
Slice models and open them in PrusaSlicer directly from Blender.

- Import configurations from a folder containing PrusaSlicer .ini configuration files. You can export those from a PrusaSlicer project using File > Export > Export Config, or you can find them online.
- Collection-based slicing: the settings are stored at a collection level: when selecting different objects to slice, the active configuration will reflect the current selection. This is especially useful when creating files for different printers.
- Slicing to disk (the .gcode will be generated in the same folder as your .blend file) or directly to USB devices.

![image](https://github.com/user-attachments/assets/a70932a4-0df0-46ef-81aa-1e9a0b64b0ee)

- Customizing the slicing using overrides. The original configuration file itself will remain unchaged.

![image](https://github.com/user-attachments/assets/64d968d1-f4fa-4932-9027-eb2fb872ccac)

- Adding pauses, color changes, and custom gcodes at specific layers or heights

![image](https://github.com/user-attachments/assets/e5cbe15f-3257-46dc-b57b-3b269e8c08a4)

- Prusaslicer profiles for Prusa printers are bundled for convenience. You can find non-prusa profiles at https://github.com/prusa3d/PrusaSlicer-settings-non-prusa-fff .

## Installation
- Clone or download this repository.
- Open Blender and go to Edit > Preferences > Add-ons > arrow on the top-right corner > Install from Disk.

![image](https://github.com/user-attachments/assets/cc34cb88-59cb-40fb-91ea-fb14242db1f2)

- Click Install and select the .zip file of the add-on.
- Enable the add-on in the preferences.
- Install the psutil dependency using the "Install dependencies" button in the add-on preferences
- In the add-on preferences also specify the path to the PrusaSlicer executable. Commands (such as flatpak run) are also supported.

## Usage
- Load a custom configuration file (.ini) for slicing settings. 
- Select the objects to slice in Blender.
- Find the PrusaSlicer section in the Scene menu:

![image](https://github.com/user-attachments/assets/9b2c9180-a9db-4675-b65f-aed40a3c1958)
- Optional: use the additional panels below the slicing buttons to change settings on the fly.
- Click "Slice" to generate and preview the G-code (it will be saved in the same folder as the .blend file) or "Open with PrusaSlicer" to export and open the model in the regular PrusaSlicer UI.

## Requirements
- Blender 4.2.0 or higher.
- PrusaSlicer installed and accessible from the command line.

## Troubleshooting
- If after installing the dependencies the addon doesn't reload correctly, close and re-open blender, and re-activate the addon.
- If using a sandboxed PrusaSlicer such as the flatpak version, make sure PrusaSlicer can write temporary files (in Linux, this means being allowed to write to /tmp ). The AppImage version however is the only one i currently support.

## Coming Soon
- Multi-material slicing
- In-blender gcode preview

## License
This project is licensed under GPL-3.0.
Prusaslicer (Licensed under AGPL-3.0) profiles for Prusa printers are bundled together with the addon; a copy of the license is provided.
