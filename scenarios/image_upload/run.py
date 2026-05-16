import base64
import io
import json

from scenarios.common import aws_client


def create_test_image() -> bytes:
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return b"fake-image-data-placeholder"


def run():
    lambda_client = aws_client("lambda")
    s3 = aws_client("s3")

    image_bytes = create_test_image()
    image_b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "filename": "test-image.png",
        "content_type": "image/png",
        "body": image_b64,
    }

    print(f"Invoking Lambda with image ({len(image_bytes)} bytes)...")
    resp = lambda_client.invoke(
        FunctionName="image-upload-processor",
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )

    result = json.loads(resp["Payload"].read())
    print(f"Lambda response: {json.dumps(result, indent=2)}")

    if resp["StatusCode"] == 200:
        print("\nChecking stored image in S3...")
        try:
            obj = s3.get_object(Bucket="images", Key="test-image.png")
            stored_size = obj["ContentLength"]
            print(f"Image found in S3 (bucket=images, key=test-image.png, size={stored_size} bytes)")
            print("SUCCESS: Image uploaded and stored in S3 via Lambda.")
        except s3.exceptions.NoSuchKey:
            print("ERROR: Image not found in S3.")


if __name__ == "__main__":
    run()
