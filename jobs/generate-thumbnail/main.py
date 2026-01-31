import functions_framework
from google.cloud import storage
from PIL import Image
import io
import os

storage_client = storage.Client()

@functions_framework.cloud_event
def generate_thumbnail(cloud_event):
    """
    Cloud Function triggered by a change to a Cloud Storage bucket.
    """
    data = cloud_event.data

    event_id = cloud_event["id"]
    event_type = cloud_event["type"]
    bucket_name = data["bucket"]
    name = data["name"]

    print(f"Event ID: {event_id}")
    print(f"Event Type: {event_type}")
    print(f"Bucket: {bucket_name}")
    print(f"File: {name}")

    # Prevent infinite loops and only process files in the 'optimized/' directory (excluding 'thumbnail/')
    # Expected structure: optimized/filename.webp
    # Target structure: optimized/thumbnail/filename.webp
    
    # 1. Must be in 'optimized/'
    if not name.startswith("optimized/"):
        print(f"Skipping {name}: Not in 'optimized/' directory.")
        return

    # 2. Must NOT be in 'optimized/thumbnail/' (or just 'thumbnail/') to avoid loops
    if "/thumbnail/" in name:
        print(f"Skipping {name}: Already a thumbnail.")
        return

    # 3. Process the image
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(name)
        
        # Download image to memory
        image_bytes = blob.download_as_bytes()
        image = Image.open(io.BytesIO(image_bytes))

        # Calculate new size (4x smaller dimensions)
        original_width, original_height = image.size
        new_width = int(original_width / 4)
        new_height = int(original_height / 4)
        
        print(f"Resizing from {original_width}x{original_height} to {new_width}x{new_height}")

        # Resize
        image.thumbnail((new_width, new_height))

        # Prepare path for thumbnail
        # original: optimized/my-image.png (or .webp)
        # target: optimized/thumbnail/my-image.webp
        dirname, basename = os.path.split(name)
        filename, _ = os.path.splitext(basename)
        
        # We replace 'optimized/' with 'optimized/thumbnail/' in the path
        thumbnail_path = name.replace("optimized/", "optimized/thumbnail/", 1).replace(basename, f"{filename}.webp")

        # Save to buffer as WebP
        thumb_buffer = io.BytesIO()
        image.save(thumb_buffer, format="WEBP")
        thumb_buffer.seek(0)

        # Upload thumbnail
        thumbnail_blob = bucket.blob(thumbnail_path)
        thumbnail_blob.upload_from_file(thumb_buffer, content_type="image/webp")
        thumbnail_blob.make_public()

        print(f"Thumbnail created at gs://{bucket_name}/{thumbnail_path}")

    except Exception as e:
        print(f"Error processing {name}: {e}")
        # Depending on requirements, we might want to raise the error to retry, 
        # but for image processing issues, retries often fail similarly.
        # For now, we log and exit.
