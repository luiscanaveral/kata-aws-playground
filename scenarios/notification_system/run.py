import json
import time
import uuid

from scenarios.common import account_id, aws_client


def _api_get(api_id: str, path: str):
    import urllib.request

    url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_{path}"
    resp = urllib.request.urlopen(url)
    return resp.status, json.loads(resp.read().decode())


def _api_post(api_id: str, path: str, body: dict):
    import urllib.request

    url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return resp.status, json.loads(resp.read().decode())


def _api_put(api_id: str, path: str, body: dict):
    import urllib.request

    url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return resp.status, json.loads(resp.read().decode())


def run():
    apigw = aws_client("apigateway")
    dynamodb = aws_client("dynamodb")
    s3 = aws_client("s3")

    rest_apis = apigw.get_rest_apis()
    api = next(
        (a for a in rest_apis.get("items", []) if a["name"] == "notification-system-api"),
        None,
    )
    if not api:
        print("ERROR: Notification System API not found. Deploy infrastructure first.")
        return
    api_id = api["id"]

    CUSTOMER = "cust-alice"
    DRIVER = "driver-bob"
    CUSTOMER_PHONE = "+15551234567"
    CUSTOMER_EMAIL = "alice@example.com"

    print("=" * 70)
    print("NOTIFICATION SYSTEM DEMO")
    print("=" * 70)

    print("\n1. SET NOTIFICATION PREFERENCES")
    print("-" * 50)
    status, data = _api_put(
        api_id, f"/preferences/{CUSTOMER}",
        {
            "channels": ["SMS", "EMAIL"],
            "phone_number": CUSTOMER_PHONE,
            "email": CUSTOMER_EMAIL,
        },
    )
    print(f"  Customer pref set: {data}")

    status, data = _api_put(
        api_id, f"/preferences/{DRIVER}",
        {
            "channels": ["EMAIL"],
            "phone_number": "",
            "email": "bob@driver.com",
        },
    )
    print(f"  Driver pref set: {data}")

    print("\n2. CREATE A PACKAGE")
    print("-" * 50)
    status, data = _api_post(
        api_id, "/packages",
        {
            "customer_id": CUSTOMER,
            "address_from": "123 Main St, Springfield",
            "address_to": "456 Oak Ave, Shelbyville",
        },
    )
    pkg_id = data.get("package_id")
    print(f"  Created: {data}")

    print("\n3. GET PACKAGE DETAILS")
    print("-" * 50)
    status, data = _api_get(api_id, f"/packages/{pkg_id}")
    print(f"  Status: {data['status']}")
    print(f"  From:   {data['address_from']}")
    print(f"  To:     {data['address_to']}")

    print("\n4. ASSIGN DRIVER")
    print("-" * 50)
    status, data = _api_put(
        api_id, f"/packages/{pkg_id}/assign",
        {"driver_id": DRIVER},
    )
    print(f"  Assigned driver: {data}")

    print("\n5. DRIVER EVENTS (triggering notifications)")
    print("-" * 50)

    for event_type, location in [
        ("package_picked_up", "123 Main St, Springfield"),
        ("package_location_change", "Broadway Ave, Mile 5"),
        ("package_location_change", "Highway 42, Mile 12"),
        ("package_delivered", "456 Oak Ave, Shelbyville"),
    ]:
        status, data = _api_post(
            api_id, f"/packages/{pkg_id}/events",
            {"event_type": event_type, "location": location},
        )
        print(f"  {event_type}: {location}")
        if event_type in ("package_picked_up", "package_location_change"):
            print(f"    → Notification dispatch triggered")
        time.sleep(0.5)

    print("\n6. TRACK PACKAGE LOCATION")
    print("-" * 50)
    status, data = _api_get(api_id, f"/packages/{pkg_id}/location")
    print(f"  Current location: {data['current_location']}")
    print(f"  Status:           {data['status']}")

    print("\n7. GET NOTIFICATION PREFERENCES (cache warm)")
    print("-" * 50)
    status, data = _api_get(api_id, f"/preferences/{CUSTOMER}")
    print(f"  Preferences: {data}")
    print(f"  (Data now cached in Redis for {300}s)")

    print("\n8. PACKAGE EVENT HISTORY")
    print("-" * 50)
    status, data = _api_get(api_id, f"/packages/{pkg_id}")
    print(f"  Package:  {data['package_id']}")
    print(f"  Status:   {data['status']}")
    print(f"  Customer: {data['customer_id']}")
    print(f"  Driver:   {data['driver_id']}")
    print(f"  Events:   {len(data.get('events', []))} recorded")
    for ev in data.get("events", []):
        print(f"    · {ev['type']} @ {ev['location']}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("  - Package lifecycle: created → assigned → picked_up → in_transit → delivered")
    print("  - Driver events trigger async notifications via SQS")
    print("  - Notification preference cached in Redis (300s TTL)")
    print("  - Notification dispatched via SNS (SMS, Email, or simulated)")
    print()
    print("Architecture:")
    print("  API Gateway → Lambda → DynamoDB (packages + preferences)")
    print("                        → SQS → Lambda (notification dispatch)")
    print("                        → Redis (preference cache)")
    print("                        → SNS (SMS/Email notifications)")


if __name__ == "__main__":
    run()
