import base64
import json
import os

import boto3

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://floci:4566"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
)


def handler(event, context):
    records = event.get("Records", [])

    for record in records:
        bucket = record.get("s3", {}).get("bucket", {}).get("name", "")
        key = record.get("s3", {}).get("object", {}).get("key", "")

        if key:
            print(f"S3 event: {bucket}/{key}")
            return {"statusCode": 200, "body": json.dumps("ok")}

    filename = event.get("filename", "upload.bin")
    content_type = event.get("content_type", "application/octet-stream")
    body_b64 = event.get("body", "")
    body = base64.b64decode(body_b64)

    s3.put_object(
        Bucket=os.environ["UPLOAD_BUCKET"],
        Key=filename,
        Body=body,
        ContentType=content_type,
    )

    print(f"Stored {filename} in {os.environ['UPLOAD_BUCKET']}")
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"bucket": os.environ["UPLOAD_BUCKET"], "key": filename, "size": len(body)}
        ),
    }
