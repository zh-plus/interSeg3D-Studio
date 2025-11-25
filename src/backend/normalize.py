from pathlib import Path

import open3d as o3d
import numpy as np

scan_path = Path("interactive_dataset/scene_00_reconstructed_00/scan.ply")
transformed_path = scan_path.with_stem('transformed_mesh')

# Read the point cloud from 'scan.ply'
pcd = o3d.io.read_triangle_mesh(scan_path)
print(f"Loaded point cloud with {len(pcd.vertices)} points")

# Define the rotation matrix (R)
R = np.array([
    [0.99204412, 0.09793481, -0.07910274],
    [0.09793481, -0.20555151, 0.97373372],
    [0.07910274, -0.97373372, -0.21350739]
])

# Define the translation vector (t)
t = np.array([0.0, 0.0, 1.14547409])

# Create a 4x4 transformation matrix
transform = np.eye(4)  # Initialize as identity matrix
transform[:3, :3] = R  # Set the top-left 3x3 block as the rotation matrix
transform[:3, 3] = t   # Set the first three elements of the last column as the translation vector

# Apply the transformation to the point cloud
pcd.transform(transform)

# Save the transformed point cloud to 'transformed_scan.ply'
o3d.io.write_triangle_mesh(transformed_path, pcd)
print(f"Transformed point cloud saved as '{transformed_path}'")