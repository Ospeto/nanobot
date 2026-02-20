from PIL import Image

# Open the source texture
img = Image.open('nanobot/daemon/static/models/digivice/digivice_kiban.png').convert("RGBA")
w, h = img.size

# The pink runes ring surrounds the left half LCD box.
# Let's crop exactly the rune circle.
# Estimating coordinates:
left_x = int(w * 0.0)
top_y = int(h * 0.0)
right_x = int(w * 0.65)
bottom_y = int(h * 0.65)
runes_crop = img.crop((left_x, top_y, right_x, bottom_y))
runes_crop.save('nanobot/daemon/static/models/digivice/runes_ring.png')

# The black circuit ring is on the bottom right.
left_x2 = int(w * 0.45)
top_y2 = int(h * 0.45)
right_x2 = int(w * 1.0)
bottom_y2 = int(h * 1.0)
circuit_crop = img.crop((left_x2, top_y2, right_x2, bottom_y2))
circuit_crop.save('nanobot/daemon/static/models/digivice/circuit_ring.png')

print(f"Runes saved: {runes_crop.size}, Circuit saved: {circuit_crop.size}")
