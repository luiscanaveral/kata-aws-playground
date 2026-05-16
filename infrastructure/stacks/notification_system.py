import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class NotificationSystemStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        pkg_table = dynamodb.Table(
            self,
            "PackagesTable",
            table_name="notification_packages",
            partition_key=dynamodb.Attribute(
                name="package_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        pref_table = dynamodb.Table(
            self,
            "PreferencesTable",
            table_name="notification_preferences",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        event_queue = sqs.CfnQueue(
            self,
            "DriverEventsQueue",
            queue_name="driver-events",
        )

        topic = sns.CfnTopic(
            self,
            "NotificationsTopic",
            topic_name="notifications-topic",
        )

        role = iam.Role(
            self,
            "NotificationLambdaRole",
            role_name="notification-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*", "dynamodb:*", "sqs:*", "sns:*"],
                resources=["*"],
            )
        )

        fn = lambda_.Function(
            self,
            "NotificationHandler",
            function_name="notification-system-handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/notification_system/lambda_function",
            ),
            role=role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "PKG_TABLE": pkg_table.table_name,
                "PREF_TABLE": pref_table.table_name,
                "EVENT_QUEUE_URL": event_queue.attr_queue_url,
                "SNS_TOPIC_ARN": topic.attr_topic_arn,
                "REDIS_HOST": "redis",
                "REDIS_PORT": "6379",
                "AWS_ENDPOINT_URL": "http://floci:4566",
            },
        )

        lambda_.CfnEventSourceMapping(
            self,
            "NotificationSQSEventSource",
            function_name=fn.function_name,
            event_source_arn=event_queue.attr_arn,
            batch_size=5,
        )

        api = apigw.LambdaRestApi(
            self,
            "NotificationSystemApi",
            rest_api_name="notification-system-api",
            handler=fn,
            proxy=False,
        )

        packages = api.root.add_resource("packages")
        packages.add_method("POST")

        pkg_item = packages.add_resource("{packageId}")
        pkg_item.add_method("GET")

        pkg_item.add_resource("assign").add_method("PUT")
        pkg_item.add_resource("events").add_method("POST")
        pkg_item.add_resource("location").add_method("GET")

        preferences = api.root.add_resource("preferences")
        pref_item = preferences.add_resource("{userId}")
        pref_item.add_method("GET")
        pref_item.add_method("PUT")
