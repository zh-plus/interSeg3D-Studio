import os
import shutil
import tempfile
from typing import Dict, List, Any

import numpy as np
import open3d as o3d
import torch
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import app_utils  # Import our custom utility functions
# Import the inference module
from inference import Click, ClickHandler, PointCloudInference
from interactive_tool.utils import get_obj_color  # Import for object coloring
from visual_obj_recognition import mask_obj_recognition

# Create static directory if it doesn't exist
static_dir = os.path.join(os.getcwd(), "static")
os.makedirs(static_dir, exist_ok=True)

app = FastAPI(title="AGILE3D Interactive Segmentation API")

# Mount the static files directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Add CORS middleware with specific allowed origins
app.add_middleware(
    CORSMiddleware,
    # List specific origins instead of using wildcard "*"
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state (in a real application, you might want to use a database)
current_point_cloud = None
current_point_cloud_path = None
current_inference: PointCloudInference | None = None
current_results = None
current_object_info = None  # Store object recognition results


class InferenceRequest(BaseModel):
    clickData: Dict[str, Dict[str, Any]]  # clickIdx, clickTimeIdx, clickPositions
    cubeSize: float
    objectNames: List[str]


class MaskObjDetectionRequest(BaseModel):
    # "mask" is a list of integers where 0 is background, 1 is first object, 2 is second object, etc.
    mask: list


@app.post("/api/upload")
async def upload_point_cloud(file: UploadFile = File(...)):
    """
    Upload a point cloud file (PLY format)
    """
    global current_point_cloud, current_point_cloud_path, current_inference

    # Create a temporary directory to store the uploaded file
    temp_dir = tempfile.mkdtemp()
    try:
        # Save the uploaded file
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Store the file path for later use
        current_point_cloud_path = file_path

        # Load the point cloud
        pcd_type = o3d.io.read_file_geometry_type(file_path)

        if pcd_type == o3d.io.FileGeometry.CONTAINS_TRIANGLES:
            # It's a mesh
            mesh = o3d.io.read_triangle_mesh(file_path)
            coords = np.array(mesh.vertices)
            colors = np.array(mesh.vertex_colors) if mesh.has_vertex_colors() else np.ones(
                (len(mesh.vertices), 3)) * 0.5
            is_point_cloud = False
        elif pcd_type == o3d.io.FileGeometry.CONTAINS_POINTS:
            # It's a point cloud
            pcd = o3d.io.read_point_cloud(file_path)
            coords = np.array(pcd.points)
            colors = np.array(pcd.colors) if pcd.has_colors() else np.ones((len(pcd.points), 3)) * 0.5
            is_point_cloud = True
        else:
            return JSONResponse(
                status_code=400,
                content={"message": f"Unsupported file format: {file.filename}"}
            )

        # Initialize the inference object
        current_inference = PointCloudInference(
            pretraining_weights='agile3d/weights/checkpoint1099.pth',
            voxel_size=0.05
        )
        current_inference.load_point_cloud(file_path)

        # Store the full point cloud data (but don't return it to client)
        current_point_cloud = {
            "is_point_cloud": is_point_cloud,
            "coords": coords,
            "colors": colors,
            "point_count": len(coords)
        }

        # Return only metadata - no point cloud data
        return JSONResponse(content={
            "message": "File uploaded successfully",
            "filename": file.filename,
            "pointCount": len(coords),
            "boundingBox": {
                "min": coords.min(axis=0).tolist(),
                "max": coords.max(axis=0).tolist()
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Error processing file: {str(e)}"}
        )


@app.post("/api/infer")
async def run_inference(request: InferenceRequest):
    """
    Run inference on the current point cloud with the provided click data
    """
    global current_inference, current_results

    if not current_inference:
        return JSONResponse(
            status_code=400,
            content={"message": "No point cloud loaded. Please upload a point cloud first."}
        )

    try:
        # Convert click data to format expected by inference
        click_handler = ClickHandler()

        # Process click positions and create Click objects
        for obj_idx_str, positions in request.clickData["clickPositions"].items():
            obj_idx = int(obj_idx_str)
            obj_name = "background" if obj_idx == 0 else f"object_{obj_idx}"

            # Get time indices for this object
            time_indices = request.clickData["clickTimeIdx"][obj_idx_str]

            for i, pos in enumerate(positions):
                # Create click and add to handler
                click = Click(
                    position=torch.tensor(pos, dtype=torch.float32),
                    obj_idx=obj_idx,
                    obj_name=obj_name,
                    time_idx=time_indices[i],
                    is_positive=True,
                    cube_size=request.cubeSize
                )
                click_handler.clicks.append(click)

                # Find nearest point in the point cloud
                click.find_nearest_point(current_inference.raw_coords_qv)

                # Update model-compatible formats
                click_handler._update_click_dicts(click)

        # Set clicks in the inference object
        current_inference.click_handler = click_handler

        # Run inference
        mask = current_inference.run_inference()

        # Save the results
        colored_ply = current_inference.save_results(
            mask,
            output_dir="./outputs",
            prefix=f"web_session_{os.path.basename(os.path.splitext(current_point_cloud_path)[0])}"
        )

        # Store the results for later download
        current_results = {
            "mask": mask,
            "result_path": colored_ply
        }

        # Prepare segmentation results for frontend
        segmentation = mask.tolist()

        print(f'number of positive in mask: {segmentation.count(True)}')

        return JSONResponse(content={
            "message": "Inference completed successfully",
            "segmentedPointCloud": {
                "segmentation": segmentation
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Error running inference: {str(e)}"}
        )


def mask_obj_recognition_worker(args):
    obj_id, point_cloud_path, mask_np = args
    # Use mask_np.copy() if necessary to avoid sharing issues.
    return mask_obj_recognition(point_cloud_path, mask_np.copy(), obj_id)


@app.post("/api/mask_obj_recognition")
async def run_mask_obj_recognition(request: MaskObjDetectionRequest):
    """
    Run mask-based object recognition on the current point cloud using provided mask.

    The request body should contain a field "mask" that is a list of integers where:
      - 0 represents the background
      - 1 represents the first object
      - 2 represents the second object, and so on.

    Returns:
      - A list of JSON objects with keys "selected_views", "description", "label", and "cost",
        one for each unique object ID in the mask (excluding background).
    """
    global current_point_cloud_path, current_object_info
    if not current_point_cloud_path:
        return JSONResponse(
            status_code=400,
            content={"message": "No point cloud loaded. Please upload a point cloud first."}
        )
    try:
        mask = request.mask
        if not isinstance(mask, list):
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid mask format. Please provide a list of integers."}
            )

        # Convert to numpy array.
        mask_np = np.array(mask, dtype=int)

        # Find unique object IDs, excluding background (0).
        unique_obj_ids = np.unique(mask_np)
        unique_obj_ids = unique_obj_ids[unique_obj_ids > 0]

        if len(unique_obj_ids) == 0:
            return JSONResponse(
                status_code=400,
                content={"message": "No objects found in the mask (all values are 0/background)."}
            )

        # Prepare arguments for each object.
        work_args = [
            (obj_id, current_point_cloud_path, mask_np)
            for obj_id in unique_obj_ids
        ]

        # Process each object in parallel.
        import multiprocessing
        with multiprocessing.Pool() as pool:
            result = pool.map(mask_obj_recognition_worker, work_args)

        # Store the results for later use in download
        current_object_info = result

        return JSONResponse(content={
            "message": "Mask object recognition completed successfully",
            "result": result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Error running mask object recognition: {str(e)}"}
        )


@app.get("/api/download-results")
async def download_results():
    """
    Download the segmentation results as a zip file containing:
    1. A PLY file with uncolored scene and colored objects
    2. A JSON file with object labels, descriptions, colors, and other metadata
    """
    global current_results, current_object_info, current_inference, current_point_cloud_path, current_point_cloud

    if not current_results or not current_results.get("result_path"):
        return JSONResponse(
            status_code=400,
            content={"message": "No results available. Please run inference first."}
        )

    try:
        # Create a temporary directory for the zip files
        import tempfile
        import json
        import shutil
        import os.path

        temp_dir = tempfile.mkdtemp()
        try:
            mask = current_results["mask"]

            # Get point cloud data - either from cached data or load from file
            if current_point_cloud:
                coords = current_point_cloud["coords"]
                colors = current_point_cloud["colors"]
                is_point_cloud = current_point_cloud["is_point_cloud"]
            else:
                # Load point cloud data from file
                coords, colors, is_point_cloud = app_utils.load_point_cloud_data(current_point_cloud_path)

            # Create a PLY file with uncolored scene and colored objects
            new_ply_path = os.path.join(temp_dir, "scene_with_colored_objects.ply")
            app_utils.create_colored_ply(
                coords=coords,
                colors=colors,
                mask=mask,
                is_point_cloud=is_point_cloud,
                original_geometry_path=current_point_cloud_path,
                output_path=new_ply_path,
                get_obj_color_func=get_obj_color
            )

            # Verify the PLY file was created
            if not os.path.exists(new_ply_path):
                raise FileNotFoundError(f"Failed to create PLY file at {new_ply_path}")
            print(f"Successfully created PLY file: {new_ply_path}, size: {os.path.getsize(new_ply_path)} bytes")

            # Generate metadata JSON
            metadata = app_utils.generate_metadata_json(
                mask=mask,
                new_ply_path=new_ply_path,
                original_file_path=current_point_cloud_path,
                object_info=current_object_info,
                inference_obj=current_inference,
                get_obj_color_func=get_obj_color
            )

            # Write the JSON file
            json_path = os.path.join(temp_dir, "metadata.json")
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2, cls=app_utils.NumpyEncoder)

            # Verify the JSON file was created
            if not os.path.exists(json_path):
                raise FileNotFoundError(f"Failed to create JSON file at {json_path}")
            print(f"Successfully created JSON file: {json_path}, size: {os.path.getsize(json_path)} bytes")

            # Prepare for zip creation
            zip_path = os.path.join(temp_dir, "segmentation_results.zip")
            files_to_zip = {
                new_ply_path: os.path.basename(new_ply_path),
                json_path: "metadata.json"
            }

            # Create the zip file with explicit error handling
            try:
                app_utils.create_zip_file(files_to_zip, zip_path)

                # Verify the zip file was created
                if not os.path.exists(zip_path):
                    raise FileNotFoundError(f"Zip file was not created at {zip_path}")
                print(f"Successfully created ZIP file: {zip_path}, size: {os.path.getsize(zip_path)} bytes")
            except Exception as zip_error:
                print(f"Error creating zip file: {str(zip_error)}")
                raise

            # Stream the zip file as response
            def iterfile():
                with open(zip_path, 'rb') as f:
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while chunk := f.read(chunk_size):
                        yield chunk

            file_size = os.path.getsize(zip_path)
            headers = {
                'Content-Disposition': f'attachment; filename="segmentation_results.zip"',
                'Content-Type': 'application/zip',
                'Content-Length': str(file_size)
            }

            return StreamingResponse(
                iterfile(),
                headers=headers,
                media_type='application/zip'
            )

        finally:
            # Clean up the temporary directory, but don't delete it until the streaming is complete
            # We'll rely on the StreamingResponse to complete before the function exits
            try:
                # Instead of immediately deleting, we'll schedule deletion after a delay
                # to ensure streaming completes
                import threading

                def delayed_cleanup():
                    import time
                    # Wait a bit to ensure streaming completes
                    time.sleep(10)
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        print(f"Cleaned up temporary directory {temp_dir}")

                # Start cleanup in a separate thread
                threading.Thread(target=delayed_cleanup).start()
            except Exception as cleanup_error:
                print(f"Warning: Error scheduling cleanup: {str(cleanup_error)}")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error downloading results: {str(e)}\n{error_details}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Error downloading results: {str(e)}"}
        )


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn

    # Ensure output directory exists
    os.makedirs("./outputs", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=9501)
