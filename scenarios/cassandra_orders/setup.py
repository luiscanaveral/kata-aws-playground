import io
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from scenarios.common import account_id, aws_client


def _install_deps(target_dir: str):
    deps = ["cassandra-driver"]
    for dep in deps:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                dep,
                "-t",
                target_dir,
                "--platform",
                "manylinux2014_x86_64",
                "--python-version",
                "3.13",
                "--only-binary=:all:",
                "--no-deps",
            ],
            check=False,
            capture_output=True,
        )


def create_lambda_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(
            "scenarios/cassandra_orders/lambda_function/index.py", "index.py"
        )
    return buf.getvalue()


def setup():
    lambda_client = aws_client("lambda")
    iam_client = aws_client("iam")
    sqs_client = aws_client("sqs")
    s3_client = aws_client("s3")

    aws_account_id = account_id()
    region = "us-east-1"

    role_arn = f"arn:aws:iam::{aws_account_id}:role/cassandra-lambda-role"
    try:
        iam_client.create_role(
            RoleName="cassandra-lambda-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="cassandra-lambda-role",
            PolicyName="cassandra-lambda-policy",
            PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:*","sqs:*","s3:*"],"Resource":"*"}]}',
        )
        print("Created IAM role: cassandra-lambda-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists")

    for bucket in ["order-receipts"]:
        try:
            s3_client.create_bucket(Bucket=bucket)
            print(f"S3 bucket created: {bucket}")
        except s3_client.exceptions.BucketAlreadyExists:
            print(f"S3 bucket already exists: {bucket}")

    queue = sqs_client.create_queue(QueueName="order-notifications")
    queue_url = queue["QueueUrl"]
    queue_arn = sqs_client.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    print(f"SQS queue created: {queue_url}")

    zip_bytes = create_lambda_zip()
    try:
        fn = lambda_client.create_function(
            FunctionName="cassandra-order-processor",
            Runtime="python3.13",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=30,
            MemorySize=256,
            Environment={
                "Variables": {
                    "CASSANDRA_HOST": "cassandra",
                    "CASSANDRA_KEYSPACE": "orders_app",
                    "ORDER_QUEUE_URL": queue_url,
                }
            },
        )
        fn_arn = fn["FunctionArn"]
        print(f"Lambda function created: {fn_arn}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName="cassandra-order-processor", ZipFile=zip_bytes
        )
        lambda_client.update_function_configuration(
            FunctionName="cassandra-order-processor",
            Environment={
                "Variables": {
                    "CASSANDRA_HOST": "cassandra",
                    "CASSANDRA_KEYSPACE": "orders_app",
                    "ORDER_QUEUE_URL": queue_url,
                }
            },
        )
        fn = lambda_client.get_function(FunctionName="cassandra-order-processor")
        fn_arn = fn["Configuration"]["FunctionArn"]
        print(f"Lambda function updated: {fn_arn}")

    esm = lambda_client.create_event_source_mapping(
        FunctionName="cassandra-order-processor",
        EventSourceArn=queue_arn,
        BatchSize=5,
    )
    print(f"Event source mapping created: {esm['UUID']}")

    return {
        "function_name": "cassandra-order-processor",
        "queue_url": queue_url,
        "queue_arn": queue_arn,
    }


if __name__ == "__main__":
    ctx = setup()
    print(f"\nSetup complete. Lambda: {ctx['function_name']}, Queue: {ctx['queue_url']}")
