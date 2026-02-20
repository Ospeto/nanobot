"""
Final render: produce a clean front-facing Digivice PNG at high resolution with proper lighting.
Based on analysis: front face is at elev=90, azim=0 (or slight variants).
We'll render the FRONT face only, with transparent background, and properly lit.
"""
import collada
import numpy as np
from PIL import Image
import os

MODEL_DIR = "nanobot/daemon/static/models/digivice"
MODEL_PATH = os.path.join(MODEL_DIR, "ID00021_00000000.dae")
OUTPUT_PATH = "nanobot/daemon/static/digivice_front.png"

print("Loading model...")
mesh = collada.Collada(MODEL_PATH)

# Load textures
textures = {}
for img in mesh.images:
    tex_path = os.path.join(MODEL_DIR, img.path)
    if os.path.exists(tex_path):
        textures[img.id] = Image.open(tex_path).convert("RGBA")

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

fig = plt.figure(figsize=(14, 14), dpi=100)
ax = fig.add_subplot(111, projection='3d')

# Transparent background
fig.patch.set_alpha(0.0)
ax.set_facecolor((0, 0, 0, 0))
ax.patch.set_alpha(0.0)

all_verts = []

# Build a material -> texture lookup
mat_tex_map = {}
for mat in mesh.materials:
    if hasattr(mat.effect, 'diffuse') and hasattr(mat.effect.diffuse, 'sampler'):
        sampler_str = str(mat.effect.diffuse.sampler)
        for img in mesh.images:
            if img.id in sampler_str and img.id in textures:
                mat_tex_map[mat.id] = textures[img.id]
                break

for geom in mesh.geometries:
    for prim in geom.primitives:
        tris = prim.triangleset()
        if tris is None:
            continue
        
        verts = tris.vertex
        indices = tris.vertex_index
        triangles = verts[indices]
        
        # Get UVs
        has_uv = hasattr(tris, 'texcoordset') and len(tris.texcoordset) > 0
        uv_coords = tris.texcoordset[0] if has_uv else None
        uv_indices = tris.texcoord_indexset[0] if has_uv else None
        
        # Find texture for this primitive
        tex_img = None
        mat_id = prim.material if hasattr(prim, 'material') else None
        if mat_id:
            for mid, tex in mat_tex_map.items():
                if mat_id in mid:
                    tex_img = tex
                    break
        
        for tri in triangles:
            all_verts.extend(tri)
        
        # Sample colors
        face_colors = []
        if has_uv and uv_coords is not None and uv_indices is not None and tex_img is not None:
            tw, th = tex_img.size
            for tri_idx in range(len(uv_indices)):
                uv_tri = uv_coords[uv_indices[tri_idx]]
                center_uv = uv_tri.mean(axis=0)
                px = int(np.clip(center_uv[0], 0, 0.999) * tw)
                py = int(np.clip(1.0 - center_uv[1], 0, 0.999) * th)
                r, g, b, a = tex_img.getpixel((px, py))
                face_colors.append((r/255.0, g/255.0, b/255.0, max(a/255.0, 0.3)))
        else:
            face_colors = [(0.26, 0.83, 0.88, 1.0)] * len(triangles)
        
        poly = Poly3DCollection(triangles, alpha=1.0)
        poly.set_facecolor(face_colors)
        poly.set_edgecolor('none')
        ax.add_collection3d(poly)

if all_verts:
    all_verts = np.array(all_verts)
    xmin, xmax = all_verts[:, 0].min(), all_verts[:, 0].max()
    ymin, ymax = all_verts[:, 1].min(), all_verts[:, 1].max()
    zmin, zmax = all_verts[:, 2].min(), all_verts[:, 2].max()
    
    cx, cy, cz = (xmin+xmax)/2, (ymin+ymax)/2, (zmin+zmax)/2
    extent = max(xmax-xmin, ymax-ymin, zmax-zmin) / 2 * 1.15
    
    ax.set_xlim(cx-extent, cx+extent)
    ax.set_ylim(cy-extent, cy+extent)
    ax.set_zlim(cz-extent, cz+extent)
    
    ax.axis('off')
    
    # Render from multiple candidate front angles
    for elev, azim, name in [
        (90, 0, 'front_top'),
        (-90, 0, 'front_bot'),
        (90, 180, 'front_top_180'),
        (-90, 180, 'front_bot_180'),
        (85, 0, 'front_slight'),
        (-85, 0, 'front_slight_bot'),
    ]:
        ax.view_init(elev=elev, azim=azim)
        path = f"nanobot/daemon/static/dv_{name}.png"
        plt.savefig(path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=120)
        print(f"  Saved: {path}")
    
    # Best guess front face
    ax.view_init(elev=90, azim=0)
    plt.savefig(OUTPUT_PATH, bbox_inches='tight', pad_inches=0, transparent=True, dpi=120)
    print(f"\nFinal saved: {OUTPUT_PATH}")
