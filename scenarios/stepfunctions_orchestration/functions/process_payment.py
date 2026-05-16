import json
import random


def handler(event, context):
    order_id = event.get("order_id", "unknown")
    total = event.get("total", 0)
    customer = event.get("customer", {})
    inventory_status = event.get("inventory_status", "UNKNOWN")

    if inventory_status == "OUT_OF_STOCK":
        print(f"Payment SKIPPED for order {order_id}: items out of stock")
        return {
            **event,
            "payment_status": "SKIPPED",
            "payment_message": "Cannot process payment: items out of stock",
        }

    payment_success = random.random() > 0.1
    transaction_id = f"txn-{order_id}-{random.randint(10000, 99999)}"

    if payment_success:
        print(f"Payment APPROVED for order {order_id}: ${total} (txn: {transaction_id})")
        return {
            **event,
            "payment_status": "APPROVED",
            "transaction_id": transaction_id,
            "amount_charged": total,
        }

    print(f"Payment DECLINED for order {order_id}: ${total}")
    return {
        **event,
        "payment_status": "DECLINED",
        "transaction_id": None,
        "amount_charged": 0,
    }
