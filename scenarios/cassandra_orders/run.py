import json
import time
import uuid

from scenarios.common import account_id, aws_client


def create_cassandra_session():
    from cassandra.cluster import Cluster
    from cassandra.query import SimpleStatement

    cluster = Cluster(["localhost"])
    try:
        session = cluster.connect()
        session.set_keyspace("orders_app")
        return session
    except Exception:
        session = cluster.connect()
        session.execute(
            SimpleStatement(
                "CREATE KEYSPACE IF NOT EXISTS orders_app "
                "WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}"
            )
        )
        session.set_keyspace("orders_app")
        session.execute(
            SimpleStatement(
                "CREATE TABLE IF NOT EXISTS orders ("
                "  order_id text PRIMARY KEY,"
                "  customer text,"
                "  amount decimal,"
                "  items text,"
                "  status text,"
                "  created_at timestamp"
                ")"
            )
        )
        print("Created Cassandra keyspace and table")
        return session


def run():
    print("=" * 60)
    print("CASSANDRA ORDERS API - Local Playground")
    print("=" * 60)

    sqs = aws_client("sqs")
    aws_account_id = account_id()
    queue_url = f"http://localhost:4566/{aws_account_id}/order-notifications"

    session = create_cassandra_session()
    if not session:
        print("ERROR: Could not connect to Cassandra on localhost:9042")
        print("Make sure Cassandra is running: docker compose up -d")
        return

    print("\n1. CREATING ORDERS (direct Cassandra write)")
    print("-" * 40)
    orders_data = [
        {"order_id": f"ord-{uuid.uuid4().hex[:8]}", "customer": "Alice", "amount": 42.50, "items": ["widget", "gadget"]},
        {"order_id": f"ord-{uuid.uuid4().hex[:8]}", "customer": "Bob", "amount": 99.99, "items": ["premium-plan"]},
        {"order_id": f"ord-{uuid.uuid4().hex[:8]}", "customer": "Charlie", "amount": 15.00, "items": ["ebook"]},
    ]

    from cassandra.query import SimpleStatement

    for o in orders_data:
        items_json = json.dumps(o["items"])
        session.execute(
            SimpleStatement(
                "INSERT INTO orders (order_id, customer, amount, items, status, created_at) "
                "VALUES (%s, %s, %s, %s, %s, toTimestamp(now()))"
            ),
            (o["order_id"], o["customer"], o["amount"], items_json, "pending"),
        )
        print(f"  Created order: {o['order_id']} ({o['customer']}, ${o['amount']})")

    print("\n2. LISTING ORDERS (direct Cassandra read)")
    print("-" * 40)
    rows = session.execute(SimpleStatement("SELECT * FROM orders LIMIT 10"))
    for row in rows:
        print(f"  {row.order_id}: {row.customer} - ${row.amount} [{row.status}]")

    print("\n3. SENDING ORDER TO SQS (Lambda trigger)")
    print("-" * 40)
    for o in orders_data:
        resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(o))
        print(f"  Sent {o['order_id']} to SQS: MessageId={resp['MessageId']}")

    print("\n4. GETTING SINGLE ORDER BY ID")
    print("-" * 40)
    test_id = orders_data[0]["order_id"]
    rows = session.execute(
        SimpleStatement("SELECT * FROM orders WHERE order_id = %s"), (test_id,)
    )
    for row in rows:
        print(f"  Order: {row.order_id}")
        print(f"  Customer: {row.customer}")
        print(f"  Amount: ${row.amount}")
        print(f"  Items: {json.loads(row.items) if hasattr(row, 'items') else []}")
        print(f"  Status: {row.status}")
        print(f"  Created: {row.created_at}")

    print("\n5. SIMULATING ORDER STATUS UPDATE")
    print("-" * 40)
    session.execute(
        SimpleStatement("UPDATE orders SET status = %s WHERE order_id = %s"),
        ("shipped", test_id),
    )
    rows = session.execute(
        SimpleStatement("SELECT order_id, status FROM orders WHERE order_id = %s"),
        (test_id,),
    )
    for row in rows:
        print(f"  {row.order_id}: status updated to '{row.status}'")

    session.shutdown()

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("This scenario shows:")
    print("  - Apache Cassandra for order persistence")
    print("  - SQS message notifications for order events")
    print("  - Lambda function (cassandra-order-processor) triggered by SQS")
    print("  - Full CRUD operations on orders table")
    print()
    print("Architecture: Order API → Cassandra (storage) + SQS (event bus) → Lambda (processing)")


if __name__ == "__main__":
    run()
