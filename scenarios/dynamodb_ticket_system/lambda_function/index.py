import json
import os
import time
import uuid

import boto3
from boto3.dynamodb.conditions import Attr, Key

TABLE_NAME = os.environ.get("TICKET_TABLE", "tickets")

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://floci:4566"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
)

table = dynamodb.Table(TABLE_NAME)


def _list_available():
    response = table.scan(
        FilterExpression=Attr("status").eq("available"),
        ProjectionExpression="ticket_id,event_name,seat,price,section",
    )
    return response.get("Items", [])


def _get_ticket(ticket_id):
    response = table.get_item(Key={"ticket_id": ticket_id})
    item = response.get("Item")
    if not item:
        return None
    item.pop("ttl", None)
    return item


def _reserve_ticket(ticket_id, customer_email):
    now = int(time.time())
    ttl = now + 900

    try:
        table.update_item(
            Key={"ticket_id": ticket_id},
            UpdateExpression="SET #st = :reserved, customer_email = :email, reserved_at = :now, #ttl = :ttl",
            ConditionExpression=Attr("status").eq("available"),
            ExpressionAttributeNames={
                "#st": "status",
                "#ttl": "ttl",
            },
            ExpressionAttributeValues={
                ":reserved": "reserved",
                ":email": customer_email,
                ":now": now,
                ":ttl": ttl,
            },
            ReturnValues="ALL_NEW",
        )
        return {"success": True, "ticket_id": ticket_id, "status": "reserved", "expires_in": "15 minutes"}
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"success": False, "ticket_id": ticket_id, "error": "Ticket already reserved or purchased"}


def _purchase_ticket(ticket_id):
    try:
        response = table.update_item(
            Key={"ticket_id": ticket_id},
            UpdateExpression="SET #st = :purchased, purchased_at = :now REMOVE ttl",
            ConditionExpression=Attr("status").eq("reserved"),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":purchased": "purchased",
                ":now": int(time.time()),
            },
            ReturnValues="ALL_NEW",
        )
        item = response.get("Attributes", {})
        item.pop("ttl", None)
        return {"success": True, "ticket": item}
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"success": False, "ticket_id": ticket_id, "error": "Ticket is not reserved"}


def _release_ticket(ticket_id):
    try:
        table.update_item(
            Key={"ticket_id": ticket_id},
            UpdateExpression="SET #st = :available REMOVE customer_email, reserved_at, #ttl",
            ConditionExpression=Attr("status").eq("reserved"),
            ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
            ExpressionAttributeValues={":available": "available"},
            ReturnValues="ALL_NEW",
        )
        return {"success": True, "ticket_id": ticket_id, "status": "available"}
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"success": False, "ticket_id": ticket_id, "error": "Cannot release - ticket not in reserved state"}


def handler(event, context):
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    body = event.get("body", "{}")
    if body:
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    if http_method == "GET" and path == "/tickets":
        tickets = _list_available()
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"tickets": tickets, "count": len(tickets)}),
        }

    if http_method == "GET" and path.startswith("/tickets/"):
        ticket_id = path.split("/")[-1]
        ticket = _get_ticket(ticket_id)
        if not ticket:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Ticket not found"}),
            }
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ticket": ticket}),
        }

    if http_method == "PUT" and path.startswith("/tickets/") and path.endswith("/reserve"):
        ticket_id = path.split("/")[-2]
        email = body.get("email", "")
        if not email:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "email is required"}),
            }
        result = _reserve_ticket(ticket_id, email)
        status = 200 if result["success"] else 409
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }

    if http_method == "PUT" and path.startswith("/tickets/") and path.endswith("/purchase"):
        ticket_id = path.split("/")[-2]
        result = _purchase_ticket(ticket_id)
        status = 200 if result["success"] else 409
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }

    if http_method == "PUT" and path.startswith("/tickets/") and path.endswith("/release"):
        ticket_id = path.split("/")[-2]
        result = _release_ticket(ticket_id)
        status = 200 if result["success"] else 409
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not found"}),
    }
