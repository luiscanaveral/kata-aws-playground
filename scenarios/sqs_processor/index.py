import json


def handler(event, context):
    for record in event.get("Records", []):
        body = record.get("body", "")
        message_id = record.get("messageId", "")
        print(f"SQS message received: {body}")
        print(f"MessageId: {message_id}")

    return {"statusCode": 200, "body": json.dumps("processed")}
