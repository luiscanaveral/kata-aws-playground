import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class CassandraOrdersStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        role = iam.Role(
            self,
            "CassandraLambdaRole",
            role_name="cassandra-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*", "sqs:*", "s3:*"],
                resource=["*"],
            )
        )

        s3.CfnBucket(
            self,
            "OrderReceiptsBucket",
            bucket_name="order-receipts",
        )

        queue = sqs.CfnQueue(
            self,
            "OrderNotificationsQueue",
            queue_name="order-notifications",
        )

        fn = lambda_.Function(
            self,
            "CassandraOrderProcessor",
            function_name="cassandra-order-processor",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/cassandra_orders/lambda_function"
            ),
            role=role,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            environment={
                "CASSANDRA_HOST": "cassandra",
                "CASSANDRA_KEYSPACE": "orders_app",
            },
        )

        lambda_.CfnEventSourceMapping(
            self,
            "CassandraESM",
            function_name=fn.function_name,
            event_source_arn=queue.attr_arn,
            batch_size=5,
        )

        cdk.CfnOutput(
            self,
            "QueueUrl",
            value=queue.attr_queue_url,
            export_name="CassandraOrderQueueUrl",
        )
