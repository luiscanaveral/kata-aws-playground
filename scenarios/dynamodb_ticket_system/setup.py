import io
import json
import zipfile

from scenarios.common import account_id, aws_client

API_NAME = "ticket-system-api"
FUNCTION_NAME = "ticket-system-handler"
STAGE_NAME = "v1"


def create_lambda_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write("scenarios/dynamodb_ticket_system/lambda_function/index.py", "index.py")
    return buf.getvalue()


def setup():
    lambda_client = aws_client("lambda")
    apigw_client = aws_client("apigateway")
    dynamodb_client = aws_client("dynamodb")
    iam_client = aws_client("iam")

    aws_account_id = account_id()
    region = "us-east-1"
    table_name = "tickets"

    role_arn = f"arn:aws:iam::{aws_account_id}:role/ticket-lambda-role"
    try:
        iam_client.create_role(
            RoleName="ticket-lambda-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="ticket-lambda-role",
            PolicyName="ticket-lambda-policy",
            PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:*","dynamodb:*"],"Resource":"*"}]}',
        )
        print("Created IAM role: ticket-lambda-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists")

    try:
        dynamodb_client.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "ticket_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "ticket_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb_client.get_waiter("table_exists").wait(TableName=table_name)
        print(f"DynamoDB table created: {table_name}")
    except dynamodb_client.exceptions.ResourceInUseException:
        print(f"DynamoDB table already exists: {table_name}")

    table_desc = dynamodb_client.describe_table(TableName=table_name)
    print(f"  Table status: {table_desc['Table']['TableStatus']}")

    zip_bytes = create_lambda_zip()
    try:
        fn = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.13",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=15,
            MemorySize=128,
            Environment={
                "Variables": {
                    "TICKET_TABLE": table_name,
                    "AWS_ENDPOINT_URL": "http://floci:4566",
                }
            },
        )
        fn_arn = fn["FunctionArn"]
        print(f"Lambda function created: {fn_arn}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName=FUNCTION_NAME, ZipFile=zip_bytes
        )
        lambda_client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Environment={
                "Variables": {
                    "TICKET_TABLE": table_name,
                    "AWS_ENDPOINT_URL": "http://floci:4566",
                }
            },
        )
        fn = lambda_client.get_function(FunctionName=FUNCTION_NAME)
        fn_arn = fn["Configuration"]["FunctionArn"]
        print(f"Lambda function updated: {fn_arn}")

    rest_apis = apigw_client.get_rest_apis()
    existing_api = next(
        (a for a in rest_apis.get("items", []) if a["name"] == API_NAME), None
    )

    if existing_api:
        api_id = existing_api["id"]
        print(f"API Gateway already exists: {api_id}")
    else:
        api = apigw_client.create_rest_api(
            name=API_NAME,
            description="Ticket Selling System API",
        )
        api_id = api["id"]
        print(f"API Gateway created: {api_id}")

        resources = apigw_client.get_resources(restApiId=api_id)
        root_id = resources["items"][0]["id"]

        tickets_res = apigw_client.create_resource(
            restApiId=api_id, parentId=root_id, pathPart="tickets"
        )

        apigw_client.put_method(
            restApiId=api_id,
            resourceId=tickets_res["id"],
            httpMethod="GET",
            authorizationType="NONE",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=tickets_res["id"],
            httpMethod="GET",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
        )

        ticket_id_res = apigw_client.create_resource(
            restApiId=api_id,
            parentId=tickets_res["id"],
            pathPart="{ticketId}",
        )

        apigw_client.put_method(
            restApiId=api_id,
            resourceId=ticket_id_res["id"],
            httpMethod="GET",
            authorizationType="NONE",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=ticket_id_res["id"],
            httpMethod="GET",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
        )

        for action in ["reserve", "purchase", "release"]:
            action_res = apigw_client.create_resource(
                restApiId=api_id,
                parentId=ticket_id_res["id"],
                pathPart=action,
            )
            apigw_client.put_method(
                restApiId=api_id,
                resourceId=action_res["id"],
                httpMethod="PUT",
                authorizationType="NONE",
            )
            apigw_client.put_integration(
                restApiId=api_id,
                resourceId=action_res["id"],
                httpMethod="PUT",
                type="AWS_PROXY",
                integrationHttpMethod="POST",
                uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
            )

        print("API Gateway resources and methods created")

    apigw_client.create_deployment(
        restApiId=api_id,
        stageName=STAGE_NAME,
    )
    print(f"API deployed to stage: {STAGE_NAME}")

    invoke_url = f"http://localhost:4566/restapis/{api_id}/{STAGE_NAME}/_user_request_"

    if existing_api is None:
        dynamodb_client.put_item(
            TableName=table_name,
            Item={
                "ticket_id": {"S": "TICKET-001"},
                "event_name": {"S": "AWS re:Invent 2026"},
                "section": {"S": "VIP"},
                "seat": {"S": "A1"},
                "price": {"N": "499.99"},
                "status": {"S": "available"},
            },
        )
        dynamodb_client.put_item(
            TableName=table_name,
            Item={
                "ticket_id": {"S": "TICKET-002"},
                "event_name": {"S": "AWS re:Invent 2026"},
                "section": {"S": "Standard"},
                "seat": {"S": "B42"},
                "price": {"N": "199.99"},
                "status": {"S": "available"},
            },
        )
        dynamodb_client.put_item(
            TableName=table_name,
            Item={
                "ticket_id": {"S": "TICKET-003"},
                "event_name": {"S": "re:Invent After Party"},
                "section": {"S": "GA"},
                "seat": {"S": "GA-Enter"},
                "price": {"N": "79.99"},
                "status": {"S": "available"},
            },
        )
        dynamodb_client.put_item(
            TableName=table_name,
            Item={
                "ticket_id": {"S": "TICKET-004"},
                "event_name": {"S": "AWS re:Invent 2026"},
                "section": {"S": "VIP"},
                "seat": {"S": "A2"},
                "price": {"N": "499.99"},
                "status": {"S": "available"},
            },
        )
        print("Seeded DynamoDB with 4 sample tickets")

    return {
        "api_id": api_id,
        "invoke_url": invoke_url,
        "function_name": FUNCTION_NAME,
        "table_name": table_name,
    }


if __name__ == "__main__":
    ctx = setup()
    print(f"\nSetup complete.")
    print(f"API URL: {ctx['invoke_url']}")
    print(f"Table:   {ctx['table_name']}")
