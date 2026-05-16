import json
import os
import uuid

from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement

CASSANDRA_HOST = os.environ.get("CASSANDRA_HOST", "cassandra")
CASSANDRA_KEYSPACE = os.environ.get("CASSANDRA_KEYSPACE", "orders_app")
ORDER_QUEUE_URL = os.environ.get("ORDER_QUEUE_URL", "")


def get_session():
    cluster = Cluster([CASSANDRA_HOST])
    return cluster.connect(CASSANDRA_KEYSPACE)


def _create_order(session, order_data):
    order_id = order_data.get("order_id", str(uuid.uuid4()))
    customer = order_data.get("customer", "unknown")
    amount = order_data.get("amount", 0.0)
    items = json.dumps(order_data.get("items", []))

    session.execute(
        SimpleStatement(
            "INSERT INTO orders (order_id, customer, amount, items, status, created_at) "
            "VALUES (%s, %s, %s, %s, %s, toTimestamp(now()))"
        ),
        (order_id, customer, amount, items, "pending"),
    )
    return order_id


def _get_order(session, order_id):
    rows = session.execute(
        SimpleStatement("SELECT * FROM orders WHERE order_id = %s"), (order_id,)
    )
    for row in rows:
        return {
            "order_id": row.order_id,
            "customer": row.customer,
            "amount": row.amount,
            "items": json.loads(row.items) if hasattr(row, "items") else [],
            "status": row.status,
        }
    return None


def _list_orders(session, limit=20):
    rows = session.execute(
        SimpleStatement(f"SELECT * FROM orders LIMIT {limit}")
    )
    orders = []
    for row in rows:
        orders.append({
            "order_id": row.order_id,
            "customer": row.customer,
            "status": row.status,
        })
    return orders


def handler(event, context):
    records = event.get("Records", [])
    if records:
        for record in records:
            body = json.loads(record["body"])
            try:
                session = get_session()
                order_id = _create_order(session, body)
                session.shutdown()
                print(f"Created order {order_id} from SQS event")
            except Exception as e:
                print(f"Error processing SQS message: {e}")
        return {"statusCode": 200, "body": json.dumps("processed")}

    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    body = event.get("body", "{}")

    try:
        session = get_session()

        if http_method == "PUT" and path == "/orders":
            order_data = json.loads(body)
            order_id = _create_order(session, order_data)
            result = {"order_id": order_id, "status": "created"}

        elif http_method == "GET" and path.startswith("/orders/"):
            order_id = path.split("/")[-1]
            order = _get_order(session, order_id)
            result = order if order else {"error": "Order not found"}

        elif http_method == "GET" and path == "/orders":
            orders = _list_orders(session)
            result = {"orders": orders, "count": len(orders)}

        else:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Not found"}),
            }

        session.shutdown()
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
