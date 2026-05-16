import json

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct


LAMBDA_NAMES = {
    "validate_order": "sfn-validate-order",
    "check_inventory": "sfn-check-inventory",
    "process_payment": "sfn-process-payment",
    "send_confirmation": "sfn-send-confirmation",
}


class StepFunctionsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        role = iam.Role(
            self,
            "StepFunctionsLambdaRole",
            role_name="stepfunctions-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*"],
                resources=["*"],
            )
        )

        sf_role = iam.Role(
            self,
            "StepFunctionsExecRole",
            role_name="stepfunctions-exec-role",
            assumed_by=iam.ServicePrincipal(
                "states.us-east-1.amazonaws.com"
            ),
        )

        functions = {}
        for module_name, fn_name in LAMBDA_NAMES.items():
            fn = lambda_.Function(
                self,
                f"{fn_name.replace('-', '_').title()}Lambda",
                function_name=fn_name,
                runtime=lambda_.Runtime.PYTHON_3_13,
                handler=f"{module_name}.handler",
                code=lambda_.Code.from_asset(
                    "scenarios/stepfunctions_orchestration/functions"
                ),
                role=role,
                timeout=cdk.Duration.seconds(15),
                memory_size=128,
            )
            functions[fn_name] = fn

            sf_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["lambda:InvokeFunction"],
                    resources=[fn.function_arn],
                )
            )

        state_machine_path = (
            "scenarios/stepfunctions_orchestration/state_machine.json"
        )
        with open(state_machine_path) as f:
            raw = json.load(f)

        definition_str = json.dumps(raw)
        for fn_name, fn in functions.items():
            old_arn = f"arn:aws:lambda:us-east-1:000000000000:function:{fn_name}"
            definition_str = definition_str.replace(old_arn, fn.function_arn)

        sfn.CfnStateMachine(
            self,
            "OrderStateMachine",
            state_machine_name="order-processing-workflow",
            role_arn=sf_role.role_arn,
            definition_string=definition_str,
        )
