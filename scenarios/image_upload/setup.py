import io
import zipfile

from scenarios.common import account_id, aws_client


def create_lambda_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write("scenarios/image_upload/lambda_function/index.py", "index.py")
    return buf.getvalue()


def setup():
    s3_client = aws_client("s3")
    lambda_client = aws_client("lambda")
    iam_client = aws_client("iam")

    aws_account_id = account_id()

    role_arn = f"arn:aws:iam::{aws_account_id}:role/lambda-exec-role"
    try:
        iam_client.create_role(
            RoleName="lambda-exec-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="lambda-exec-role",
            PolicyName="lambda-basic-execution",
            PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:*","s3:*","sqs:*","kinesis:*","dynamodb:*"],"Resource":"*"}]}',
        )
        print("Created IAM role: lambda-exec-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists")

    for bucket in ["uploads", "images"]:
        try:
            s3_client.create_bucket(Bucket=bucket)
            print(f"S3 bucket created: {bucket}")
        except s3_client.exceptions.BucketAlreadyExists:
            print(f"S3 bucket already exists: {bucket}")
        except s3_client.exceptions.BucketAlreadyOwnedByYou:
            print(f"S3 bucket already owned: {bucket}")

    zip_bytes = create_lambda_zip()

    try:
        fn = lambda_client.create_function(
            FunctionName="image-upload-processor",
            Runtime="python3.13",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=30,
            MemorySize=256,
            Environment={
                "Variables": {
                    "UPLOAD_BUCKET": "images",
                    "AWS_ENDPOINT_URL": "http://floci:4566",
                }
            },
        )
        print(f"Lambda function created: {fn['FunctionArn']}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName="image-upload-processor", ZipFile=zip_bytes
        )
        lambda_client.update_function_configuration(
            FunctionName="image-upload-processor",
            Environment={
                "Variables": {
                    "UPLOAD_BUCKET": "images",
                    "AWS_ENDPOINT_URL": "http://floci:4566",
                }
            },
        )
        print("Lambda function updated")

    return {"function_name": "image-upload-processor", "upload_bucket": "uploads", "images_bucket": "images"}


if __name__ == "__main__":
    ctx = setup()
    print(f"\nSetup complete. Buckets: {ctx['upload_bucket']}, {ctx['images_bucket']}")
