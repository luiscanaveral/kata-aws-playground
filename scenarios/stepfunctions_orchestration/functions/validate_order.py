import json


def handler(event, context):
    order_id = event.get("order_id", "unknown")
    customer = event.get("customer", {})
    items = event.get("items", [])

    errors = []
    if not customer.get("email"):
        errors.append("Missing customer email")
    if not items:
        errors.append("No items in order")
    if not order_id:
        errors.append("Missing order_id")
    total = sum(item.get("price", 0) * item.get("quantity", 0) for item in items)

    if errors:
        print(f"Validation FAILED for order {order_id}: {errors}")
        return {"status": "FAILED", "order_id": order_id, "errors": errors}

    print(f"Validation PASSED for order {order_id}: ${total} for {len(items)} items")
    return {
        "status": "PASSED",
        "order_id": order_id,
        "customer": customer,
        "items": items,
        "total": total,
        "validation_result": "Order is valid",
    }
