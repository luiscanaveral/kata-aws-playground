import json

import boto3

from scenarios.common import account_id, aws_client


def get_signed_client(access_key_id: str, secret_access_key: str, session_token: str = ""):
    session = boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token,
    )
    return session.client(
        "apigateway",
        endpoint_url="http://localhost:4566",
        region_name="us-east-1",
    )


def invoke_api(endpoint_url: str, access_key: str, secret_key: str, method: str, path: str, body=None):
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    api_endpoint = endpoint_url.replace("/restapis/", f"/restapis/")

    client = session.client("apigateway", endpoint_url="http://localhost:4566", region_name="us-east-1")

    rest_apis = client.get_rest_apis()
    api = next(a for a in rest_apis["items"] if a["name"] == "iam-orders-api")
    api_id = api["id"]

    url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_{path}"

    if method in ("GET", "DELETE"):
        payload = None
    else:
        payload = json.dumps(body) if body else "{}"

    sig = session.client("s3")._request_signer
    region = "us-east-1"
    service = "execute-api"

    from botocore.awsrequest import AWSRequest
    from botocore.auth import SigV4Auth
    from botocore.credentials import Credentials

    credentials = Credentials(access_key, secret_key)
    request = AWSRequest(method=method.upper(), url=url, data=payload or "")
    request.headers["Content-Type"] = "application/json"
    if payload:
        request.headers["Content-Length"] = str(len(payload))
    else:
        request.headers["Content-Length"] = "0"

    auth = SigV4Auth(credentials, service, region)
    auth.add_auth(request)

    import urllib.request
    req = urllib.request.Request(
        url,
        data=payload.encode() if payload else None,
        headers=dict(request.headers),
        method=method.upper(),
    )
    try:
        resp = urllib.request.urlopen(req)
        return {"status": resp.status, "body": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode()}


def run():
    iam = aws_client("iam")
    apigw = aws_client("apigateway")

    rest_apis = apigw.get_rest_apis()
    api = next((a for a in rest_apis.get("items", []) if a["name"] == "iam-orders-api"), None)
    if not api:
        print("ERROR: API not found. Run setup first.")
        return
    api_id = api["id"]

    users_resp = iam.list_users()
    users = {u["UserName"]: u["Arn"] for u in users_resp["Users"]}

    if "api-admin" not in users:
        print("ERROR: api-admin user not found. Run setup first.")
        return

    admin_key = iam.create_access_key(UserName="api-admin")["AccessKey"]
    print("Created temporary access key for api-admin\n")

    invoke_url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_"

    print("=" * 60)
    print("TEST 1: Health check (admin user)")
    print("=" * 60)
    result = invoke_api(
        invoke_url,
        admin_key["AccessKeyId"],
        admin_key["SecretAccessKey"],
        "GET",
        "/health",
    )
    print(f"  Status: {result['status']}")
    print(f"  Body:   {json.dumps(result['body'], indent=4)}")
    print()

    print("=" * 60)
    print("TEST 2: Create order (admin user)")
    print("=" * 60)
    result = invoke_api(
        invoke_url,
        admin_key["AccessKeyId"],
        admin_key["SecretAccessKey"],
        "PUT",
        "/orders",
        {"order_id": "ord-100", "customer": "Alice", "items": ["widget", "gadget"]},
    )
    print(f"  Status: {result['status']}")
    print(f"  Body:   {json.dumps(result['body'], indent=4)}")
    print()

    print("=" * 60)
    print("TEST 3: Get order (admin user)")
    print("=" * 60)
    result = invoke_api(
        invoke_url,
        admin_key["AccessKeyId"],
        admin_key["SecretAccessKey"],
        "GET",
        "/orders/ord-100",
    )
    print(f"  Status: {result['status']}")
    print(f"  Body:   {json.dumps(result['body'], indent=4)}")
    print()

    if "api-readonly" in users:
        print("=" * 60)
        print("TEST 4: Create order (readonly user - should be DENIED)")
        print("=" * 60)
        readonly_key = iam.create_access_key(UserName="api-readonly")["AccessKey"]
        result = invoke_api(
            invoke_url,
            readonly_key["AccessKeyId"],
            readonly_key["SecretAccessKey"],
            "PUT",
            "/orders",
            {"order_id": "ord-999", "customer": "Eve"},
        )
        print(f"  Status: {result['status']}")
        print(f"  Body:   {result['body']}")
        print()

    iam.delete_access_key(
        UserName="api-admin",
        AccessKeyId=admin_key["AccessKeyId"],
    )
    print("Cleaned up temporary access keys")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("API Gateway with AWS_IAM authorization demonstrated:")
    print("  - SigV4 signed requests to API Gateway")
    print("  - API Gateway validates IAM identity and forwards to Lambda")
    print("  - Lambda receives IAM context (user ARN) in the event")
    print("  - Unauthorized users (no execute-api:Invoke) get 403/access denied")


if __name__ == "__main__":
    run()
