"""
Software rasterizer v3: 2.5D Shading
Adds simple directional lighting (diffuse + ambient) to the Z_pos projection to make it look 3D/2.5D instead of totally flat.
"""
import collada
import numpy as np
from PIL import Image
import os

MODEL_DIR = "nanobot/daemon/static/models/digivice"
MODEL_PATH = os.path.join(MODEL_DIR, "ID00021_00000000.dae")
W, H = 1200, 1200

print("Loading model for 2.5D shaded render...")
mesh = collada.Collada(MODEL_PATH)

textures = {}
for img in mesh.images:
    tex_path = os.path.join(MODEL_DIR, img.path)
    if os.path.exists(tex_path):
        textures[img.id] = np.array(Image.open(tex_path).convert("RGBA"))

mat_tex_map = {}
for mat in mesh.materials:
    if hasattr(mat.effect, 'diffuse') and hasattr(mat.effect.diffuse, 'sampler'):
        sampler_str = str(mat.effect.diffuse.sampler)
        for img_obj in mesh.images:
            if img_obj.id in sampler_str and img_obj.id in textures:
                mat_tex_map[mat.id] = img_obj.id
                break

triangles_data = []
for geom in mesh.geometries:
    for prim in geom.primitives:
        tris = prim.triangleset()
        if tris is None: continue
        
        verts = tris.vertex
        indices = tris.vertex_index
        norms = tris.normal if tris.normal is not None else None
        norm_indices = tris.normal_index if tris.normal_index is not None else None
        
        has_uv = hasattr(tris, 'texcoordset') and len(tris.texcoordset) > 0
        uv_coords = tris.texcoordset[0] if has_uv else None
        uv_indices = tris.texcoord_indexset[0] if has_uv else None

        mat_id = prim.material if hasattr(prim, 'material') else None
        tex_id = None
        if mat_id:
            for mid, tid in mat_tex_map.items():
                if mat_id in mid:
                    tex_id = tid
                    break

        for i in range(len(indices)):
            v = verts[indices[i]]
            uv = uv_coords[uv_indices[i]] if uv_coords is not None and uv_indices is not None else None
            
            n = None
            if norms is not None and norm_indices is not None:
                n = norms[norm_indices[i]]
            else:
                # compute face normal
                v0, v1, v2 = v
                n_face = np.cross(v1 - v0, v2 - v0)
                n_len = np.linalg.norm(n_face)
                if n_len > 0:
                    n_face = n_face / n_len
                n = np.array([n_face, n_face, n_face])
                
            triangles_data.append((v, uv, n, tex_id))

all_v = np.array([t[0] for t in triangles_data]).reshape(-1, 3)
min_b = all_v.min(axis=0)
max_b = all_v.max(axis=0)
extent = max_b - min_b

def barycentric(px, py, v0, v1, v2):
    d00 = (v1[0]-v0[0])**2 + (v1[1]-v0[1])**2
    d01 = (v1[0]-v0[0])*(v2[0]-v0[0]) + (v1[1]-v0[1])*(v2[1]-v0[1])
    d11 = (v2[0]-v0[0])**2 + (v2[1]-v0[1])**2
    d20 = (px-v0[0])*(v1[0]-v0[0]) + (py-v0[1])*(v1[1]-v0[1])
    d21 = (px-v0[0])*(v2[0]-v0[0]) + (py-v0[1])*(v2[1]-v0[1])
    denom = d00*d11 - d01*d01
    if abs(denom) < 1e-10: return -1, -1, -1
    v = (d11*d20 - d01*d21) / denom
    w = (d00*d21 - d01*d20) / denom
    return 1.0-v-w, v, w

# Rendering Z_pos view with directional lighting
# light direction (coming from top-left)
light_dir = np.array([-0.5, 0.8, 1.0])
light_dir = light_dir / np.linalg.norm(light_dir)
ambient = 0.4
diffuse_strength = 0.8

color_buf = np.zeros((H, W, 4), dtype=np.uint8)
depth_buf = np.full((H, W), -np.inf, dtype=np.float64)

margin = 0.075
scale = 1.0 - 2*margin
fwd, right, up, depth_sign = 2, 0, 1, 1 

for tri_verts, tri_uvs, tri_norms, tex_id in triangles_data:
    pts = []
    for v in tri_verts:
        sx = (v[right] - min_b[right]) / extent[right] * (W * scale) + W * margin
        sy = (1.0 - (v[up] - min_b[up]) / extent[up]) * (H * scale) + H * margin
        d = v[fwd] * depth_sign
        pts.append((sx, sy, d))
    
    p0, p1, p2 = pts
    min_x = max(0, int(min(p0[0], p1[0], p2[0])))
    max_x = min(W-1, int(max(p0[0], p1[0], p2[0])) + 1)
    min_y = max(0, int(min(p0[1], p1[1], p2[1])))
    max_y = min(H-1, int(max(p0[1], p1[1], p2[1])) + 1)
    if max_x <= min_x or max_y <= min_y: continue
    
    tex_arr = textures.get(tex_id) if tex_id else None
    
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            u, v, w = barycentric(px+0.5, py+0.5, p0, p1, p2)
            if u < 0 or v < 0 or w < 0: continue
            depth = u*p0[2] + v*p1[2] + w*p2[2]
            if depth <= depth_buf[py, px]: continue
            depth_buf[py, px] = depth
            
            # Interpolate normal
            n = u*tri_norms[0] + v*tri_norms[1] + w*tri_norms[2]
            n_len = np.linalg.norm(n)
            if n_len > 0: n = n / n_len
            
            # Simple diffuse shading
            dot_l = max(0.0, np.dot(n, light_dir))
            light_mult = min(1.0, ambient + diffuse_strength * dot_l)
            
            # Get base color
            base_color = [66, 212, 224, 255]
            if tex_arr is not None and tri_uvs is not None:
                tu = u*tri_uvs[0][0] + v*tri_uvs[1][0] + w*tri_uvs[2][0]
                tv = u*tri_uvs[0][1] + v*tri_uvs[1][1] + w*tri_uvs[2][1]
                th, tw2 = tex_arr.shape[:2]
                tx = int(np.clip(tu % 1.0, 0, 0.999) * tw2)
                ty = int(np.clip(1.0 - (tv % 1.0), 0, 0.999) * th)
                pixel = tex_arr[ty, tx]
                if pixel[3] > 0:
                    base_color = pixel
            
            # Apply shading
            r = int(min(255, base_color[0] * light_mult))
            g = int(min(255, base_color[1] * light_mult))
            b = int(min(255, base_color[2] * light_mult))
            a = base_color[3]
            
            # Add a slight specular highlight to make it look plasticky
            specular = 0
            if dot_l > 0.92:
                specular = int(255 * ((dot_l - 0.92) / 0.08))
            
            r = min(255, r + specular)
            g = min(255, g + specular)
            b = min(255, b + specular)
            
            color_buf[py, px] = [r, g, b, a]

img = Image.fromarray(color_buf)
bbox = img.getbbox()
if bbox: img = img.crop(bbox)
w_i, h_i = img.size
pad = 20
final = Image.new("RGBA", (w_i+pad*2, h_i+pad*2), (0,0,0,0))
final.paste(img, (pad, pad))
path = "nanobot/daemon/static/digivice_proper.png"
final.save(path)
print(f"Saved 2.5D shaded render to {path} ({final.size})")
