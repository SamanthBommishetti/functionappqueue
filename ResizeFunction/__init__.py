import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient
from PIL import Image
import io
import json
import os
import time
import uuid

def main(msg: func.QueueMessage) -> None:
    logging.info(f"Processing message DequeueCount={msg.dequeue_count}")

    conn_str = os.getenv("AzureWebJobsStorage")
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    poison_queue = QueueClient.from_connection_string(conn_str, "image-jobs-poison")

    try:
        # The message is plain UTF-8 JSON (default)
        message_text = msg.get_body().decode("utf-8")
        payload = json.loads(message_text)

        blob_url = payload["blobUrl"]
        sizes = payload.get("sizes", [320, 1024])

        # Extract blob name from URL
        blob_name = blob_url.split("/uploads/")[-1]
        original_blob = blob_service.get_blob_client(container="uploads", blob=blob_name)

        stream = original_blob.download_blob()
        image_bytes = stream.readall()
        img = Image.open(io.BytesIO(image_bytes))

        start = time.time()
        output_urls = []

        for size in sizes:
            # Preserve aspect ratio (resize to width = size)
            ratio = size / img.width
            new_height = int(img.height * ratio)
            resized = img.resize((size, new_height), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)

            out_name = f"{uuid.uuid4()}_{size}.jpg"
            out_blob = blob_service.get_blob_client(container="resized", blob=out_name)
            out_blob.upload_blob(buffer, overwrite=True)
            output_urls.append(out_blob.url)

        processing_time = time.time() - start

        # Write log
        log_data = {
            "originalUrl": blob_url,
            "outputUrls": output_urls,
            "processingTimeSec": round(processing_time, 3),
            "status": "success",
            "processedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        log_blob_name = f"ImageResizer/{uuid.uuid4()}.json"
        log_blob = blob_service.get_blob_client(container="function-logs", blob=log_blob_name)
        log_blob.upload_blob(json.dumps(log_data, indent=2), overwrite=True)

        logging.info(f"Success: {blob_url} → {len(output_urls)} resized images")

    except Exception as e:
        logging.exception("Resize failed")
        # After 5 attempts move to poison queue
        if msg.dequeue_count >= 5:
            poison_queue.send_message(message_text)
            logging.warning("Moved to poison queue after 5 failures")
        else:
            raise  # let it retry