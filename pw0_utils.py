import re
import os
import subprocess
import struct
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps
from cairosvg import svg2png


def is_gbr(filename):
    patterns = [
        r'FSLAX',
        r'%MOMM.*%' + '|' + r'%MOIN.*%',
        r'M02.*'
    ]

    with open(filename, 'r') as file:
        content = file.read()

    return all(re.search(pattern, content) for pattern in patterns)



def gerber_to_png(filenames, output_svg, output_png, gerbv, disp_res, dpi):
    color_bg = "#000000"
    color_fg = "#FFFFFF"
    h_inch = disp_res[0] / dpi
    w_inch = disp_res[1] / dpi
    print('\n---VECTORIZING GERBER/EXCELLON---')
    
    args = []
    filenames = sorted(filenames, key=is_gbr) # put excellon files before gerbers for proper rendering
    for filename in filenames:
        flip_colors = is_gbr(filename)
        args += ['--background=' + (color_bg, color_fg)[flip_colors],
                 '--foreground=' + (color_fg, color_bg)[flip_colors], filename]
    args += ["--border=0", f"--window_inch={h_inch:.6f}x{w_inch:.6f}", "--export=svg", "--output=" + output_svg]
    print(args)
    subprocess.run([gerbv, *args])
    
    print('\n---RASTERIZING VECTOR---')
    svg_disable_antialiasing(output_svg, output_svg)
    
    svg2png(url = output_svg, write_to = output_png,
                     output_width = disp_res[0], output_height = disp_res[1])


    print('\n---BINARIZING IMAGE---')
    Image.MAX_IMAGE_PIXELS = None   # disable image size limit

    image = Image.open(output_png)

    white_background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_background, image)
    grayscale = combined.convert('L')
    binary_image = grayscale.point(lambda p: 255 if p > 1 else 0)

    print('\n---CENTERING IMAGE---')
    inverted_image = ImageOps.invert(binary_image)
    bbox = inverted_image.getbbox()
    #print(bbox)
    if bbox:
        cropped_image = binary_image.crop(bbox)
        new_image = Image.new("L", binary_image.size, (255))
        paste_position = ((binary_image.size[0] - cropped_image.size[0]) // 2,
                          (binary_image.size[1] - cropped_image.size[1]) // 2)
        
        new_image.paste(cropped_image, paste_position)
    else:
        new_image = inverted_image
    print('\n---SAVING TO PNG---')

    new_image.save(output_png, format='PNG')
    print(f"Processed image saved to {output_png}")
        
    w_mm = cropped_image.size[0] * 25.4 / dpi
    h_mm = cropped_image.size[1] * 25.4 / dpi
    #print(f"\nBoard dimensions: {w_mm:.4f}x{h_mm:.4f} mm")
    return [w_mm, h_mm]



def svg_disable_antialiasing(input_svg, output_svg):
    # Add the CSS property shape-rendering:crispEdges to an SVG file
    print('\n---PATCHING VECTOR---')  
    
    tree = ET.parse(input_svg)
    root = tree.getroot()
    
    namespaces = {'svg': 'http://www.w3.org/2000/svg'}
    ET.register_namespace('', namespaces['svg'])
    
    if root.get('shape-rendering') != 'crispEdges':
        root.set('shape-rendering', 'crispEdges')
        
    tree.write(output_svg)


def svg_to_png(size_mm, printer_resolution, printer_dpi, input_svg, output_png):
    print('\n---RASTERIZING VECTOR---')
    h_res = round(printer_dpi * size_mm[0] / 25.4)
    v_res = round(printer_dpi * size_mm[1] / 25.4)
    output_img_width = printer_resolution[0]
    output_img_height = printer_resolution[1]
    print(f"SVG TO PNG: {size_mm[0]}x{size_mm[1]}mm at {printer_dpi:.2f} DPI - {h_res}x{v_res} px") 
    svg2png(url = input_svg, write_to = output_png,
                     output_width = h_res, output_height = v_res)
    
    print('\n---BINARIZING IMAGE---')
    Image.MAX_IMAGE_PIXELS = None   # disable image size limit
    image = Image.open(output_png)

    white_background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_background, image)
    grayscale = combined.convert('L')
    binary_image = grayscale.point(lambda p: 255 if p > 1 else 0)

    print('\n---PADDING---')
    orig_width, orig_height = binary_image.size
    # Check if padding is needed
    if orig_width >= output_img_width or orig_height >= output_img_height:
        print(f"Target size ({output_img_width}, {output_img_height}) is smaller than or equal to the current image size ({orig_width}, {orig_height}). No padding needed.")
        padded_image = binary_image
    else:
        padded_image = Image.new(
                'L', (output_img_width, output_img_height), "white") 

        # Paste original image in the center of a new image
        pad_width = (output_img_width - orig_width) // 2
        pad_height = (output_img_height - orig_height) // 2
        paste_position = (pad_width, pad_height)
        padded_image.paste(binary_image, paste_position)
    
    print('\n---SAVING TO PNG---')
    padded_image.save(output_png, format='PNG')
    print(f"Processed image saved to {output_png}")

    return padded_image   



def process_png(size_mm, printer_resolution, printer_dpi, source_dpi, input_png, output_png):
    Image.MAX_IMAGE_PIXELS = None   # disable image size limit
    output_img_width = printer_resolution[0]
    output_img_height = printer_resolution[1]

    image = Image.open(input_png)

    print('\n---BINARIZING IMAGE---')
    image = image.convert("RGBA")
    white_background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_background, image)
    grayscale = combined.convert('L')
    binary_image = grayscale.point(lambda p: 255 if p > 1 else 0)

    print('\n---SCALING---')
    scale_factor = printer_dpi / source_dpi
    new_width = round(binary_image.width * scale_factor)
    new_height = round(binary_image.height * scale_factor)
    scaled_image = binary_image.resize((new_width, new_height), Image.NEAREST)
    
    print('\n---PADDING---')
    orig_width, orig_height = scaled_image.size
    # Check if padding is needed
    if orig_width >= output_img_width or orig_height >= output_img_height:
        print(f"Target size ({output_img_width}, {output_img_height}) is smaller than or equal to the current image size ({orig_width}, {orig_height}). No padding needed.")
        padded_image = scaled_image
    else:
        padded_image = Image.new(
                'L', (output_img_width, output_img_height), "white") 

        # Paste original image in the center of a new image
        pad_width = (output_img_width - orig_width) // 2
        pad_height = (output_img_height - orig_height) // 2
        paste_position = (pad_width, pad_height)
        padded_image.paste(scaled_image, paste_position)
    
    print('\n---SAVING TO PNG---')
    padded_image.save(output_png, format='PNG')
    print(f"Processed image saved to {output_png}")

    return padded_image



def read_pw0_file(file_path):
    print('\n--- LOADING PW0 FILE ---')
    with open(file_path, 'rb') as file:
        data = file.read()
        check_word = 'pw0Img'
        check_bytes = check_word.encode('utf-8')
        check_addr = data.find(check_bytes) 
        if check_addr != -1:
            print("PW0 data found")
        else:
            raise ValueError("PW0 data not found")
            return

        return(data)



def parse_header(data):
    print('\n--- PARSING HEADER ---')
    pix_size_offset = 16
    exp_time_offset = 32
    disp_width_offset = 60
    disp_height_offset = 64

    header_word = 'HEADER'
    word_bytes = header_word.encode('utf-8')
    header_addr = data.find(word_bytes)
    if header_addr != -1:
        print(f"'{header_word}' found at offset: 0x{header_addr:08X}")
    else:
        raise ValueError("File header not found")
        return

    if (header_addr + disp_height_offset) >= len(data):
        raise ValueError("Header data out of bounds")
        return

    # Parse LCD pixel size
    pix_size_addr = header_addr + pix_size_offset
    pixel_size = data[pix_size_addr:pix_size_addr + 4]
    pixel_size = struct.unpack('<f', pixel_size)[0]  # Unpack the bytes as a little-endian fp32
    print(f"Pixel size: {pixel_size:.1f} um")

    # Parse exposure time
    exp_time_addr = header_addr + exp_time_offset
    exp_time = data[exp_time_addr:exp_time_addr + 4]
    exp_time = struct.unpack('<f', exp_time)[0]
    print(f"Exposure time: {exp_time:.1f} sec")

    # Parse display horizontal resolution
    disp_width_addr = header_addr + disp_width_offset
    disp_width = data[disp_width_addr:disp_width_addr + 4]
    disp_width = struct.unpack('<I', disp_width)[0]  # Unpack the bytes as a little-endian uint32
    print(f"Horizontal resolution: {disp_width} px")

    disp_height_addr = header_addr + disp_height_offset
    disp_height = data[disp_height_addr:disp_height_addr + 4]
    disp_height = struct.unpack('<I', disp_height)[0]
    print(f"Vertical resolution: {disp_height} px")

    return [pixel_size, disp_width, disp_height, exp_time_addr]



# Returns a string with printer name
def parse_model(data):
    print('\n--- PARSING MODEL ---')
    model_offset = 16
    model_word = 'MACHINE'

    word_bytes = model_word.encode('utf-8')
    machine_addr = data.find(word_bytes)
    if machine_addr != -1:
        print(f"'{model_word}' found at offset: 0x{machine_addr:08X}")
    else:
        raise ValueError("Printer model not found")
        return

    model_addr = machine_addr + model_offset
    if model_addr >= len(data): # Ensure offset is within bounds
        raise ValueError("Model address out of bounds")
        return

    string_bytes = []
    # Get printer name
    for i in range(model_addr, len(data)):
        if data[i] == 0:  
            break
        string_bytes.append(data[i])

    # Convert the collected bytes to a string
    result_string = bytes(string_bytes).decode('utf-8')
    print(f"Printer model: {result_string}")

    return result_string



def parse_layer(data):
    print('\n--- PARSING LAYERS ---')
    layer_num_offset = 16
    img_data_addr_offset = 20
    img_size_offset = 24
    exposure_time_offset = 36
    white_pix_num_offset = 44
    layer_word = 'LAYERDEF'

    word_bytes = layer_word.encode('utf-8')
    layer_addr = data.find(word_bytes)  # Search for the word 'LAYERDEF'
    if layer_addr != -1:
        print(f"'{layer_word}' found at offset: 0x{layer_addr:08X}")
    else:
        raise ValueError("Layer information not found")
        return

    if (layer_addr + white_pix_num_offset) >= len(data): # Ensure largest offset is within bounds
        raise ValueError("Layer data out of bounds")
        return

    # Read amount of layers
    layer_num_addr = layer_addr + layer_num_offset
    layer_num = data[layer_num_addr:layer_num_addr + 4]
    value = struct.unpack('<I', layer_num)[0]  # Unpack the bytes as a little-endian uint32
    print(f"Layer amount: {value}")
    if value > 1:
        print("WARNING: FOUND MORE THAN ONE LAYER IN THE FILE, PATCHING MAY NOT WORK!")

    # Read exposure time    
    exposure_time_addr = layer_addr + exposure_time_offset
    exposure_time = data[exposure_time_addr:exposure_time_addr + 4]
    exposure_time = struct.unpack('<f', exposure_time)[0]  # Unpack the bytes as a little-endian fp32
    print(f"Exposure time: {exposure_time:.1f} sec at 0x{exposure_time_addr:08X}")

    # Read the amount of white pixels in layer image
    white_pix_num_addr = layer_addr + white_pix_num_offset
    white_pix_num = data[white_pix_num_addr:white_pix_num_addr + 4]
    value = struct.unpack('<I', white_pix_num)[0]
    print(f"Number of white pixels in layer image: {value} at 0x{white_pix_num_addr:08X}")

    # Read the image data address
    img_data_loc_addr = layer_addr + img_data_addr_offset
    img_data_addr = data[img_data_loc_addr:img_data_loc_addr + 4]
    img_data_addr = struct.unpack('<I', img_data_addr)[0]
    print(f"Layer image data address: 0x{img_data_addr:08X}")

    # Read the image data size
    img_size_addr = layer_addr + img_size_offset
    int32_bytes = data[img_size_addr:img_size_addr + 4]
    value = struct.unpack('<I', int32_bytes)[0]
    print(f"Compressed image data size: {value} bytes at 0x{white_pix_num_addr:08X}")

    if (img_data_addr) > len(data): # Ensure image data is within bounds
        raise ValueError("Image data out of bounds")
        return

    return [exposure_time, exposure_time_addr, white_pix_num_addr, img_data_addr, img_size_addr]



def rll_encode_image(image):

    '''
            Layer image data is encoded in 2-byte chunks:

               ⌐ ¬ Number of pixels to fill
            0x0FFF
              ↑
              Pixel color: 0 -- black, F -- white
    '''

    print('\n---ENCODING TO RLL---')
    color = 0
    length = 1 # how many pixels of the same color in a row
    pixel_prev = 4 # anything but 0x0 or 0xF
    white_pixel_count = 0
    rll_data = bytearray()

    pixels = image.getdata() # get all pixels as a sequence
    for pixel in pixels:  # either 0x0 of 0xFF
        if pixel == 0xFF:
            white_pixel_count += 1

        if (pixel != pixel_prev) or (length>=0xFFF):
            encoded_word = ((color << 12) | length) & 0xFFFF
            encoded_word = encoded_word.to_bytes(2, byteorder='big')
            rll_data.extend(encoded_word)

            color = pixel
            length = 1

        else:
            length += 1

        pixel_prev = pixel   

    rll_size = len(rll_data)

    #output_file = 'lib_copper_bottom.bin'
    #with open(output_file, "wb") as file:  # Open in binary write mode
    #    file.write(rll_data)    

    #print(f'Image contains {white_pixel_count} white pixels')
    #print(f'Wrote {rll_size} bytes to {output_file}')

    return [rll_data, rll_size, white_pixel_count]



def patch_pw0(file_path, layer_data, rll_result, exp_time_addr2, exposure_time):
    print('\n---PATCHING---')
    print(f"Exposure time: {exposure_time} sec")
    #print(layer_data)
    exposure_time_addr = layer_data[1]
    white_pix_num_addr = layer_data[2]
    img_data_addr = layer_data[3]
    img_size_addr = layer_data[4]

    rll_data = rll_result[0]
    rll_size = rll_result[1]
    white_pixel_count = rll_result[2]

    with open(file_path, "rb") as f:
        original_data = bytearray(f.read())

    # Remove old layer image data
    #print(f'Layer image data address: 0x{img_data_addr:08X}')
    new_data = original_data[:img_data_addr]

    # Add new layer image data
    new_data.extend(rll_data)

    # Patch layer image size
    new_data[img_size_addr:img_size_addr + 4] = struct.pack('<I', rll_size)
    # Patch white pixel count
    new_data[white_pix_num_addr:white_pix_num_addr + 4] = struct.pack('<I', white_pixel_count)
    # Patch exposure time in the layer description
    new_data[exposure_time_addr:exposure_time_addr + 4] = struct.pack('<f', exposure_time)
    # Patch exposure time in the header
    new_data[exp_time_addr2:exp_time_addr2 + 4] = struct.pack('<f', exposure_time)
    
    file_name = os.path.basename(file_path)
    name, ext = os.path.splitext(file_name)
    file_out = f"{name}_patched{ext}"
    with open(file_out, "wb") as f:
        f.write(new_data)
    print(f'{file_out} written to the script directory.')
