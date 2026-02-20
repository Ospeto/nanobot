from PIL import Image

# Load the texture map
img = Image.open('nanobot/daemon/static/models/digivice/digivice_kiban.png')
w, h = img.size

# The Digicode Outer Ring is roughly in the top left.
# It seems to be approximately x:0, y:0, w:360, h:360 (on a 512x512)
# The Screen Circuit Inner Ring is roughly in the bottom right.
# Let's crop them based on visual estimation.
runes = img.crop((0, 0, int(w*0.75), int(h*0.75)))
runes.save('nanobot/daemon/static/models/digivice/runes.png')

circuit = img.crop((int(w*0.60), int(h*0.50), w, h))
circuit.save('nanobot/daemon/static/models/digivice/circuit.png')

print("Split complete")
