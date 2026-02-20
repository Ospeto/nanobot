import collada
import trimesh
import pyrender
import numpy as np
from PIL import Image
import os

print("Starting high-fidelity render...")

MODEL_DIR = "nanobot/daemon/static/models/digivice"
MODEL_PATH = os.path.join(MODEL_DIR, "ID00021_00000000.dae")
OUTPUT_PATH = "nanobot/daemon/static/digivice_proper.png"

mesh = collada.Collada(MODEL_PATH)
print("Collada loaded.")

# Load textures
textures = {}
for img in mesh.images:
    tex_path = os.path.join(MODEL_DIR, img.path)
    if os.path.exists(tex_path):
        textures[img.id] = Image.open(tex_path).convert("RGBA")

# Mat to Tex
mat_tex_map = {}
for mat in mesh.materials:
    if hasattr(mat.effect, 'diffuse') and hasattr(mat.effect.diffuse, 'sampler'):
        sampler_str = str(mat.effect.diffuse.sampler)
        for img in mesh.images:
            if img.id in sampler_str and img.id in textures:
                mat_tex_map[mat.id] = textures[img.id]
                break

scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.6, 0.6, 0.6])

all_verts_for_bounds = []

for geom in mesh.geometries:
    for prim in geom.primitives:
        tris = prim.triangleset()
        if tris is None: continue
        
        # Unroll the triangles to unique vertices to properly map UVs
        indices = tris.vertex_index
        verts = tris.vertex[indices] # shape (N, 3, 3)
        verts = verts.reshape(-1, 3) # shape (N*3, 3)
        all_verts_for_bounds.extend(verts)
        
        # Normals
        if tris.normal is not None and tris.normal_index is not None:
            norms = tris.normal[tris.normal_index].reshape(-1, 3)
        else:
            norms = None
            
        # UVs
        uvs = None
        if hasattr(tris, 'texcoordset') and len(tris.texcoordset) > 0:
            uv_coords = tris.texcoordset[0]
            uv_indices = tris.texcoord_indexset[0]
            uvs = uv_coords[uv_indices].reshape(-1, 2)
            
        # Create unrolled faces: [0, 1, 2], [3, 4, 5], ...
        num_verts = len(verts)
        faces = np.arange(num_verts).reshape(-1, 3)
        
        # Determine material/texture
        tex_img = None
        mat_id = prim.material if hasattr(prim, 'material') else None
        if mat_id:
            for mid, tex in mat_tex_map.items():
                if mat_id in mid:
                    tex_img = tex
                    break
        
        # Build trimesh
        tmesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        if norms is not None:
            tmesh.vertex_normals = norms
            
        if tex_img is not None and uvs is not None:
            material = pyrender.MetallicRoughnessMaterial(
                baseColorTexture=pyrender.Texture(source=np.array(tex_img)),
                roughnessFactor=0.8,
                metallicFactor=0.1,
                alphaMode='BLEND'
            )
            # Trimesh visuals to hold UVs
            tmesh.visual = trimesh.visual.TextureVisuals(uv=uvs, image=tex_img)
        else:
            material = pyrender.MetallicRoughnessMaterial(
                baseColorFactor=[0.26, 0.83, 0.88, 1.0],
                roughnessFactor=0.5,
                metallicFactor=0.1
            )
            
        pr_mesh = pyrender.Mesh.from_trimesh(tmesh, material=material, smooth=False)
        scene.add(pr_mesh)

print("Geometry added to scene.")

# Determine bounds
all_verts_for_bounds = np.array(all_verts_for_bounds)
min_b = all_verts_for_bounds.min(axis=0)
max_b = all_verts_for_bounds.max(axis=0)
center = (min_b + max_b) / 2.0
extent = max_b - min_b
max_ext = max(extent)

# Camera (Orthographic might be better, but let's use Perspective)
camera = pyrender.PerspectiveCamera(yfov=np.pi / 5.0, aspectRatio=1.0)
# To see the front face (Z-axis look down)
# Wait, based on earlier renders, elev=90 azim=0 was top down Y-axis.
# Let's set up the camera to look down the Y axis.
cam_pose = np.eye(4)
cam_pose[:3, :3] = trimesh.transformations.rotation_matrix(np.radians(-90), [1, 0, 0])[:3, :3]
# Move camera up Y axis
cam_pose[0, 3] = center[0]
cam_pose[1, 3] = center[1] + max_ext * 2.5
cam_pose[2, 3] = center[2]
scene.add(camera, pose=cam_pose)

# Light
light = pyrender.DirectionalLight(color=np.ones(3), intensity=4.0)
scene.add(light, pose=cam_pose)

# Render
print("Rendering offscreen...")
r = pyrender.OffscreenRenderer(1024, 1024)
color, depth = r.render(scene, flags=pyrender.RenderFlags.RGBA)
r.delete()

# Crop and save
img = Image.fromarray(color)
bbox = img.getbbox()
if bbox:
    img = img.crop(bbox)

# Add padding
w, h = img.size
pad = 30
new_img = Image.new("RGBA", (w + pad*2, h + pad*2), (0,0,0,0))
new_img.paste(img, (pad, pad))

new_img.save(OUTPUT_PATH)
print(f"Rendered to {OUTPUT_PATH}")
