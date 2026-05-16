import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_apigateway as apigw
from constructs import Construct


class IamApiAuthStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        role = iam.Role(
            self,
            "LambdaApigwRole",
            role_name="lambda-apigw-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*"],
                resources=["*"],
            )
        )

        fn = lambda_.Function(
            self,
            "IamOrdersHandler",
            function_name="iam-orders-handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("scenarios/iam_api_auth/lambda_function"),
            role=role,
            timeout=cdk.Duration.seconds(10),
            memory_size=128,
        )

        api = apigw.LambdaRestApi(
            self,
            "IamOrdersApi",
            rest_api_name="iam-orders-api",
            handler=fn,
            proxy=False,
        )

        orders = api.root.add_resource("orders")
        orders.add_method("PUT", authorization_type=apigw.AuthorizationType.IAM)

        order_item = orders.add_resource("{orderId}")
        order_item.add_method("GET", authorization_type=apigw.AuthorizationType.IAM)

        api.root.add_resource("health").add_method(
            "GET", authorization_type=apigw.AuthorizationType.IAM
        )

        iam.CfnUser(
            self,
            "ApiAdminUser",
            user_name="api-admin",
        )
        iam.CfnUser(
            self,
            "ApiReadonlyUser",
            user_name="api-readonly",
        )

        iam.CfnUserPolicy(
            self,
            "ApiAdminPolicy",
            user_name="api-admin",
            policy_name="admin-access",
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": "*", "Resource": "*"}
                ],
            },
        )
