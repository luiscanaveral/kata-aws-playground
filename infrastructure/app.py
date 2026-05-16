import os

import aws_cdk as cdk

from infrastructure.stacks.base import BaseStack
from infrastructure.stacks.sqs_lambda import SqsLambdaStack
from infrastructure.stacks.image_upload import ImageUploadStack
from infrastructure.stacks.ec2_wordpress import Ec2WordpressStack
from infrastructure.stacks.iam_api_auth import IamApiAuthStack
from infrastructure.stacks.cassandra_orders import CassandraOrdersStack
from infrastructure.stacks.stepfunctions import StepFunctionsStack
from infrastructure.stacks.dynamodb_tickets import DynamodbTicketsStack
from infrastructure.stacks.notification_system import NotificationSystemStack
from infrastructure.stacks.sns_fanout import SnsFanoutStack

app = cdk.App()

floci_endpoint = app.node.try_get_context("floci_endpoint") or "http://localhost:4566"
floci_region = app.node.try_get_context("floci_region") or "us-east-1"
floci_account = app.node.try_get_context("floci_account") or "000000000000"

env = cdk.Environment(account=floci_account, region=floci_region)

BaseStack(app, "BaseStack", env=env, floci_endpoint=floci_endpoint)
SqsLambdaStack(app, "SqsLambdaStack", env=env, floci_endpoint=floci_endpoint)
ImageUploadStack(app, "ImageUploadStack", env=env, floci_endpoint=floci_endpoint)
Ec2WordpressStack(app, "Ec2WordpressStack", env=env, floci_endpoint=floci_endpoint)
IamApiAuthStack(app, "IamApiAuthStack", env=env, floci_endpoint=floci_endpoint)
CassandraOrdersStack(app, "CassandraOrdersStack", env=env, floci_endpoint=floci_endpoint)
StepFunctionsStack(app, "StepFunctionsStack", env=env, floci_endpoint=floci_endpoint)
DynamodbTicketsStack(app, "DynamodbTicketsStack", env=env, floci_endpoint=floci_endpoint)
NotificationSystemStack(app, "NotificationSystemStack", env=env, floci_endpoint=floci_endpoint)
SnsFanoutStack(app, "SnsFanoutStack", env=env, floci_endpoint=floci_endpoint)

app.synth()
