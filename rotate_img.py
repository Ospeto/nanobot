from PIL import Image
import os

input_path = "nanobot/daemon/static/dv_front_top.png"
output_path = "nanobot/daemon/static/digivice_proper.png"

img = Image.open(input_path)
# Rotate 90 degrees counter-clockwise
img_rotated = img.rotate(90, expand=True)

# Crop transparent borders to tighten it up
bbox = img_rotated.getbbox()
if bbox:
    img_rotated = img_rotated.crop(bbox)

# Add some padding
width, height = img_rotated.size
new_img = Image.new("RGBA", (width + 40, height + 40), (0, 0, 0, 0))
new_img.paste(img_rotated, (20, 20))

new_img.save(output_path)
print(f"Saved correctly oriented image to {output_path}")
