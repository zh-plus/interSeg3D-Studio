import json
import os
from pathlib import Path
from pprint import pprint
from typing import List, Tuple

import httpx
import numpy as np
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from inference import infer
# Import the test_camera_positions function from view_rendering.py
from view_rendering import test_camera_positions


class ObjInfo(BaseModel):
    selected_views: List[int]
    description: str
    label: str


def get_cost(response):
    """
    Extracts the cost of the request from the response object.

    Args:
        response (genai.Response): The response object from the Gemini-2.0-flash model.

    Returns:
        float: The cost of the request.
    """
    # per 1M tokens in USD
    input_price = 0.1
    output_price = 0.4

    prompt_token = response.usage_metadata.prompt_token_count
    output_token = response.usage_metadata.candidates_token_count

    cost = (prompt_token + output_token) / 1e6 * (input_price + output_price)

    return cost


def mask_obj_recognition(point_cloud_path: str | Path, mask: np.ndarray | str, obj_id: int) -> Tuple[str, float]:
    """
    Performs mask-based object recognition on a given point cloud using the provided mask.

    This function generates rendered views of the masked object, sends these images along with a prompt
    to the Gemini-2.0-flash model, and returns the model's response text along with the computed cost.

    Args:
        point_cloud_path (str | Path): Path to the 3D point cloud file.
        mask (np.ndarray | str): The mask used to highlight the object of interest. This can be a numpy array or a file path.
        obj_id (int): The ID of the object to recognize.

    Returns:
        Tuple[str, float]: A tuple where the first element is the response text from the model and the second element is the cost of the request.
    """
    # Load environment variables (e.g., for API keys)
    load_dotenv(override=True)

    # Get API key from environment variables
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in the .env file.")

    TIMEOUT = 10000

    # Initialize the Google Gen AI client with your API key.
    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=TIMEOUT))  # 10s timeout

    # Set mask mode for rendering (options: "outline" or "full")
    mask_mode = "outline"

    # Define the output directory for the rendered camera views.
    view_output_dir = f"./object_views/obj_{obj_id}"

    # Generate camera views for the masked object.
    view_paths = test_camera_positions(
        point_cloud_path=point_cloud_path,
        mask=mask,
        output_dir=view_output_dir,
        view_angle=90.0,
        distance_factor=1,
        num_positions=8,
        camera_height=1.5,
        mask_mode=mask_mode,
        obj_id=obj_id,
    )

    # Load the rendered images.
    images = []
    for path in view_paths:
        if os.path.exists(path):
            try:
                images.append(Image.open(path))
            except Exception as e:
                print(f"Error opening {path}: {e}")
        else:
            print(f"Warning: {path} not found.")

    # Construct the analysis prompt.
    prompt = (
        f"I have uploaded a series of rendered views of a scene generated using the '{mask_mode}' mask mode. "
        "Do not describe the mask itself, which is used to highlight the object of interest. "
        "Please analyze these images and select the views with the best quality. Then, according to these good quality images, provide the following:\n"
        "1. A detailed description of the object along with the surrounding scene or any nearby objects.\n"
        "2. A concise label for the masked object."
        "Note, for the description, directly mention the object's attributes, such as color, shape, size, and any other relevant details. For example: 'A black sofa with...' Do not use 'This is a ...' or 'This image shows a ...' in the description."
        "Also, describe the relationship between the object and the surrounding scene or any nearby objects. For example: 'The sofa is placed in front of a desk.'"
        "Never use 'in the scene' or 'in the image' in the description."
    )

    # Call the Gemini-2.0-flash model with the images and the prompt.
    response = None
    for i in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=images + [prompt],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=ObjInfo,
                )
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            print(f"Connection timed out after {TIMEOUT} ms, retrying number: {i + 1}")

    if response is None:
        raise RuntimeError("Failed to get a response from the model after 3 attempts.")

    print('Get response from LLM')

    # Extract response text and compute the cost using the provided helper function.
    response_text = response.text
    cost = get_cost(response)

    result = json.loads(response_text)
    result['cost'] = cost

    # Save the result to a JSON file
    with open(f'{view_output_dir}/result.json', 'w') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    return result


if __name__ == '__main__':
    load_dotenv()

    pcd_path = Path('agile3d/data/interactive_dataset/scene_00_reconstructed_01_transformed_mesh/scan.ply')

    # result_path, mask = infer(
    #     point_cloud_path=pcd_path,
    #     click_positions=[[1.3158004, 1.5544679, 0.4713757], [-0.14292482, 1.3323758, 0.49515364]],
    #     click_obj_indices=[1, 2],
    #     click_obj_names=["sofa", "desk"],
    #     output_dir="./outputs"
    # )

    result_path, mask = infer(
        point_cloud_path=pcd_path,
        click_positions=[[1.3158004, 1.5544679, 0.4713757]],
        click_obj_indices=[1],
        click_obj_names=["sofa"],
        output_dir="./outputs"
    )

    result = mask_obj_recognition(
        point_cloud_path=pcd_path,
        mask=mask,
        obj_id=1
    )

    pprint(result)
