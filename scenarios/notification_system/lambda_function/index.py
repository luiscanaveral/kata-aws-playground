import json
import os
import uuid
import time

import boto3
from boto3.dynamodb.conditions import Attr

redis_client = None
try:
    import redis as redis_mod
    redis_client = redis_mod.Redis(
        host=os.environ.get("REDIS_HOST", "redis"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        decode_responses=True,
    )
except ImportError:
    pass

PKG_TABLE = os.environ.get("PKG_TABLE", "notification_packages")
PREF_TABLE = os.environ.get("PREF_TABLE", "notification_preferences")
EVENT_QUEUE_URL = os.environ.get("EVENT_QUEUE_URL", "")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
FLOCI_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://floci:4566")

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=FLOCI_ENDPOINT,
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
)
pkg_table = dynamodb.Table(PKG_TABLE)
pref_table = dynamodb.Table(PREF_TABLE)

sqs = boto3.client(
    "sqs",
    endpoint_url=FLOCI_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

sns = boto3.client(
    "sns",
    endpoint_url=FLOCI_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

CACHE_TTL = 300


def _get_preference_channels(user_id: str) -> list:
    if redis_client:
        cached = redis_client.get(f"pref:{user_id}")
        if cached:
            return json.loads(cached)

    resp = pref_table.get_item(Key={"user_id": user_id})
    item = resp.get("Item")
    channels = item.get("channels", ["SMS"]) if item else ["SMS"]

    if redis_client and item:
        redis_client.setex(f"pref:{user_id}", CACHE_TTL, json.dumps(channels))

    return channels


def _send_notification(user_id: str, event_type: str, pkg_id: str, location: dict | None = None):
    channels = _get_preference_channels(user_id)
    message = json.dumps({
        "event": event_type,
        "package_id": pkg_id,
        "location": location,
        "timestamp": time.time(),
    })

    resp = pref_table.get_item(Key={"user_id": user_id})
    item = resp.get("Item", {})
    phone = item.get("phone_number", "")
    email = item.get("email", "")

    sent = []
    for channel in channels:
        try:
            if channel == "SMS" and phone:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=message,
                    Subject=f"Package {event_type}",
                    MessageAttributes={
                        "channel": {"DataType": "String", "StringValue": "SMS"},
                        "phone": {"DataType": "String", "StringValue": phone},
                    },
                )
                sent.append("SMS")
            elif channel in ("EMAIL", "email") and email:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=message,
                    Subject=f"Package {event_type}",
                    MessageAttributes={
                        "channel": {"DataType": "String", "StringValue": "EMAIL"},
                        "email": {"DataType": "String", "StringValue": email},
                    },
                )
                sent.append("EMAIL")
            else:
                sent.append(f"{channel}_SIMULATED")
        except Exception as e:
            print(f"Notification failed for {channel}: {e}")

    print(f"Notification sent via {sent} to user {user_id} for {event_type}")
    return sent


def _handle_api(event: dict) -> dict:
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    body = event.get("body", "{}")
    if body:
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    parts = [p for p in path.split("/") if p]

    if method == "POST" and path == "/packages":
        pkg_id = f"PKG-{uuid.uuid4().hex[:8].upper()}"
        now = int(time.time())
        pkg_table.put_item(Item={
            "package_id": pkg_id,
            "customer_id": body.get("customer_id", "unknown"),
            "driver_id": "",
            "status": "created",
            "address_from": body.get("address_from", ""),
            "address_to": body.get("address_to", ""),
            "current_location": body.get("address_from", ""),
            "events": [],
            "created_at": now,
            "updated_at": now,
        })
        return _ok({"package_id": pkg_id, "status": "created"})

    if method == "GET" and len(parts) == 2 and parts[0] == "packages":
        resp = pkg_table.get_item(Key={"package_id": parts[1]})
        item = resp.get("Item")
        if not item:
            return _err(404, "Package not found")
        return _ok(item)

    if method == "GET" and len(parts) == 3 and parts[0] == "packages" and parts[2] == "location":
        resp = pkg_table.get_item(Key={"package_id": parts[1]})
        item = resp.get("Item")
        if not item:
            return _err(404, "Package not found")
        return _ok({
            "package_id": item["package_id"],
            "current_location": item.get("current_location", ""),
            "status": item.get("status", ""),
        })

    if method == "PUT" and len(parts) == 3 and parts[0] == "packages" and parts[2] == "assign":
        resp = pkg_table.update_item(
            Key={"package_id": parts[1]},
            UpdateExpression="SET driver_id = :d, #st = :s, updated_at = :t",
            ConditionExpression=Attr("status").eq("created"),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":d": body.get("driver_id", ""),
                ":s": "assigned",
                ":t": int(time.time()),
            },
            ReturnValues="ALL_NEW",
        )
        return _ok(resp.get("Attributes", {}))

    if method == "POST" and len(parts) == 3 and parts[0] == "packages" and parts[2] == "events":
        pkg_id = parts[1]
        event_type = body.get("event_type", "")
        location = body.get("location", "")

        status_map = {
            "package_picked_up": "picked_up",
            "package_location_change": "in_transit",
            "package_delivered": "delivered",
        }
        new_status = status_map.get(event_type, "in_transit")

        now = int(time.time())
        event_entry = {"type": event_type, "location": location, "timestamp": now}

        pkgs = dynamodb.Table(PKG_TABLE)
        resp = pkgs.update_item(
            Key={"package_id": pkg_id},
            UpdateExpression=(
                "SET #st = :s, current_location = :loc, "
                "updated_at = :t ADD events :ev"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":s": new_status,
                ":loc": location,
                ":t": now,
                ":ev": [event_entry],
            },
            ReturnValues="ALL_NEW",
        )
        item = resp.get("Attributes", {})

        sqs.send_message(
            QueueUrl=EVENT_QUEUE_URL,
            MessageBody=json.dumps({
                "event_type": event_type,
                "package_id": pkg_id,
                "location": location,
                "customer_id": item.get("customer_id", ""),
                "driver_id": item.get("driver_id", ""),
                "timestamp": now,
            }),
        )
        return _ok({"package_id": pkg_id, "status": new_status, "event": event_type})

    if method == "GET" and len(parts) == 2 and parts[0] == "preferences":
        resp = pref_table.get_item(Key={"user_id": parts[1]})
        item = resp.get("Item", {})
        return _ok(item)

    if method == "PUT" and len(parts) == 2 and parts[0] == "preferences":
        user_id = parts[1]
        now = int(time.time())
        pref_table.put_item(Item={
            "user_id": user_id,
            "channels": body.get("channels", ["SMS"]),
            "phone_number": body.get("phone_number", ""),
            "email": body.get("email", ""),
            "updated_at": now,
        })
        if redis_client:
            redis_client.setex(
                f"pref:{user_id}", CACHE_TTL, json.dumps(body.get("channels", ["SMS"]))
            )
        return _ok({"user_id": user_id, "status": "updated"})

    return _err(404, "Not found")


def _handle_sqs(records: list):
    for record in records:
        try:
            body = json.loads(record["body"])
        except (json.JSONDecodeError, TypeError):
            continue

        event_type = body.get("event_type", "")
        if event_type in ("package_picked_up", "package_location_change"):
            customer_id = body.get("customer_id", "")
            driver_id = body.get("driver_id", "")
            pkg_id = body.get("package_id", "")
            location = body.get("location", "")

            if customer_id:
                _send_notification(customer_id, event_type, pkg_id, location)
            if driver_id:
                _send_notification(driver_id, event_type, pkg_id, location)

        else:
            print(f"Skipping notification for event: {event_type}")


def _ok(data: dict) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
    }


def _err(code: int, msg: str) -> dict:
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": msg}),
    }


def handler(event: dict, context) -> dict:
    if event.get("httpMethod"):
        return _handle_api(event)

    records = event.get("Records", [])
    if records and records[0].get("eventSource") == "aws:sqs":
        _handle_sqs(records)
        return {"statusCode": 200, "body": json.dumps("processed")}

    return _err(400, "Unknown event source")
