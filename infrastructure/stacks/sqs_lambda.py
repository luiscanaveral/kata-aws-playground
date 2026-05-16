import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_lambda_event_sources as sources
from constructs import Construct


class SqsLambdaStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        queue = sqs.CfnQueue(
            self,
            "OrderEventsQueue",
            queue_name="order-events",
        )

        role = iam.CfnRole(
            self,
            "SqsLambdaRole",
            role_name="sqs-lambda-role",
            assume_role_policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            policies=[
                iam.CfnRole.PolicyProperty(
                    policy_name="sqs-lambda-policy",
                    policy_document={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["logs:*", "sqs:*"],
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
        )

        fn = lambda_.Function(
            self,
            "SqsOrderProcessor",
            function_name="sqs-order-processor",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("scenarios/sqs_lambda/lambda_function"),
            role=iam.Role.from_role_arn(
                self, "SqsLambdaRoleRef", role.attr_arn
            ),
            timeout=cdk.Duration.seconds(10),
            memory_size=128,
        )

        lambda_.CfnEventSourceMapping(
            self,
            "SqsLambdaESM",
            function_name=fn.function_name,
            event_source_arn=queue.attr_arn,
            batch_size=10,
        )
