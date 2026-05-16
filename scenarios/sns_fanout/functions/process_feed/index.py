import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = os.environ.get("FEED_TABLE", "social_posts")
FLOCI_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://floci:4566")

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=FLOCI_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    for record in event.get("Records", []):
        try:
            sns_msg = json.loads(record["body"])
        except (json.JSONDecodeError, TypeError):
            continue

        topic_arn = sns_msg.get("TopicArn", "")
        message_str = sns_msg.get("Message", "{}")
        try:
            post = json.loads(message_str)
        except (json.JSONDecodeError, TypeError):
            post = {}

        if not post.get("post_id"):
            continue

        table.put_item(Item=post)
        print(f"Stored post {post['post_id']} from {post.get('username', '?')}")

    return {"statusCode": 200, "body": json.dumps("ok")}
