import json
import time

from scenarios.common import account_id, aws_client


def run():
    aws_account_id = account_id()

    queue_url = f"http://localhost:4566/{aws_account_id}/order-events"

    print("Sending order events to SQS...")
    sqs = aws_client("sqs")
    orders = [
        {"order_id": "ord-001", "customer": "Alice", "amount": 42.50},
        {"order_id": "ord-002", "customer": "Bob", "amount": 99.99},
        {"order_id": "ord-003", "customer": "Charlie", "amount": 15.00},
    ]

    for order in orders:
        resp = sqs.send_message(
            QueueUrl=queue_url, MessageBody=json.dumps(order)
        )
        print(f"  Sent {order['order_id']}: MessageId={resp['MessageId']}")

    print("\nMessages sent. Lambda (sqs-order-processor) will be triggered via event source mapping.")
    print("Check Lambda logs via CloudWatch or inspect SQS queue for processed messages.\n")

    print("Waiting 5s for Lambda to consume messages...")
    time.sleep(5)

    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["ApproximateNumberOfMessages"]
    )
    remaining = attrs["Attributes"].get("ApproximateNumberOfMessages", "unknown")
    print(f"Messages remaining in queue: {remaining}")

    if remaining == "0":
        print("SUCCESS: All messages were consumed by Lambda.")
    else:
        print(f"NOTE: {remaining} messages still in queue. Lambda may still be processing.")


if __name__ == "__main__":
    run()
