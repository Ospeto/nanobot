from PIL import Image

img = Image.open('nanobot/daemon/static/models/digivice/digivice_kiban.png').convert("RGBA")
w, h = img.size

# We know the runes are bright pink/white. 
# Let's crop the top-left area where the runes ring is:
runes_crop = img.crop((0, 0, int(w * 0.65), int(h * 0.65)))
data = runes_crop.getdata()

new_data = []
for item in data:
    # item is (R, G, B, A)
    # The runes are very bright, mostly pink/white. The PCB is dark/greenish.
    # Let's check brightness.
    # Actually, the pink runes are highly saturated in Red and Blue, or just very bright white.
    r, g, b, a = item
    
    # If the pixel is very bright or pinkish, keep it as white. Otherwise, make it transparent.
    # Let's use a simple luminance threshold.
    luminance = (r * 0.299 + g * 0.587 + b * 0.114)
    if luminance > 160 or (r > 180 and b > 150): # It's pink/white rune
        # Make the rune pure white, with alpha based on how bright it is 
        new_data.append((255, 255, 255, int(min(255, max(0, (luminance - 150) * 2)))))
    else:
        new_data.append((255, 255, 255, 0))

runes_crop.putdata(new_data)
runes_crop.save('nanobot/daemon/static/models/digivice/pure_runes.png')

# Also let's extract the black circuit ring cleanly for the inner bezel
circuit_crop = img.crop((int(w * 0.45), int(h * 0.45), w, h))
circuit_crop.save('nanobot/daemon/static/models/digivice/pure_circuit.png')

print("Extraction complete")
