import json
import time

from scenarios.common import account_id, aws_client


def invoke_api(api_id: str, method: str, path: str, body: dict = None):
    import urllib.request

    url = f"http://localhost:4566/restapis/{api_id}/v1/_user_request_{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def run():
    apigw = aws_client("apigateway")

    rest_apis = apigw.get_rest_apis()
    api = next(
        (a for a in rest_apis.get("items", []) if a["name"] == "ticket-system-api"),
        None,
    )
    if not api:
        print("ERROR: Ticket system API not found. Run setup first.")
        return
    api_id = api["id"]

    print("=" * 70)
    print("TICKET SELLING SYSTEM")
    print("=" * 70)

    print("\n1. LIST AVAILABLE TICKETS")
    print("-" * 40)
    status, data = invoke_api(api_id, "GET", "/tickets")
    print(f"  Status: {status}")
    if data.get("tickets"):
        for t in data["tickets"]:
            print(f"    {t['ticket_id']}: {t['event_name']} - {t['section']} {t['seat']} (${t['price']})")
    else:
        print("  No tickets available")

    print("\n2. GET TICKET DETAILS")
    print("-" * 40)
    status, data = invoke_api(api_id, "GET", "/tickets/TICKET-001")
    if status == 200:
        t = data["ticket"]
        print(f"  Ticket:     {t['ticket_id']}")
        print(f"  Event:      {t['event_name']}")
        print(f"  Seat:       {t['section']} - {t['seat']}")
        print(f"  Price:      ${t['price']}")
        print(f"  Status:     {t['status']}")
    else:
        print(f"  Error: {data}")

    print("\n3. RESERVE A TICKET (conditional write)")
    print("-" * 40)
    status, data = invoke_api(api_id, "PUT", "/tickets/TICKET-001/reserve", {"email": "alice@example.com"})
    print(f"  Status: {status}")
    print(f"  Result: {json.dumps(data, indent=4)}")

    print("\n4. TRY TO RESERVE SAME TICKET AGAIN (should fail)")
    print("-" * 40)
    status, data = invoke_api(api_id, "PUT", "/tickets/TICKET-001/reserve", {"email": "bob@example.com"})
    print(f"  Status: {status}")
    print(f"  Result: {json.dumps(data, indent=4)}")

    print("\n5. PURCHASE THE RESERVED TICKET")
    print("-" * 40)
    status, data = invoke_api(api_id, "PUT", "/tickets/TICKET-001/purchase")
    print(f"  Status: {status}")
    print(f"  Result: {json.dumps(data, indent=4)}")

    print("\n6. TRY TO PURCHASE SAME TICKET AGAIN (should fail)")
    print("-" * 40)
    status, data = invoke_api(api_id, "PUT", "/tickets/TICKET-001/purchase")
    print(f"  Status: {status}")
    print(f"  Result: {json.dumps(data, indent=4)}")

    print("\n7. RESERVE AND RELEASE A TICKET")
    print("-" * 40)
    status, data = invoke_api(api_id, "PUT", "/tickets/TICKET-002/reserve", {"email": "carol@example.com"})
    print(f"  Reserve: {data}")

    status, data = invoke_api(api_id, "PUT", "/tickets/TICKET-002/release")
    print(f"  Release: {json.dumps(data, indent=4)}")

    status, data = invoke_api(api_id, "GET", "/tickets/TICKET-002")
    if status == 200:
        print(f"  Ticket {data['ticket']['ticket_id']} status: {data['ticket']['status']} (back to available)")

    print("\n8. FINAL INVENTORY CHECK")
    print("-" * 40)
    status, data = invoke_api(api_id, "GET", "/tickets")
    print(f"  Available tickets: {data.get('count', 0)}")
    for t in data.get("tickets", []):
        print(f"    {t['ticket_id']}: {t['event_name']} - {t['section']} {t['seat']}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("  - DynamoDB conditional writes prevent double-booking")
    print("  - Reservation with 15-min TTL auto-expiry")
    print("  - Atomic state transitions: available -> reserved -> purchased")
    print("  - Release flow returns ticket to available pool")
    print()


if __name__ == "__main__":
    run()
