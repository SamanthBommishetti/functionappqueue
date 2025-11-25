# functionappqueue
Queue-driven Image Resizer

This project resizes images using Azure Functions, Blob Storage, and Storage Queues.

POST /api/upload accepts an image and stores it in uploads/ container.

A queue message is created: { "blobUrl": "...", "sizes":[320,1024] }.

Queue-triggered Function picks up the message.

Images are resized to the specified sizes.

Resized images are stored under resized/<size>/.

JSON logs are written in function-logs/ImageResizer/<date>/.

Errors are retried; after 5 attempts messages go to dead-letter queue.

Uses azure-storage-blob and Pillow for upload and resizing.

Run locally with func start and test HTTP upload via API.
