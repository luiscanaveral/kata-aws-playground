import json
from datetime import datetime


def handler(event, context):
    order_id = event.get("order_id", "unknown")
    customer = event.get("customer", {})
    payment_status = event.get("payment_status", "UNKNOWN")
    total = event.get("total", 0)
    transaction_id = event.get("transaction_id")
    inventory_status = event.get("inventory_status", "UNKNOWN")

    email = customer.get("email", "unknown@example.com")

    if payment_status == "APPROVED" and inventory_status == "IN_STOCK":
        message = (
            f"Order {order_id} confirmed!\n"
            f"Total: ${total}\n"
            f"Transaction: {transaction_id}\n"
            f"Thank you for your purchase."
        )
        print(f"CONFIRMATION sent to {email}: {message}")
        return {
            **event,
            "final_status": "CONFIRMED",
            "notification_sent": True,
            "confirmation_message": message,
            "processed_at": datetime.utcnow().isoformat(),
        }

    if payment_status == "DECLINED":
        message = f"Order {order_id}: Payment declined. Please try a different payment method."
    elif inventory_status == "OUT_OF_STOCK":
        message = f"Order {order_id}: Some items are out of stock."
    else:
        message = f"Order {order_id}: Could not be processed."

    print(f"FAILURE notification sent to {email}: {message}")
    return {
        **event,
        "final_status": "FAILED",
        "notification_sent": True,
        "failure_message": message,
        "processed_at": datetime.utcnow().isoformat(),
    }
