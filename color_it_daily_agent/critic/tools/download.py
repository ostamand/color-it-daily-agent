import os
import tempfile
from google.cloud import storage

def download_image(gcs_path: str) -> str:
    """
    Downloads an image from Google Cloud Storage to a local temporary path.
    
    Args:
        gcs_path (str): The GCS path (e.g., gs://bucket-name/path/to/image.png)
        
    Returns:
        str: The local file path where the image was downloaded.
    """
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path: {gcs_path}")

    # Parse GCS path
    path_parts = gcs_path[5:].split("/", 1)
    if len(path_parts) != 2:
        raise ValueError(f"Invalid GCS path format: {gcs_path}")
        
    bucket_name, blob_name = path_parts

    # Initialize client
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Create a temporary file
    _, temp_local_path = tempfile.mkstemp(suffix=os.path.splitext(blob_name)[1])
    
    # Download the file
    blob.download_to_filename(temp_local_path)
    
    print(f"Downloaded {gcs_path} to {temp_local_path}")
    return temp_local_path
