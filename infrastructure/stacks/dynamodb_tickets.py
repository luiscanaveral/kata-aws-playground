import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_apigateway as apigw
from constructs import Construct


class DynamodbTicketsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        table = dynamodb.Table(
            self,
            "TicketsTable",
            table_name="tickets",
            partition_key=dynamodb.Attribute(
                name="ticket_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        role = iam.Role(
            self,
            "TicketLambdaRole",
            role_name="ticket-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*", "dynamodb:*"],
                resources=["*"],
            )
        )

        fn = lambda_.Function(
            self,
            "TicketSystemHandler",
            function_name="ticket-system-handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/dynamodb_ticket_system/lambda_function"
            ),
            role=role,
            timeout=cdk.Duration.seconds(15),
            memory_size=128,
            environment={
                "TICKET_TABLE": table.table_name,
                "AWS_ENDPOINT_URL": "http://floci:4566",
            },
        )

        api = apigw.LambdaRestApi(
            self,
            "TicketSystemApi",
            rest_api_name="ticket-system-api",
            handler=fn,
            proxy=False,
        )

        tickets = api.root.add_resource("tickets")
        tickets.add_method("GET")

        ticket_id = tickets.add_resource("{ticketId}")
        ticket_id.add_method("GET")

        ticket_id.add_resource("reserve").add_method("PUT")
        ticket_id.add_resource("purchase").add_method("PUT")
        ticket_id.add_resource("release").add_method("PUT")
