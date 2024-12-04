import configparser
import os
import sys
import re
import shutil
import subprocess

import magic
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageOps

import pw0_utils

all_good = False    

output_svg = "output.svg"
output_png = "padded.png"

gerbv_loaded = False

display_img = None 
rendered_img = None 

lcd_h_res = None
lcd_v_res = None
lcd_px_size = None
printer_dpi = None
disp_width = None
disp_height = None

display_properties = None
layer_data = None
last_printer_file = None

exposure_time = None
board_width = None
board_height = None

config = configparser.ConfigParser()
config_ini_file = 'config.ini'
config_files_section = 'files'
config_gerbv_file = 'last_gerbv_file'
config_printer_file = 'last_prn_file'
config_settings_section = 'settings'
config_img_invert = 'invert_image'
config_img_mirror = 'mirror_image'

last_gerbv_file = ''
last_printer_file = ''

def empty_if_none(config, section, option):
    try:
        return config.get(section, option)
    except:
        return ''

def save_config():
    global config_ini_file
    global config

    with open(config_ini_file, 'w') as file:
        config.write(file)

def save_settings():
    global config_ini_file
    global config
    global checkbutton_invert 
    global checkbutton_mirror
    
    try:
        if not config.has_section(config_settings_section):
            config.add_section(config_settings_section)
        
        config.set(config_settings_section, config_img_invert, str(checkbutton_invert.get()))
        config.set(config_settings_section, config_img_mirror, str(checkbutton_mirror.get()))    
        save_config()
        
        root.destroy()
        sys.exit()  
    except:
        sys.exit() 
    
def load_config():
    global last_gerbv_file
    global last_printer_file
    global config_gerbv_file
    global config_printer_file
    global config_files_section
    global config_settings_section
    global config_ini_file
    global config
    global checkbutton_invert 
    global checkbutton_mirror
    
    config.read(config_ini_file)
    last_printer_file = empty_if_none(config, config_files_section, config_printer_file)
    if not config.has_section(config_files_section):
        config.add_section(config_files_section)
    config.set(config_files_section, config_printer_file, last_printer_file)
    last_gerbv_file = empty_if_none(config, config_files_section, config_gerbv_file)
    if last_gerbv_file == '':
        last_gerbv_file = shutil.which('gerbv')
        config.set(config_files_section, config_gerbv_file,
                   last_gerbv_file if last_gerbv_file is not None else '')
    
    
    invert = config.getboolean(config_settings_section, config_img_invert, fallback=True)
    mirror = config.getboolean(config_settings_section, config_img_mirror, fallback=True)
    checkbutton_invert.set(invert)
    checkbutton_mirror.set(mirror)
    
def draw_image():
    global display_img
    
    img = display_img.copy()
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()
    img.thumbnail((canvas_width, canvas_height))

    tk_img = ImageTk.PhotoImage(img)

    canvas.image = tk_img  # Keep a reference to avoid garbage collection
    canvas.create_image(canvas_width // 2, canvas_height // 2, image=tk_img, anchor="center")

def on_resize(event):
    if display_img:
        draw_image()

def apply_transform():
    global checkbutton_invert
    global checkbutton_mirror 
    global display_img
    global rendered_img
    
    if rendered_img is not None:
        display_img = rendered_img.copy()
        if checkbutton_invert.get():
            display_img = ImageOps.invert(display_img)
        if checkbutton_mirror.get():
            display_img = display_img.transpose(Image.FLIP_LEFT_RIGHT)
        draw_image()

def load_gerbv(dialog = True):
    global gerbv_file_label
    global last_gerbv_file
    global config_gerbv_file
    global config_files_section
    global config
    global gerbv_loaded
    
    last_gerbv_file = config.get(config_files_section, config_gerbv_file)
    if dialog:
        file = filedialog.askopenfilename(initialfile = last_gerbv_file, title="Select gerbv executable")
        if file:
            last_gerbv_file = file
        else: return
    
    if not last_gerbv_file:
        return
    
    try:
        retn = subprocess.run([last_gerbv_file, '--version'], capture_output = True)
        if retn.stdout.decode()[:6] == 'gerbv ':
            gerbv_file_label.configure(text=f"gerbv loaded successfully")
            config.set(config_files_section, config_gerbv_file, last_gerbv_file)
            save_config()
            gerbv_loaded = True
    except:
        gerbv_file_label.configure(text=f"gerbv not loaded, gerber files won't be processed")
        gerbv_loaded = False
        
def set_entry(entry, value):
    entry.delete(0, tk.END)
    if value is not None:
        entry.insert(0, str(value))

def load_pw0(dialog = True):
    global exp_time_entry
    global dpi_entry
    global w_entry
    global h_entry
    global printer_file_label
    global lcd_h_res
    global lcd_v_res
    global lcd_px_size
    global printer_dpi
    global disp_width
    global disp_height
    global exposure_time
    global last_printer_file
    global config_printer_file
    global config_files_section
    global config
    
    global layer_data
    global display_properties

    
    last_printer_file = config.get(config_files_section, config_printer_file)
    if dialog:
        file = filedialog.askopenfilename(initialfile = last_printer_file, title="Select printer file")
        if file:
            last_printer_file = file
        else: return

    if not last_printer_file:
        return

    error_message = ""

    try:
        printer_file_label.configure(text=os.path.basename(last_printer_file))

        data = pw0_utils.read_pw0_file(last_printer_file)
        printer_name = pw0_utils.parse_model(data)
        display_properties = pw0_utils.parse_header(data)
        layer_data = pw0_utils.parse_layer(data)

        lcd_h_res = display_properties[1]
        lcd_v_res = display_properties[2]
        lcd_px_size = display_properties[0]
        disp_width = lcd_h_res * lcd_px_size / 1000
        disp_height = lcd_v_res * lcd_px_size / 1000

        exposure_time = layer_data[0]
        printer_dpi = 25400.0 / lcd_px_size
        set_entry(exp_time_entry, exposure_time)
        set_entry(dpi_entry, printer_dpi)
        set_entry(w_entry, disp_width)
        set_entry(h_entry, disp_height)

        printer_name_label.configure(text=printer_name)

        lcd_label_text = f"{lcd_h_res}x{lcd_v_res}px, {lcd_px_size:.1f} μm - {disp_width:.1f}x{disp_height:.1f}mm"
        printer_lcd_label.configure(text=lcd_label_text)

        config.set(config_files_section, config_printer_file, last_printer_file)
        save_config()
    except Exception as e:
        error_message = str(e)   
        printer_name_label.configure(text=error_message) 
        printer_lcd_label.configure(text="")

def load_pcb():
    global dpi_entry
    global w_entry
    global h_entry
    global rendered_img
    global board_width
    global board_height
    global output_svg
    global vector_png
    global output_png
    global lcd_h_res
    global lcd_v_res
    global disp_width
    global disp_height
    
    file_paths = list(filedialog.askopenfilenames(title="Select PCB file"))
    
    if not file_paths:
        return
        
    gerber_file_label.configure(text="Working...")
    gerber_file_label.update_idletasks() # Force the label to update without waiting for main update loop

    mime = magic.from_file(file_paths[0], mime = True) \
            if len(file_paths) == 1 else ''
    #print(mime)
            
    if (mime == 'image/svg+xml' or mime == 'image/svg'):
        try:
            pcb_size = [float(w_entry.get()), float(h_entry.get())]
        except:
            gerber_file_label.configure(text="Error: PCB size not specified")
            return
        if pcb_size[0] <= 0 or pcb_size[1] <= 0:
            gerber_file_label.configure(text="Error: PCB size too small")
            return
        if pcb_size[0] > disp_width or pcb_size[1] > disp_height:
            gerber_file_label.configure(text="Error: PCB size is larger than printer's display")
            return
            
        pw0_utils.svg_disable_antialiasing(file_paths[0], output_svg)
        pw0_utils.svg_to_png(pcb_size, [lcd_h_res, lcd_v_res], printer_dpi, output_svg, output_png)
        
    elif (mime == 'image/png'):
        source_dpi = float(dpi_entry.get())
        pcb_size = [float(w_entry.get()), float(h_entry.get())]
        if pcb_size[0] <= 0 or pcb_size[1] <= 0:
            gerber_file_label.configure(text="Error: PCB size too small")
            return
        if pcb_size[0] > disp_width or pcb_size[1] > disp_height:
            gerber_file_label.configure(text="Error: PCB size is larger than printer's display")
            return
               
        pw0_utils.process_png(pcb_size, [lcd_h_res, lcd_v_res], printer_dpi, source_dpi, file_paths[0], output_png)
        
    else:  # if gerber/drl
        if not (gerbv_loaded):
            gerber_file_label.configure(text="Error: gerbv executable not loaded")
            return
        else:
            pcb_size = pw0_utils.gerber_to_png(file_paths, output_svg, output_png, last_gerbv_file, [lcd_h_res, lcd_v_res], printer_dpi)
    
    rendered_img = Image.open(output_png)
    apply_transform()
    draw_image()
    
    gerber_file_label.configure(
            text = ', '.join([os.path.basename(path) for path in file_paths]))
            
def filter_float(value):
    return re.fullmatch('([0-9]*[.])?[0-9]*', value) is not None

def patch_printer_file():
    global patch_label
    global display_properties
    global layer_data
    global last_printer_file
    global exposure_time
    global display_img
    global lcd_h_res
    global lcd_v_res
    
    patch_label.configure(text="Working...")
    patch_label.update_idletasks() # Force the label to update without waiting for main update loop
    
    if any(var is None for var in (display_properties, layer_data, last_printer_file, exposure_time, display_img, lcd_h_res, lcd_v_res)):
        patch_label.configure(text="Error: Patch data not ready")
        return

    exposure_time = float(exp_time_entry.get())
    if exposure_time < 0.1:
        patch_label.configure(text="Exposure time is too short!")
        return

    source_img_size = display_img.size
    if source_img_size[0] != lcd_h_res or source_img_size[1] != lcd_v_res:
        patch_label.configure(text="Error: Source and target resolution mismatch")
        return
    
    
    rll_result = pw0_utils.rll_encode_image(display_img)
    pw0_utils.patch_pw0(last_printer_file, layer_data, rll_result, display_properties[3], exposure_time)
    patch_label.configure(text="Success")
    
root = tk.Tk()
root.title("ANYCUBIC CONVERTER")
root.geometry("1000x550")
root.wm_minsize(600, 550)
root.protocol("WM_DELETE_WINDOW", save_settings)

checkbutton_invert = tk.BooleanVar() 
checkbutton_mirror = tk.BooleanVar()

control_frame = ttk.Frame(borderwidth=1, relief=tk.SOLID, width = 300, padding=[8, 10])  

btn = tk.Button(control_frame, text = 'Choose gerbv executable', command = load_gerbv)
btn.pack(anchor=tk.NW, fill=tk.X)

gerbv_file_label = ttk.Label(control_frame, text="")
gerbv_file_label.pack(anchor=tk.NW, fill=tk.X)

btn = tk.Button(control_frame, text = 'Choose printer file', command = load_pw0)
btn.pack(anchor=tk.NW, fill=tk.X)

printer_file_label = ttk.Label(control_frame, text="")
printer_file_label.pack(anchor=tk.NW, fill=tk.X)

printer_name_label = ttk.Label(control_frame, text="")
printer_name_label.pack(anchor=tk.NW, fill=tk.X)

printer_lcd_label = ttk.Label(control_frame, text="")
printer_lcd_label.pack(anchor=tk.NW, fill=tk.X)

btn = tk.Button(control_frame, text = 'Choose PCB (GBR[+Excellon] / SVG / PNG)', command = load_pcb)
btn.pack(anchor=tk.NW, fill=tk.X)

gerber_file_label = ttk.Label(control_frame, text="Multiple gerber files can be selected")
gerber_file_label.pack(anchor=tk.NW, fill=tk.X)

label = ttk.Label(control_frame, text="\nPROCESSING OPTIONS")
label.pack(anchor=tk.NW, fill=tk.X)


Button1 = tk.Checkbutton(control_frame, text = "Invert image", 
                variable = checkbutton_invert,
                command = apply_transform, 
                height = 1, 
                width = 10,
                anchor='w')
Button1.pack(anchor=tk.NW, fill=tk.X)


Button2 = tk.Checkbutton(control_frame, text = "Mirror image horizontally", 
                variable = checkbutton_mirror, 
                command = apply_transform,
                height = 1, 
                width = 10,
                anchor='w')
Button2.pack(anchor=tk.NW, fill=tk.X)

label = ttk.Label(control_frame, text="Adjust exposure time (sec)")
label.pack(anchor=tk.NW, fill=tk.X)
exp_time_entry = ttk.Entry(control_frame, validate = "key")
exp_time_entry.configure(validate = 'all',
        validatecommand = (exp_time_entry.register(filter_float), '%P'))
exp_time_entry.pack(anchor=tk.NW, fill=tk.X, pady=3)

label = ttk.Label(control_frame, text="Source image DPI (for PNGs)")
label.pack(anchor=tk.NW, fill=tk.X)
dpi_entry = ttk.Entry(control_frame, validate = "key")
dpi_entry.configure(validate = 'all',
        validatecommand = (dpi_entry.register(filter_float), '%P'))
dpi_entry.pack(anchor=tk.NW, fill=tk.X, pady=3)

label = ttk.Label(control_frame, text="PCB width, mm (for SVGs and PNGs)")
label.pack(anchor=tk.NW, fill=tk.X)
w_entry = ttk.Entry(control_frame, validate = "key")
w_entry.configure(validate = 'all',
        validatecommand = (w_entry.register(filter_float), '%P'))
w_entry.pack(anchor=tk.NW, fill=tk.X, pady=3)

label = ttk.Label(control_frame, text="PCB height, mm (for SVGs and PNGs)")
label.pack(anchor=tk.NW, fill=tk.X)
h_entry = ttk.Entry(control_frame, validate = "key")
h_entry.configure(validate = 'all',
        validatecommand = (h_entry.register(filter_float), '%P'))
h_entry.pack(anchor=tk.NW, fill=tk.X, pady=3)

btn = tk.Button(control_frame, text = 'PATCH', command = patch_printer_file)
btn.pack(anchor=tk.NW, fill=tk.X, pady=7)

patch_label = ttk.Label(control_frame, text="")
patch_label.pack(anchor=tk.NW, fill=tk.X, pady=7)

control_frame.pack(anchor=tk.NW, side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
control_frame.pack_propagate(0) # tell frame not to let its children control its size

canvas = tk.Canvas(root, bg = "gray", width = 250, height = 250)
canvas.pack(anchor=tk.NW, expand=True, fill=tk.BOTH)
canvas.bind("<Configure>", on_resize)

load_config()
load_gerbv(False)
load_pw0(False)

root.mainloop()
