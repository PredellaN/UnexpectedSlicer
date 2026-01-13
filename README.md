# UnexpectedSlicer

![release_gfx](https://github.com/user-attachments/assets/c007e2e3-9dcc-4331-bfc3-5b0887a55834)

## Overview
This Blender add-on integrates PrusaSlicer directly within Blender, allowing for seamless 3D model slicing and export to G-code without leaving the Blender environment.

<img width="480" alt="image" src="https://github.com/user-attachments/assets/2a125b07-2967-49cc-a4ae-4aabeb1a0bcf" />

## Features
Slice models and open them in PrusaSlicer directly from Blender.

- Import configurations from a folder containing PrusaSlicer .ini configuration files. You can export those from a PrusaSlicer project using File > Export > Export Config, or you can find them online.
- Collection-based slicing: the settings are stored at a collection level: when selecting different objects to slice, the active configuration will reflect the current selection. This is especially useful when creating files for different printers.
- Slicing to disk (the .gcode will be generated in the same folder as your .blend file) or directly to USB devices.

<img src="https://github.com/user-attachments/assets/22bf57ed-fedd-4bf5-827a-df8ac76a361c" width="480">

- Customizing the slicing using overrides. The original configuration file itself will remain unchaged.
<img width="480" alt="image" src="https://github.com/user-attachments/assets/e9d4687d-829f-4d9e-81fe-922465633f14" />

- Adding pauses, color changes, and custom gcodes at specific layers or heights.

<img width="480" alt="image" src="https://github.com/user-attachments/assets/09c8280e-e59f-410a-9e24-9f245ce99ef3" />

- Multi Material Slicing: individual objects can be assigned to specific extruders, which can be assigned specific colors:

<img width="480" alt="image" src="https://github.com/user-attachments/assets/54e6ab1f-32cc-44be-8459-a655573cf279" />

<img width="480" alt="image" src="https://github.com/user-attachments/assets/765715ca-ea48-4a02-850d-202b12ef01ab" />

- Objects can be used as parts, modifier objects, support blockers/enforcers, to position wipe towers, as negative volumes, or ignored. Modifier parameters can be also assigned.

<img width="480" alt="image" src="https://github.com/user-attachments/assets/c7049c5b-4e7b-44af-b21a-efe34c8aa339" />

<img width="480" alt="image" src="https://github.com/user-attachments/assets/270c25c4-0717-4803-b861-38bf7a78211f" />

- Creality, Prusalink and Moonraker printers can be controlled remotely:

<img width="480" height="646" alt="image" src="https://github.com/user-attachments/assets/5fc503d9-c6c0-49b2-bcc5-42951745a266" />

- Preview GCode (BGCode currently not supported) directly inside blender
<img width="1024" alt="image" src="https://github.com/user-attachments/assets/b47846b2-a69a-4ed5-b392-5aaba5f592b2" />

- Prusaslicer profiles for Prusa printers are bundled for convenience. You can find non-prusa profiles at https://github.com/prusa3d/PrusaSlicer-settings-non-prusa-fff .
- You can bundle your configuration with the addon to distribute it in your workplace or lab: simply export the configuration, and put it in the root folder with name bundled_conf.json.

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
- Click "Slice" to generate and preview the G-code (it will be saved in the same folder as the .blend file) or "Open with PrusaSlicer" to export and open the model in the regular PrusaSlicer UI.

## Requirements
- Blender 4.2.0 or higher.
- PrusaSlicer installed and accessible from the command line.

## Troubleshooting
- If using a sandboxed PrusaSlicer such as the flatpak version, it is required that you allow PrusaSlicer to write temporary files (in Linux, this means being allowed to write to /tmp ). When using flatpak, you can do this using Flatseal.

## License
This project is licensed under GPL-3.0.
Prusaslicer (Licensed under AGPL-3.0) profiles for Prusa printers are bundled together with the addon; a copy of the license is provided.
