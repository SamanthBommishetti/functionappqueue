import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient
import json
import os
import uuid

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Upload request received')

    conn_str = os.getenv("AzureWebJobsStorage")
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)

    # Use plain text messages (default) – no base64 policy
    queue_client = QueueClient.from_connection_string(conn_str, queue_name="image-jobs")

    try:
        # Handle multipart/form-data first
        if req.files and "file" in req.files:
            file = req.files["file"]
            file_content = file.read()
            original_name = file.filename
        else:
            # Fallback: raw body assumed to be the image binary
            file_content = req.get_body()
            original_name = "uploaded.jpg"

        if not file_content:
            return func.HttpResponse("No image data", status_code=400)

        # Upload original
        filename = f"{uuid.uuid4()}{os.path.splitext(original_name)[1]}"
        blob_client = blob_service_client.get_blob_client(container="uploads", blob=filename)
        blob_client.upload_blob(file_content, overwrite=True)
        blob_url = blob_client.url

        # Enqueue plain JSON string
        message = json.dumps({"blobUrl": blob_url, "sizes": [320, 1024]})
        queue_client.send_message(message)   # plain text, no base64

        return func.HttpResponse(
            json.dumps({"originalUrl": blob_url, "status": "enqueued"}),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.exception("Upload failed")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)