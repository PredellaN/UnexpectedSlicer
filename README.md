## Overview
This Blender add-on integrates PrusaSlicer directly within Blender, allowing for seamless 3D model slicing and export to G-code without leaving the Blender environment.

![image](https://github.com/user-attachments/assets/d9cf0ecd-5c34-4dbc-a598-b7e6dd149df1)

## Features
Slice models and open them in PrusaSlicer directly from Blender.

- Import configurations from a folder containing PrusaSlicer .ini configuration files. You can export those from a PrusaSlicer project using File > Export > Export Config, or you can find them online.
- Collection-based slicing: the settings are stored at a collection level: when selecting different objects to slice, the active configuration will reflect the current selection. This is especially useful when creating files for different printers.
- Slicing to disk (the .gcode will be generated in the same folder as your .blend file) or directly to USB devices.

![image](https://github.com/user-attachments/assets/22bf57ed-fedd-4bf5-827a-df8ac76a361c)

- Customizing the slicing using overrides. The original configuration file itself will remain unchaged.

![image](https://github.com/user-attachments/assets/d9023516-aef8-4ed2-bebe-a22564971c56)

- Adding pauses, color changes, and custom gcodes at specific layers or heights.

![image](https://github.com/user-attachments/assets/4b1b31f3-ed62-41c7-85fa-62c659e0f168)

- Multi Material Slicing: individual objects can be assigned to specific extruders:

![image](https://github.com/user-attachments/assets/295dfd90-df8b-4aad-831e-602dd85cb3c0)

- Objects can be used as modifiers, support blockers/enforcers, and as negative volumes.

![image](https://github.com/user-attachments/assets/27304598-a8a1-4bd3-8a7b-4a5b4f8185bb)

- Prusaslicer profiles for Prusa printers are bundled for convenience. You can find non-prusa profiles at https://github.com/prusa3d/PrusaSlicer-settings-non-prusa-fff .

## Installation
- Clone or download this repository.
- Open Blender and go to Edit > Preferences > Add-ons > arrow on the top-right corner > Install from Disk.
- Click Install and select the .zip file of the add-on.
- Enable the add-on in the preferences.
- In the add-on preferences also specify the path to the PrusaSlicer executable. Commands (such as flatpak run) are also supported.

## Usage
- Select the objects to slice in Blender.
- Find the slicing section in the Collection menu
- Select the configurations, and add any overrides or pause/color changes. 
![image](https://github.com/user-attachments/assets/9b2c9180-a9db-4675-b65f-aed40a3c1958)
- Click "Slice" to generate and preview the G-code (it will be saved in the same folder as the .blend file) or "Open with PrusaSlicer" to export and open the model in the regular PrusaSlicer UI.

## Requirements
- Blender 4.2.0 or higher.
- PrusaSlicer installed and accessible from the command line.

## Troubleshooting
- If after installing the dependencies the addon doesn't reload correctly, close and re-open blender, and re-activate the addon.
- If using a sandboxed PrusaSlicer such as the flatpak version, make sure PrusaSlicer can write temporary files (in Linux, this means being allowed to write to /tmp ). The AppImage version however is the only one i currently support.

## Coming Soon
- In-blender gcode preview

## License
This project is licensed under GPL-3.0.
Prusaslicer (Licensed under AGPL-3.0) profiles for Prusa printers are bundled together with the addon; a copy of the license is provided.
