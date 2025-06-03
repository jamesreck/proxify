import os
from PIL import Image, ImageDraw, ImageEnhance
import math # For math.ceil or math.round
import re # For sanitizing filenames

# --- Configuration ---
CARD_WIDTH_MM = 63.5
CARD_HEIGHT_MM = 88.9
PAPER_WIDTH_IN = 8.5
PAPER_HEIGHT_IN = 11
DPI = 1200
MM_TO_IN = 1 / 25.4

# Desired final black border thickness in mm for each side
DESIRED_BORDER_TOP_MM = 3
DESIRED_BORDER_LEFT_MM = 3
DESIRED_BORDER_RIGHT_MM = 3
DESIRED_BORDER_BOTTOM_MM = 4.1

# For Extended Art: vertical offset from top of content to scan for side borders
EXTENDED_ART_SCAN_OFFSET_Y_MM = 3

# Pixels to trim from original bottom of full art cards. Set to 0 for no crop.
FULL_ART_BOTTOM_CROP_PX = 80

LINE_COLOR = (255, 51, 153) # Pink for high visibility
LINE_WIDTH = 4 # Pixels
BLACK_BORDER_THRESHOLD = 50 # RGB values must all be <= this to be considered 'black'
EDGE_ZONE_CHECK_WIDTH_PX = 10  # Pixel width of edge zones to check for solid black

SATURATION_FACTOR = 1.0  # e.g., 1.2 for a 20% increase
BRIGHTNESS_FACTOR = 1.0 # e.g., 1.15 for a 15% increase (1.0 is no change)

# --- NEW CONFIGURATION OPTION ---
# Set to True to force all cards to be processed as "standard" frame type,
# skipping automatic detection.
FORCE_STANDARD_FRAME_TYPE = False # Default is False (use automatic detection)


# --- Calculations ---
CARD_WIDTH_PX = round((CARD_WIDTH_MM * MM_TO_IN) * DPI)
CARD_HEIGHT_PX = round((CARD_HEIGHT_MM * MM_TO_IN) * DPI)

BORDER_TOP_PX = round((DESIRED_BORDER_TOP_MM * MM_TO_IN) * DPI)
BORDER_LEFT_PX = round((DESIRED_BORDER_LEFT_MM * MM_TO_IN) * DPI)
BORDER_RIGHT_PX = round((DESIRED_BORDER_RIGHT_MM * MM_TO_IN) * DPI)
BORDER_BOTTOM_PX = round((DESIRED_BORDER_BOTTOM_MM * MM_TO_IN) * DPI)

EXTENDED_ART_SCAN_OFFSET_Y_PX = round(EXTENDED_ART_SCAN_OFFSET_Y_MM * MM_TO_IN * DPI)

PAPER_WIDTH_PX = round(PAPER_WIDTH_IN * DPI)
PAPER_HEIGHT_PX = round(PAPER_HEIGHT_IN * DPI)

GRID_WIDTH_PX = 3 * CARD_WIDTH_PX
GRID_HEIGHT_PX = 3 * CARD_HEIGHT_PX
MARGIN_X = (PAPER_WIDTH_PX - GRID_WIDTH_PX) // 2
MARGIN_Y = (PAPER_HEIGHT_PX - GRID_HEIGHT_PX) // 2

if MARGIN_X < 0 or MARGIN_Y < 0:
  print("Warning: Calculated grid size exceeds paper dimensions at 1200 DPI.")
  MARGIN_X = max(0, MARGIN_X)
  MARGIN_Y = max(0, MARGIN_Y)

def get_content_bounding_box(image, threshold):
  """
  Calculates the bounding box of the content area by identifying pixels
  brighter than the threshold.
  Returns a tuple (x0, y0, x1, y1) for the bounding box of content,
  or None if no content found (e.g., image is all border color or empty).
  """
  original_size = image.size
  image_width = image.width
  image_height = image.height

  if image_width == 0 or image_height == 0:
    return None

  temp_l_image_full = Image.new("L", original_size, 0) # All black
  try:
    # Ensure image is RGB for consistent pixel reading
    source_img_rgb = image
    if image.mode != 'RGB':
        source_img_rgb = image.convert("RGB")
    source_pixels_full_rgb = source_img_rgb.load()
  except Exception as e:
    print(f"    Error in get_content_bounding_box pixel conversion: {e}")
    return None
    
  dest_pixels_full_l = temp_l_image_full.load()
  has_any_content_pixel = False
  for y_f in range(image_height):
    for x_f in range(image_width):
      r, g, b = source_pixels_full_rgb[x_f, y_f] # Will be 3-tuple
      if r > threshold or g > threshold or b > threshold: # If content
        dest_pixels_full_l[x_f, y_f] = 255 # Mark as white
        has_any_content_pixel = True
            
  if not has_any_content_pixel:
    return None # Entire image is "border" color or darker

  return temp_l_image_full.getbbox() # Bbox of white pixels

def get_content_extents_at_row(image, y_row, threshold):
  """
  Finds the start and end x-coordinates of content on a specific row.
  Content is defined by pixels brighter than the threshold.
  Assumes image is already in a mode like RGBA or RGB for pixel access.
  Returns (content_start_x, content_end_x) or (None, None) if no content found.
  """
  try:
    pixels = image.load() # pixels[x,y]
    width = image.width
  except Exception as e:
    print(f"    Error loading image pixels in get_content_extents_at_row: {e}")
    return None, None

  content_start_x = -1
  # Scan from left for content_start_x
  for x in range(width):
    pixel_tuple = pixels[x, y_row]
    r, g, b = pixel_tuple[:3] # Access first 3 for RGB, handles RGB and RGBA
    if r > threshold or g > threshold or b > threshold:
      content_start_x = x
      break
  
  if content_start_x == -1:
    # No content found on this row
    return None, None

  content_end_x = content_start_x # Initialize with start_x, in case only one content pixel found
  # Scan from right for content_end_x (no need to scan more left than content_start_x)
  for x in range(width - 1, content_start_x - 1, -1):
    pixel_tuple = pixels[x, y_row]
    r, g, b = pixel_tuple[:3]
    if r > threshold or g > threshold or b > threshold:
      content_end_x = x
      break
  
  return content_start_x, content_end_x

def check_strip_for_solid_lr_border(strip_image, check_width_px, threshold):
  """
  Checks if a horizontal image strip has solid black borders on its left and right sides.
  """
  if not strip_image or strip_image.height == 0 or strip_image.width < 2 * check_width_px:
    return False

  try:
    # Ensure strip_image is in a suitable mode (e.g. RGBA or RGB) before loading pixels
    if strip_image.mode not in ['RGB', 'RGBA']:
        strip_image_conv = strip_image.convert('RGBA') # Convert to RGBA for consistent pixel access
    else:
        strip_image_conv = strip_image
    strip_pixels = strip_image_conv.load()
  except Exception as e:
    # print(f"    Debug: Error converting strip or loading pixels: {e}")
    return False 
    
  strip_h = strip_image_conv.height
  strip_w = strip_image_conv.width

  left_border_is_solid = True
  if check_width_px > 0:
    for x_coord in range(check_width_px):
      for y_coord in range(strip_h):
        pixel_tuple = strip_pixels[x_coord, y_coord]
        r, g, b = pixel_tuple[:3]
        if r > threshold or g > threshold or b > threshold:
          left_border_is_solid = False
          break
      if not left_border_is_solid:
        break
  else: # No width to check, so technically no border defined by this check
    left_border_is_solid = False
  
  if not left_border_is_solid:
    return False # No need to check right if left failed

  right_border_is_solid = True
  if check_width_px > 0: # Only check if check_width_px is positive
    for x_coord in range(strip_w - check_width_px, strip_w):
      for y_coord in range(strip_h):
        pixel_tuple = strip_pixels[x_coord, y_coord]
        r, g, b = pixel_tuple[:3]
        if r > threshold or g > threshold or b > threshold:
          right_border_is_solid = False
          break
      if not right_border_is_solid:
        break
  else: # No width to check
    right_border_is_solid = False
            
  return left_border_is_solid and right_border_is_solid

def determine_card_type(image, threshold, edge_check_pixel_width):
  """
  Determines card type based on analyzing borders in top and middle zones.
  Assumes image is already RGBA or RGB.
  """
  width, height = image.size
  if height < 20: # Arbitrary minimum height to define zones meaningfully
    return "borderless"

  min_zone_height = max(1, edge_check_pixel_width // 2 if edge_check_pixel_width > 0 else 1)

  top_zone_actual_height = max(min_zone_height, int(height * 0.05))
  top_zone_img = image.crop((0, 0, width, top_zone_actual_height))

  middle_zone_top_y = int(height * 0.50)
  middle_zone_bottom_y = int(height * 0.60)
  middle_zone_calculated_height = middle_zone_bottom_y - middle_zone_top_y
  middle_zone_actual_height = max(min_zone_height, middle_zone_calculated_height)
  
  if middle_zone_actual_height == min_zone_height and middle_zone_calculated_height < min_zone_height:
    if middle_zone_top_y + middle_zone_actual_height > height: # Avoid cropping beyond image
      middle_zone_top_y = max(0, height - middle_zone_actual_height)

  middle_zone_img = image.crop((0, middle_zone_top_y, width, middle_zone_top_y + middle_zone_actual_height))
  
  top_has_lr_border = check_strip_for_solid_lr_border(top_zone_img, edge_check_pixel_width, threshold)
  middle_has_lr_border = check_strip_for_solid_lr_border(middle_zone_img, edge_check_pixel_width, threshold)
  
  if top_has_lr_border and middle_has_lr_border:
    return "standard"
  elif top_has_lr_border and not middle_has_lr_border:
    return "extended_art"
  else: # Neither, or only middle (which defaults to borderless as per rule "If neither...")
    return "borderless"

def resize_card(image_path, target_final_card_width_px, target_final_card_height_px):
  try:
    original_img = Image.open(image_path)
    original_img = original_img.convert("RGBA") # Ensure consistent RGBA mode for all operations
    original_w, original_h = original_img.size
    print(f"Processing {os.path.basename(image_path)} (Original size: {original_w}x{original_h})...")

    # --- MODIFIED SECTION: Card Type Determination ---
    if FORCE_STANDARD_FRAME_TYPE:
      card_type = "standard"
      print(f"  Config override: Treating card as '{card_type}' type.")
    else:
      card_type = determine_card_type(original_img, BLACK_BORDER_THRESHOLD, EDGE_ZONE_CHECK_WIDTH_PX)
      print(f"  Detected card type: {card_type}")
    # --- END OF MODIFIED SECTION ---

    img_to_final_resize = None # This will hold the image after initial cropping, before final resize
    image_ready_for_enhancement = None # This will hold the image at final dimensions, before enhancement

    # Get overall content box first; used for cy0, cy1 and as fallback for cx0, cx1 for Standard/Extended.
    overall_content_bbox = get_content_bounding_box(original_img, BLACK_BORDER_THRESHOLD)

    # Initialize effective content coordinates
    # These will be used for Standard/Extended art border processing
    effective_cx0, effective_cy0, effective_cx1, effective_cy1 = -1, -1, -1, -1 
    
    if overall_content_bbox:
      effective_cx0, effective_cy0, effective_cx1, effective_cy1 = overall_content_bbox
    else:
      # No content box found by global check (e.g. image is all border color)
      print(f"    Warning: No overall content found by get_content_bounding_box. Effective content for Stnd/Ext will be full image.")
      effective_cx0, effective_cy0 = 0, 0 # Default to full image if no bbox
      effective_cx1, effective_cy1 = original_w, original_h

    # --- Special handling for Extended Art side content detection ---
    if card_type == "extended_art": # This block will be skipped if FORCE_STANDARD_FRAME_TYPE is True
      if overall_content_bbox: 
        content_top_y_for_scan = effective_cy0 
        vertical_sample_y = content_top_y_for_scan + EXTENDED_ART_SCAN_OFFSET_Y_PX

        if 0 <= vertical_sample_y < original_h:
          print(f"    Extended Art: Scanning for side content at y={vertical_sample_y} (content_top_y={content_top_y_for_scan} + {EXTENDED_ART_SCAN_OFFSET_Y_PX}px offset)")
          cx_at_row_start, cx_at_row_end = get_content_extents_at_row(original_img, vertical_sample_y, BLACK_BORDER_THRESHOLD)

          if cx_at_row_start is not None and cx_at_row_end is not None and cx_at_row_start <= cx_at_row_end:
            print(f"      Found side content at y={vertical_sample_y} from x={cx_at_row_start} to x={cx_at_row_end}")
            effective_cx0 = cx_at_row_start 
            effective_cx1 = cx_at_row_end   
          else:
            print(f"      Warning: Could not determine specific side content for Extended Art at y={vertical_sample_y}. Using overall content box for sides.")
        else:
          print(f"      Warning: Calculated vertical_sample_y ({vertical_sample_y}) for Extended Art scan is out of image bounds ({original_h}). Using overall content box for sides.")
      else: 
          print(f"    Extended Art: Skipping special side scan as no overall content box was found. Using full image as effective content.")
    
    # --- Process Standard and Extended Art Cards ---
    # If FORCE_STANDARD_FRAME_TYPE is True, card_type will be "standard", so this block will execute.
    if card_type == "standard" or card_type == "extended_art":
      if card_type == "standard":
        print(f"  Action: '{card_type}' - Applying proportional border adjustment using overall content box.")
      # For extended art (if not forced to standard), messages were printed above.
      
      current_content_width_orig = effective_cx1 - effective_cx0
      current_content_height_orig = effective_cy1 - effective_cy0

      if current_content_width_orig > 0 and current_content_height_orig > 0:
        final_artwork_width = max(1, target_final_card_width_px - BORDER_LEFT_PX - BORDER_RIGHT_PX)
        final_artwork_height = max(1, target_final_card_height_px - BORDER_TOP_PX - BORDER_BOTTOM_PX)

        scale_w = final_artwork_width / current_content_width_orig if current_content_width_orig != 0 else 0
        scale_h = final_artwork_height / current_content_height_orig if current_content_height_orig != 0 else 0
        
        keep_orig_border_left_px = round(BORDER_LEFT_PX / scale_w) if abs(scale_w) > 1e-6 else 0
        keep_orig_border_top_px = round(BORDER_TOP_PX / scale_h) if abs(scale_h) > 1e-6 else 0
        keep_orig_border_right_px = round(BORDER_RIGHT_PX / scale_w) if abs(scale_w) > 1e-6 else 0
        keep_orig_border_bottom_px = round(BORDER_BOTTOM_PX / scale_h) if abs(scale_h) > 1e-6 else 0
        
        crop_x0 = max(0, effective_cx0 - keep_orig_border_left_px)
        crop_y0 = max(0, effective_cy0 - keep_orig_border_top_px)
        crop_x1 = min(original_w, effective_cx1 + keep_orig_border_right_px)
        crop_y1 = min(original_h, effective_cy1 + keep_orig_border_bottom_px)

        if crop_x1 > crop_x0 and crop_y1 > crop_y0:
          img_to_final_resize = original_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
        else: 
          print(f"    Warning: Calculated proportional crop for '{card_type}' is invalid.")
          if effective_cx0 >= 0 and effective_cy0 >=0 and effective_cx1 > effective_cx0 and effective_cy1 > effective_cy0:
            print(f"      Falling back to cropping to effective content box: ({effective_cx0},{effective_cy0},{effective_cx1},{effective_cy1})")
            img_to_final_resize = original_img.crop((effective_cx0, effective_cy0, effective_cx1, effective_cy1))
          else: 
            print(f"      Falling back to using full original image (copy).")
            img_to_final_resize = original_img.copy() 
      else: 
        print(f"    Warning: Effective content box for '{card_type}' has zero/negative dimension. Using full original image (copy).")
        img_to_final_resize = original_img.copy()
      
      if img_to_final_resize:
        if img_to_final_resize.size != (target_final_card_width_px, target_final_card_height_px):
          image_ready_for_enhancement = img_to_final_resize.resize(
              (target_final_card_width_px, target_final_card_height_px), 
              Image.Resampling.LANCZOS
          )
        else:
          image_ready_for_enhancement = img_to_final_resize.copy()

    # --- Process Full Art (Borderless) Cards ---
    # This block will be skipped if FORCE_STANDARD_FRAME_TYPE is True.
    elif card_type == "borderless":
      img_for_full_art_processing = original_img.copy() 
      if FULL_ART_BOTTOM_CROP_PX > 0:
        print(f"  Action: Full Art - cropping {FULL_ART_BOTTOM_CROP_PX}px from original bottom, then resizing.")
        if FULL_ART_BOTTOM_CROP_PX >= original_h :
          print(f"    Warning: Full art bottom trim amount ({FULL_ART_BOTTOM_CROP_PX}px) meets or exceeds image height ({original_h}px). Cropping to 1px height.")
          img_for_full_art_processing = original_img.crop((0, 0, original_w, 1)) if original_h > 0 else Image.new("RGBA", (max(1, original_w), 1), (0,0,0,0))
        elif original_w > 0 :
          crop_bottom_y = max(1, original_h - FULL_ART_BOTTOM_CROP_PX)
          img_for_full_art_processing = original_img.crop((0, 0, original_w, crop_bottom_y))
        elif original_w == 0:
            print(f"    Warning: Original image width is 0 for Full Art. Creating 1x1 transparent pixel.")
            img_for_full_art_processing = Image.new("RGBA",(1,1),(0,0,0,0))
      else: 
        print(f"  Action: Full Art - resizing as-is (FULL_ART_BOTTOM_CROP_PX is 0).")

      if img_for_full_art_processing.size != (target_final_card_width_px, target_final_card_height_px):
        image_ready_for_enhancement = img_for_full_art_processing.resize(
            (target_final_card_width_px, target_final_card_height_px), 
            Image.Resampling.LANCZOS
        )
      else:
        image_ready_for_enhancement = img_for_full_art_processing.copy()
            
    if not image_ready_for_enhancement: 
      print(f"  Fallback Error: Image for enhancement not set for {os.path.basename(image_path)}. Resizing original (copy).")
      image_ready_for_enhancement = original_img.copy().resize(
          (target_final_card_width_px, target_final_card_height_px), 
          Image.Resampling.LANCZOS
      )

    image_after_enhancements = image_ready_for_enhancement
    if BRIGHTNESS_FACTOR != 1.0:
      enhancer_brightness = ImageEnhance.Brightness(image_after_enhancements)
      image_after_enhancements = enhancer_brightness.enhance(BRIGHTNESS_FACTOR)
    if SATURATION_FACTOR != 1.0:
      enhancer_color = ImageEnhance.Color(image_after_enhancements)
      image_after_enhancements = enhancer_color.enhance(SATURATION_FACTOR)
    
    print(f"  Finished processing {os.path.basename(image_path)} -> Final card size {image_after_enhancements.size}")
    return image_after_enhancements

  except FileNotFoundError:
    print(f"Error: Image file not found at {image_path}")
    return None
  except Exception as e:
    print(f"Error processing image {image_path}: {e}")
    import traceback 
    traceback.print_exc() 
    return None

def create_printable_sheet(image_file_paths_chunk, output_path_for_sheet):
  print(f"Creating sheet: {os.path.basename(output_path_for_sheet)}")
  sheet = Image.new('RGBA', (PAPER_WIDTH_PX, PAPER_HEIGHT_PX), (255, 255, 255, 255))
  draw = ImageDraw.Draw(sheet)
  current_image_index = 0
  for row in range(3):
    for col in range(3):
      if current_image_index < len(image_file_paths_chunk):
        image_path = image_file_paths_chunk[current_image_index]
        card_img = resize_card(image_path, CARD_WIDTH_PX, CARD_HEIGHT_PX) 
        if card_img:
          paste_x_sheet = MARGIN_X + col * CARD_WIDTH_PX
          paste_y_sheet = MARGIN_Y + row * CARD_HEIGHT_PX
          sheet.paste(card_img, (paste_x_sheet, paste_y_sheet), card_img if card_img.mode == 'RGBA' else None)
        current_image_index += 1
      else: 
        break
    if current_image_index >= len(image_file_paths_chunk): 
      break

  for col_idx in range(1, 3): 
    line_x = MARGIN_X + col_idx * CARD_WIDTH_PX
    draw.line([(line_x - LINE_WIDTH // 2, 0), 
               (line_x - LINE_WIDTH // 2, PAPER_HEIGHT_PX)], 
              fill=LINE_COLOR, width=LINE_WIDTH)
  for row_idx in range(1, 3): 
    line_y = MARGIN_Y + row_idx * CARD_HEIGHT_PX
    draw.line([(0, line_y - LINE_WIDTH // 2), 
               (PAPER_WIDTH_PX, line_y - LINE_WIDTH // 2)], 
              fill=LINE_COLOR, width=LINE_WIDTH)
  try:
    sheet.save(output_path_for_sheet, dpi=(DPI, DPI))
    print(f"  Successfully saved sheet: {output_path_for_sheet}")
  except Exception as e:
    print(f"  Error saving sheet {output_path_for_sheet}: {e}")

def sanitize_filename_component(name_component):
  name_component = os.path.basename(name_component) 
  name_component = os.path.splitext(name_component)[0] 
  invalid_chars = r'[<>:"/\\|?*\s\.]+' 
  sanitized = re.sub(invalid_chars, '_', name_component)
  sanitized = re.sub(r'_+', '_', sanitized) 
  sanitized = sanitized.strip('_') 
  return sanitized if sanitized else "file"

if __name__ == "__main__":
  input_folder = input("Enter the path to the folder containing card images: ")
  output_dir_path = input("Enter the path to the output directory for the print sheets: ")

  if not os.path.isdir(input_folder):
    print(f"Error: Input folder '{input_folder}' not found or is not a directory. Exiting.")
    exit()
  
  if not os.path.exists(output_dir_path):
    try:
      os.makedirs(output_dir_path)
      print(f"Created output directory: '{output_dir_path}'")
    except OSError as e:
      print(f"Error creating output directory '{output_dir_path}': {e}. Exiting.")
      exit()
  elif not os.path.isdir(output_dir_path):
    print(f"Error: Output path '{output_dir_path}' exists but is not a directory. Exiting.")
    exit()

  all_image_files = sorted([
    os.path.join(input_folder, f)
    for f in os.listdir(input_folder)
    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'))
  ])

  num_total_images = len(all_image_files)
  print(f"\nFound {num_total_images} image(s) in '{input_folder}'.")

  if num_total_images == 0:
    print("No images found in the input folder. Exiting.")
    exit()
  
  if num_total_images < 9 : 
    print(f"Info: Only {num_total_images} image(s) found. Need at least 9 images to create a full print sheet. Exiting.")
    exit() 

  num_sheets_created = 0
  num_images_to_process_in_full_sheets = (num_total_images // 9) * 9 

  if num_images_to_process_in_full_sheets == 0 : 
      print(f"Not enough images ({num_total_images}) to form a complete sheet of 9. Exiting.")
      exit()

  if FORCE_STANDARD_FRAME_TYPE: # Add a print statement here as well for global context
    print("\nCONFIG: All cards will be processed as 'standard' frame type due to FORCE_STANDARD_FRAME_TYPE=True.\n")

  for i in range(0, num_images_to_process_in_full_sheets, 9):
    current_chunk_paths = all_image_files[i : i + 9]
    
    first_file_sanitized = sanitize_filename_component(current_chunk_paths[0])
    last_file_sanitized = sanitize_filename_component(current_chunk_paths[-1])
    
    output_sheet_name = f"{first_file_sanitized}_to_{last_file_sanitized}_sheet_{num_sheets_created + 1}.png"
    full_output_path_for_sheet = os.path.join(output_dir_path, output_sheet_name)

    print(f"\n--- Processing Batch {num_sheets_created + 1} for {output_sheet_name} ---")
    create_printable_sheet(current_chunk_paths, full_output_path_for_sheet)
    num_sheets_created += 1
  
  print(f"\n--- Summary ---")
  if num_sheets_created > 0:
    print(f"Finished processing. Created {num_sheets_created} print sheet(s) in '{output_dir_path}'.")
  elif num_total_images > 0 : 
    print(f"No full print sheets were created (total images: {num_total_images}, needed 9 per sheet).")
  else: 
    pass 

  leftover_count = num_total_images % 9
  if leftover_count > 0:
    print(f"Note: {leftover_count} image(s) were left over as they did not form a full batch of 9.")
    print("Leftover files:")
    for leftover_idx in range(num_images_to_process_in_full_sheets, num_total_images):
      print(f"  - {os.path.basename(all_image_files[leftover_idx])}")