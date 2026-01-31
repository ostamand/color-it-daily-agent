import os
import uuid
import subprocess
import tempfile
from PIL import Image
import cairosvg
from google.cloud import storage
from color_it_daily_agent.app_configs import configs

def optimize_image(image_path: str) -> str:
    """
    Optimizes a raw coloring page image for printing by vectorizing it and 
    rendering it at high resolution (3300x2550).

    Args:
        image_path (str): The GCS path of the raw image (e.g., gs://bucket/raw/xyz.png).

    Returns:
        str: The GCS path of the optimized image (e.g., gs://bucket/optimized/xyz.png).
    """
    
    # Check if potrace is installed
    if subprocess.call(["which", "potrace"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        raise RuntimeError("The 'potrace' utility is not installed. Please install it (e.g., 'apt-get install potrace') to use this tool.")

    storage_client = storage.Client(project=configs.gcp_project)

    # Parse GCS path
    if not image_path.startswith("gs://"):
        raise ValueError("image_path must start with gs://")
    
    path_parts = image_path[5:].split("/", 1)
    bucket_name = path_parts[0]
    blob_name = path_parts[1]

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Extract original filename to keep consistency (e.g., "raw/abc.png" -> "abc.png")
    original_filename = os.path.basename(blob_name)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. Download
        local_input = os.path.join(temp_dir, "input.png")
        blob.download_to_filename(local_input)

        # 2. Pre-process (Convert to BMP for Potrace)
        local_bmp = os.path.join(temp_dir, "input.bmp")
        with Image.open(local_input) as img:
            # Convert to grayscale then to 1-bit monochrome
            # Thresholding might be needed if the input isn't pure B&W, 
            # but usually generated coloring pages are high contrast.
            # We'll use a simple threshold to ensure crisp edges for the tracer.
            img = img.convert("L") # Grayscale
            threshold = 128
            img = img.point(lambda p: 255 if p > threshold else 0)
            img = img.convert("1") # 1-bit pixels, black and white
            img.save(local_bmp)

        # 3. Vectorize (Potrace -> SVG)
        # -s: SVG output
        # -k 0.5: Black level (default)
        # --group: Group paths for easier editing (optional)
        local_svg = os.path.join(temp_dir, "output.svg")
        subprocess.check_call(["potrace", local_bmp, "-s", "-o", local_svg])

        # 4. Render High-Res (SVG -> PNG)
        # Target: 2550x3300 (Portrait)
        # The prompt specifically requested portrait orientation.
        target_width = 2550
        target_height = 3300
        
        local_optimized = os.path.join(temp_dir, "optimized.png")
        
        cairosvg.svg2png(
            url=local_svg,
            write_to=local_optimized,
            output_width=target_width,
            output_height=target_height
        )

        # Post-process: Ensure white background for both PNG and WebP
        with Image.open(local_optimized) as img:
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert("RGBA")
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
            
            # Save corrected PNG
            img.save(local_optimized, format="PNG")
            
            # Save WebP
            local_webp = os.path.join(temp_dir, "optimized.webp")
            img.save(local_webp, format="WEBP")

        # 5. Upload PNG
        output_filename = f"optimized/{original_filename}"
        output_blob = bucket.blob(output_filename)
        output_blob.upload_from_filename(local_optimized, content_type="image/png")
        output_blob.make_public()

        # 6. Upload WebP
        webp_filename = os.path.splitext(original_filename)[0] + ".webp"
        output_webp_filename = f"optimized/{webp_filename}"
        output_webp_blob = bucket.blob(output_webp_filename)
        output_webp_blob.upload_from_filename(local_webp, content_type="image/webp")
        output_webp_blob.make_public()

        return f"gs://{bucket_name}/{output_filename}"

if __name__ == "__main__":
    # Test stub (requires a valid GCS path to test fully)
    print("Optimize tool loaded.")
