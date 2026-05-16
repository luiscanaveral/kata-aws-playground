import io
import json
import zipfile
from pathlib import Path

from scenarios.common import account_id, aws_client

FUNCTIONS = {
    "sfn-validate-order": "validate_order.py",
    "sfn-check-inventory": "check_inventory.py",
    "sfn-process-payment": "process_payment.py",
    "sfn-send-confirmation": "send_confirmation.py",
}

BASE_DIR = Path(__file__).parent


def create_lambda_zip(handler_file: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(str(BASE_DIR / "functions" / handler_file), "index.py")
    return buf.getvalue()


def setup():
    lambda_client = aws_client("lambda")
    sfn_client = aws_client("stepfunctions")
    iam_client = aws_client("iam")

    aws_account_id = account_id()

    role_arn = f"arn:aws:iam::{aws_account_id}:role/sfn-lambda-role"
    try:
        iam_client.create_role(
            RoleName="sfn-lambda-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="sfn-lambda-role",
            PolicyName="sfn-lambda-policy",
            PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:*","lambda:InvokeFunction"],"Resource":"*"}]}',
        )
        print("Created IAM role: sfn-lambda-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists")

    sfn_role_arn = f"arn:aws:iam::{aws_account_id}:role/sfn-execution-role"
    try:
        iam_client.create_role(
            RoleName="sfn-execution-role",
            AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"states.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        )
        iam_client.put_role_policy(
            RoleName="sfn-execution-role",
            PolicyName="sfn-execution-policy",
            PolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": "*"},
                    {"Effect": "Allow", "Action": ["sqs:SendMessage", "events:*"], "Resource": "*"},
                ],
            }),
        )
        print("Created IAM role: sfn-execution-role")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role sfn-execution-role already exists")

    fn_arns = {}
    for fn_name, handler_file in FUNCTIONS.items():
        zip_bytes = create_lambda_zip(handler_file)
        try:
            fn = lambda_client.create_function(
                FunctionName=fn_name,
                Runtime="python3.13",
                Role=role_arn,
                Handler="index.handler",
                Code={"ZipFile": zip_bytes},
                Timeout=10,
                MemorySize=128,
            )
            fn_arns[fn_name] = fn["FunctionArn"]
            print(f"Lambda created: {fn_name}")
        except lambda_client.exceptions.ResourceConflictException:
            lambda_client.update_function_code(
                FunctionName=fn_name, ZipFile=zip_bytes
            )
            fn = lambda_client.get_function(FunctionName=fn_name)
            fn_arns[fn_name] = fn["Configuration"]["FunctionArn"]
            print(f"Lambda updated: {fn_name}")

    sm_path = BASE_DIR / "state_machine.json"
    with open(sm_path) as f:
        definition = f.read()

    for fn_name, arn in fn_arns.items():
        definition = definition.replace(f"arn:aws:lambda:us-east-1:000000000000:function:{fn_name}", arn)

    state_machines = sfn_client.list_state_machines()
    existing_sm = next(
        (sm for sm in state_machines.get("stateMachines", []) if sm["name"] == "order-processing-workflow"),
        None,
    )

    if existing_sm:
        sfn_client.update_state_machine(
            stateMachineArn=existing_sm["stateMachineArn"],
            definition=definition,
            roleArn=sfn_role_arn,
        )
        sm_arn = existing_sm["stateMachineArn"]
        print(f"State machine updated: {sm_arn}")
    else:
        sm = sfn_client.create_state_machine(
            name="order-processing-workflow",
            definition=definition,
            roleArn=sfn_role_arn,
        )
        sm_arn = sm["stateMachineArn"]
        print(f"State machine created: {sm_arn}")

    return {
        "sm_arn": sm_arn,
        "function_names": list(FUNCTIONS.keys()),
    }


if __name__ == "__main__":
    ctx = setup()
    print(f"\nState machine ARN: {ctx['sm_arn']}")
