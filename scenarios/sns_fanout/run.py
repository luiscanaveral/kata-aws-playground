import json
import random
import time
import uuid

from scenarios.common import aws_client


USERS = [
    "alice", "bob", "charlie", "diana", "eve",
    "frank", "grace", "henry", "isabel", "jack",
]

TOPICS = [
    "Just had the best coffee this morning!",
    "Working on a new side project...",
    "Beautiful sunset today!",
    "Anyone else love Python?",
    "Reading a great book on distributed systems.",
    "TIL about SNS fanout patterns.",
    "Cats are the best. That is all.",
    "Deployed to production. No bugs. Unbelievable.",
    "Hot take: tabs > spaces.",
    "Finally understanding Kafka. Mind blown.",
    "Who else is at the conference?",
    "Just shipped a new feature!",
    "Any recommendations for good podcasts?",
    "The weather is perfect today.",
    "Code review complete. Merging to main!",
]

ANALYTICS_HEADERS = [
    "~", "~", "~", "~", "~",
    "> feed-processor saves to DynamoDB",
    "> audit-logger prints to CloudWatch",
    "> both subscribed to the same SNS Topic",
    "~", "~", "~", "~", "~",
]


def random_post() -> dict:
    return {
        "post_id": str(uuid.uuid4()),
        "username": random.choice(USERS),
        "content": random.choice(TOPICS),
        "created_at": int(time.time()),
    }


def run():
    sns = aws_client("sns")

    topics_resp = sns.list_topics()
    topic = next(
        (t for t in topics_resp.get("Topics", [])
         if t["TopicArn"].endswith(":social-feed-topic")),
        None,
    )
    if not topic:
        print("ERROR: SNS topic not found. Deploy infrastructure first.")
        return

    topic_arn = topic["TopicArn"]
    api_id = _find_api_id()

    base_url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_"
    frontend_url = base_url + "/"

    print("=" * 60)
    print("SNS FANOUT — SOCIAL FEED")
    print("=" * 60)
    print()
    print(f"  Frontend: {frontend_url}")
    print()
    print("  Publishing a random post every 15 seconds.")
    print("  Press Ctrl+C to stop.")
    print()

    count = 0
    try:
        while True:
            post = random_post()
            sns.publish(
                TopicArn=topic_arn,
                Message=json.dumps(post),
                Subject=f"New post by {post['username']}",
                MessageAttributes={
                    "source": {
                        "DataType": "String",
                        "StringValue": "social-feed-publisher",
                    },
                },
            )

            count += 1
            print(f"  [{count:>3}] @{post['username']}: {post['content'][:50]}...")

            if count < len(ANALYTICS_HEADERS):
                h = ANALYTICS_HEADERS[count]
                if h != "~":
                    print(f"         {h}")

            if count == 1:
                print()
                print("  SNS is fanning out to:")
                print("    1. feed-queue  → feed-processor Lambda → DynamoDB")
                print("    2. audit-queue → audit-logger Lambda → CloudWatch Logs")
                print()

            time.sleep(15)

    except KeyboardInterrupt:
        print()
        print(f"  Published {count} posts total.")
        print(f"  Open {frontend_url} to view the feed.")
        print("  Done.")


def _find_api_id() -> str:
    apigw = aws_client("apigateway")
    apis = apigw.get_rest_apis()
    api = next(
        (a for a in apis.get("items", []) if a["name"] == "social-feed-api"),
        None,
    )
    return api["id"] if api else ""


if __name__ == "__main__":
    run()
