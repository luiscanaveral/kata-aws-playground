import json
import random


def handler(event, context):
    items = event.get("items", [])
    order_id = event.get("order_id", "unknown")

    inventory_results = []
    all_available = True
    for item in items:
        sku = item.get("sku", item.get("name", "unknown"))
        qty = item.get("quantity", 1)
        available = random.randint(0, qty + 5) >= qty
        inventory_results.append({
            "sku": sku,
            "requested": qty,
            "available": available,
            "stock_level": max(0, random.randint(0, 20)),
        })
        if not available:
            all_available = False

    if all_available:
        print(f"Inventory CHECK PASSED for order {order_id}")
        return {
            **event,
            "inventory_status": "IN_STOCK",
            "inventory_results": inventory_results,
        }

    print(f"Inventory CHECK FAILED for order {order_id}: some items out of stock")
    return {
        **event,
        "inventory_status": "OUT_OF_STOCK",
        "inventory_results": inventory_results,
    }
