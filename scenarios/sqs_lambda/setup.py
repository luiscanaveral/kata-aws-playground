import io
import zipfile

from scenarios.common import account_id, aws_client


def create_lambda_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write("scenarios/sqs_lambda/lambda_function/index.py", "index.py")
    return buf.getvalue()


def setup():
    lambda_client = aws_client("lambda")
    sqs_client = aws_client("sqs")
    iam_client = aws_client("iam")


    aws_account_id = account_id()
    region = "us-east-1"

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

    queue = sqs_client.create_queue(QueueName="order-events")
    queue_url = queue["QueueUrl"]
    print(f"SQS queue created: {queue_url}")

    queue_arn = sqs_client.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]

    zip_bytes = create_lambda_zip()

    try:
        fn = lambda_client.create_function(
            FunctionName="sqs-order-processor",
            Runtime="python3.13",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=10,
            MemorySize=128,
        )
        print(f"Lambda function created: {fn['FunctionArn']}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName="sqs-order-processor", ZipFile=zip_bytes
        )
        print("Lambda function updated")

    mappings = lambda_client.list_event_source_mappings(
        FunctionName="sqs-order-processor"
    )
    existing = any(m["EventSourceArn"] == queue_arn for m in mappings.get("EventSourceMappings", []))

    if not existing:
        esm = lambda_client.create_event_source_mapping(
            FunctionName="sqs-order-processor",
            EventSourceArn=queue_arn,
            BatchSize=5,
        )
        print(f"Event source mapping created: {esm['UUID']}")
    else:
        print("Event source mapping already exists")

    return {"queue_url": queue_url, "queue_arn": queue_arn, "function_name": "sqs-order-processor"}


if __name__ == "__main__":
    ctx = setup()
    print(f"\nSetup complete. Queue URL: {ctx['queue_url']}")
