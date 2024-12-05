# Anycubic PW0 Converter
Converts Gerber + Excellon, SVG and PNG files to Anycubic Mono 3D printer files with PW0 image encoding.

## Requirements (for Windows):
tkinter, pillow, cairosvg, python-magic-bin

Alternatively, you can just download the .exe file in [Releases](https://github.com/BleakyTex/Anycubic-PW0-Converter/releases/). Cairosvg isn't working very well on Windows anyway.

# Usage
To work with Gerber and Excellon files, this converter requires [gerbv](https://github.com/gerbv/gerbv/releases/). Download it, extract the archive contents and specify the path to gerbv.exe in the converter. Without gerbv only .svg and .png can be converted.

Also this converter needs a printer file that it will patch. Create a one-layer thin figure in a 3D editor (I've included some stl files in the repo) and create a file with only one layer **(important!)** in your favorite slicer.
Specify the path to the printer file in the converter. Now you can open your PCB files and convert them. Gerber files are scaled automatically, just make sure that the size of your board doesn't exceed the size of the printer's LCD. If multiple Gerber files are selected, they will be combined.

Tested on Anycubic Photon Mono 4 and Mono M3 Plus but should work for all Anycubic MSLA printers.

![scrn](https://github.com/user-attachments/assets/b3df7b47-1929-47d0-8fdb-c4dd6d859f7e)
