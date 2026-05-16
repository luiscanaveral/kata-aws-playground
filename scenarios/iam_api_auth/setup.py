import io
import json
import zipfile

from scenarios.common import account_id, aws_client

API_NAME = "iam-orders-api"
FUNCTION_NAME = "iam-orders-handler"
STAGE_NAME = "v1"


def create_lambda_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write("scenarios/iam_api_auth/lambda_function/index.py", "index.py")
    return buf.getvalue()


def setup():
    lambda_client = aws_client("lambda")
    iam_client = aws_client("iam")
    apigw_client = aws_client("apigateway")
    sts_client = aws_client("sts")

    aws_account_id = account_id()
    region = "us-east-1"

    role_arn = f"arn:aws:iam::{aws_account_id}:role/lambda-apigw-role"
    try:
        iam_client.create_role(
            RoleName="lambda-apigw-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="lambda-apigw-role",
            PolicyName="lambda-apigw-policy",
            PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:*"],"Resource":"*"}]}',
        )
        print("Created IAM role: lambda-apigw-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists")

    admin_arn = None
    try:
        admin = iam_client.create_user(UserName="api-admin")
        iam_client.attach_user_policy(
            UserName="api-admin",
            PolicyArn=f"arn:aws:iam::aws:policy/AdministratorAccess",
        )
        admin_keys = iam_client.create_access_key(UserName="api-admin")
        admin_arn = admin["User"]["Arn"]
        print(f"Created IAM user: api-admin (ARN: {admin_arn})")
    except iam_client.exceptions.EntityAlreadyExistsException:
        admin = iam_client.get_user(UserName="api-admin")
        admin_arn = admin["User"]["Arn"]
        admin_keys = iam_client.create_access_key(UserName="api-admin")
        print(f"IAM user api-admin already exists")

    readonly_arn = None
    try:
        readonly = iam_client.create_user(UserName="api-readonly")
        readonly_arn = readonly["User"]["Arn"]
        print(f"Created IAM user: api-readonly (ARN: {readonly_arn})")
    except iam_client.exceptions.EntityAlreadyExistsException:
        readonly = iam_client.get_user(UserName="api-readonly")
        readonly_arn = readonly["User"]["Arn"]
        print(f"IAM user api-readonly already exists")

    zip_bytes = create_lambda_zip()
    try:
        fn = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.13",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=10,
            MemorySize=128,
        )
        fn_arn = fn["FunctionArn"]
        print(f"Lambda function created: {fn_arn}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName=FUNCTION_NAME, ZipFile=zip_bytes
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
            description="IAM-authorized Orders API",
        )
        api_id = api["id"]
        print(f"API Gateway created: {api_id}")

        resources = apigw_client.get_resources(restApiId=api_id)
        root_id = resources["items"][0]["id"]

        health_res = apigw_client.create_resource(
            restApiId=api_id, parentId=root_id, pathPart="health"
        )
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=health_res["id"],
            httpMethod="GET",
            authorizationType="AWS_IAM",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=health_res["id"],
            httpMethod="GET",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
        )

        orders_res = apigw_client.create_resource(
            restApiId=api_id, parentId=root_id, pathPart="orders"
        )
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=orders_res["id"],
            httpMethod="PUT",
            authorizationType="AWS_IAM",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=orders_res["id"],
            httpMethod="PUT",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
        )

        order_item_res = apigw_client.create_resource(
            restApiId=api_id, parentId=orders_res["id"], pathPart="{orderId}"
        )
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=order_item_res["id"],
            httpMethod="GET",
            authorizationType="AWS_IAM",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=order_item_res["id"],
            httpMethod="GET",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
        )

        print("API Gateway resources and methods created")

    deployment = apigw_client.create_deployment(
        restApiId=api_id,
        stageName=STAGE_NAME,
    )
    print(f"API deployed to stage: {STAGE_NAME}")

    invoke_url = f"http://localhost:4566/restapis/{api_id}/{STAGE_NAME}/_user_request_"

    resource_arn = (
        f"arn:aws:execute-api:{region}:{aws_account_id}:{api_id}/{STAGE_NAME}"
    )

    try:
        iam_client.put_role_policy(
            RoleName="api-admin",
            PolicyName="invoke-orders-api",
            PolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "execute-api:Invoke",
                        "Resource": f"{resource_arn}/*/*",
                    }
                ],
            }),
        )
        print("Added API invoke policy for user: api-admin")
    except Exception as e:
        print(f"Could not create inline policy for api-admin: {e}")

    print(f"\nAPI invoke URL:  {invoke_url}")
    print(f"Resource ARN:    {resource_arn}")

    return {
        "api_id": api_id,
        "invoke_url": invoke_url,
        "admin_arn": admin_arn,
        "admin_keys": admin_keys,
        "readonly_arn": readonly_arn,
        "function_name": FUNCTION_NAME,
    }


if __name__ == "__main__":
    ctx = setup()
    print(f"\nSetup complete.")
    print(f"API URL: {ctx['invoke_url']}")
