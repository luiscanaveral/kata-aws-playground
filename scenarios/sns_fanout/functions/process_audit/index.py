import json


def handler(event, context):
    for record in event.get("Records", []):
        try:
            sns_msg = json.loads(record["body"])
        except (json.JSONDecodeError, TypeError):
            continue

        topic_arn = sns_msg.get("TopicArn", "")
        message_id = sns_msg.get("MessageId", "")
        message_str = sns_msg.get("Message", "{}")
        try:
            post = json.loads(message_str)
        except (json.JSONDecodeError, TypeError):
            post = {}

        print(f"[AUDIT] Topic={topic_arn} MessageId={message_id}")
        print(f"[AUDIT] Post={post.get('post_id', '?')} user={post.get('username', '?')}")
        print(f"[AUDIT] Content={post.get('content', '?')[:60]}...")

    return {"statusCode": 200, "body": json.dumps("audited")}
