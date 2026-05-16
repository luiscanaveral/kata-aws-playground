import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class SnsFanoutStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        feed_table = dynamodb.Table(
            self,
            "SocialPostsTable",
            table_name="social_posts",
            partition_key=dynamodb.Attribute(
                name="post_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        topic = sns.Topic(
            self,
            "SocialFeedTopic",
            topic_name="social-feed-topic",
        )

        feed_queue = sqs.Queue(
            self,
            "FeedQueue",
            queue_name="feed-queue",
            visibility_timeout=Duration.seconds(30),
        )
        topic.add_subscription(
            subscriptions.SqsSubscription(feed_queue, raw_message_delivery=False)
        )

        audit_queue = sqs.Queue(
            self,
            "AuditQueue",
            queue_name="audit-queue",
            visibility_timeout=Duration.seconds(30),
        )
        topic.add_subscription(
            subscriptions.SqsSubscription(audit_queue, raw_message_delivery=False)
        )

        feed_role = iam.Role(
            self,
            "FeedProcessorRole",
            role_name="feed-processor-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        feed_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*", "dynamodb:*"],
                resources=["*"],
            )
        )

        feed_processor = lambda_.Function(
            self,
            "FeedProcessor",
            function_name="feed-processor",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/sns_fanout/functions/process_feed"
            ),
            role=feed_role,
            timeout=Duration.seconds(10),
            memory_size=128,
            environment={
                "FEED_TABLE": feed_table.table_name,
                "AWS_ENDPOINT_URL": "http://floci:4566",
            },
        )
        feed_queue.grant_consume_messages(feed_processor)
        feed_processor.add_event_source_mapping(
            "FeedSqsTrigger",
            event_source_arn=feed_queue.queue_arn,
            batch_size=5,
        )

        audit_role = iam.Role(
            self,
            "AuditLoggerRole",
            role_name="audit-logger-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        audit_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*"],
                resources=["*"],
            )
        )

        audit_logger = lambda_.Function(
            self,
            "AuditLogger",
            function_name="audit-logger",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/sns_fanout/functions/process_audit"
            ),
            role=audit_role,
            timeout=Duration.seconds(10),
            memory_size=128,
        )
        audit_queue.grant_consume_messages(audit_logger)
        audit_logger.add_event_source_mapping(
            "AuditSqsTrigger",
            event_source_arn=audit_queue.queue_arn,
            batch_size=5,
        )

        api_role = iam.Role(
            self,
            "FeedApiRole",
            role_name="feed-api-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        api_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*", "dynamodb:*"],
                resources=["*"],
            )
        )

        api_fn = lambda_.Function(
            self,
            "FeedApi",
            function_name="feed-api",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/sns_fanout/functions/api"
            ),
            role=api_role,
            timeout=Duration.seconds(10),
            memory_size=128,
            environment={
                "FEED_TABLE": feed_table.table_name,
                "AWS_ENDPOINT_URL": "http://floci:4566",
            },
        )

        api = apigw.LambdaRestApi(
            self,
            "SocialFeedApi",
            rest_api_name="social-feed-api",
            handler=api_fn,
            proxy=False,
        )
        root = api.root
        root.add_method("GET")
        root.add_resource("feed").add_method("GET")
