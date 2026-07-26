import os
import uuid
import subprocess
import tempfile
from PIL import Image
import cairosvg
from google.cloud import storage
from color_it_daily_agent.app_configs import configs

import os
import uuid
import logging
import subprocess
import tempfile
from PIL import Image
import cairosvg
from google.cloud import storage
from color_it_daily_agent.app_configs import configs
from color_it_daily_agent.context import get_agent_context
from color_it_daily_agent.lib.persistence import get_local_output_dir

logger = logging.getLogger(__name__)

def optimize_image(image_path: str) -> str:
    """
    Optimizes a raw coloring page image for printing by vectorizing it and 
    rendering it at high resolution (2550x3300).
    """
    ctx = get_agent_context()
    no_persist = ctx.no_persist if ctx else False

    if subprocess.call(["which", "potrace"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        raise RuntimeError("The 'potrace' utility is not installed. Please install it (e.g., 'apt-get install potrace') to use this tool.")

    with tempfile.TemporaryDirectory() as temp_dir:
        local_input = os.path.join(temp_dir, "input.png")
        original_filename = "image.png"

        if no_persist or not image_path.startswith("gs://"):
            if os.path.exists(image_path):
                import shutil
                shutil.copyfile(image_path, local_input)
                original_filename = os.path.basename(image_path)
            else:
                raise FileNotFoundError(f"Local image file not found: {image_path}")
        else:
            storage_client = storage.Client(project=configs.gcp_project)
            path_parts = image_path[5:].split("/", 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1]
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.download_to_filename(local_input)
            original_filename = os.path.basename(blob_name)

        # 2. Pre-process (Convert to BMP for Potrace)
        local_bmp = os.path.join(temp_dir, "input.bmp")
        with Image.open(local_input) as img:
            img = img.convert("L")
            threshold = 128
            img = img.point(lambda p: 255 if p > threshold else 0)
            img = img.convert("1")
            img.save(local_bmp)

        # 3. Vectorize (Potrace -> SVG)
        local_svg = os.path.join(temp_dir, "output.svg")
        subprocess.check_call(["potrace", local_bmp, "-s", "-o", local_svg])

        # 4. Render High-Res (SVG -> PNG)
        target_width = 2550
        target_height = 3300
        local_optimized = os.path.join(temp_dir, "optimized.png")
        
        cairosvg.svg2png(
            url=local_svg,
            write_to=local_optimized,
            output_width=target_width,
            output_height=target_height
        )

        local_webp = os.path.join(temp_dir, "optimized.webp")
        with Image.open(local_optimized) as img:
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert("RGBA")
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
            
            img.save(local_optimized, format="PNG")
            img.save(local_webp, format="WEBP")

        if no_persist:
            doc_id = ctx.document_id if ctx else str(uuid.uuid4())
            output_dir = get_local_output_dir(doc_id)
            final_png_path = os.path.join(output_dir, "optimized.png")
            final_webp_path = os.path.join(output_dir, "optimized.webp")
            final_svg_path = os.path.join(output_dir, "optimized.svg")
            
            import shutil
            shutil.copyfile(local_optimized, final_png_path)
            shutil.copyfile(local_webp, final_webp_path)
            shutil.copyfile(local_svg, final_svg_path)
            
            logger.info(f"[NO_PERSIST] Optimized assets saved locally in '{output_dir}'")
            return final_png_path

        # Upload to GCS
        storage_client = storage.Client(project=configs.gcp_project)
        path_parts = image_path[5:].split("/", 1)
        bucket_name = path_parts[0]
        bucket = storage_client.bucket(bucket_name)

        output_filename = f"optimized/{original_filename}"
        output_blob = bucket.blob(output_filename)
        output_blob.upload_from_filename(local_optimized, content_type="image/png")
        output_blob.make_public()

        webp_filename = os.path.splitext(original_filename)[0] + ".webp"
        output_webp_filename = f"optimized/{webp_filename}"
        output_webp_blob = bucket.blob(output_webp_filename)
        output_webp_blob.upload_from_filename(local_webp, content_type="image/webp")
        output_webp_blob.make_public()

        return f"gs://{bucket_name}/{output_filename}"


if __name__ == "__main__":
    # Test stub (requires a valid GCS path to test fully)
    print("Optimize tool loaded.")
