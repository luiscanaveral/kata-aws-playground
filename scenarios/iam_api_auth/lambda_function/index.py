import json


def handler(event, context):
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    body = event.get("body", "{}")
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("iam", {})
    )
    user_arn = claims.get("userArn", "unknown")
    user_name = user_arn.split("/")[-1] if "/" in user_arn else user_arn

    if http_method == "GET" and path == "/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "ok", "service": "orders-api"}),
        }

    if http_method == "PUT" and path == "/orders":
        order = json.loads(body)
        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Order created",
                "order": order,
                "created_by": user_name,
            }),
        }

    if http_method == "GET" and path.startswith("/orders/"):
        order_id = path.split("/")[-1]
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "order_id": order_id,
                "status": "pending",
                "requested_by": user_name,
            }),
        }

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not found"}),
    }
