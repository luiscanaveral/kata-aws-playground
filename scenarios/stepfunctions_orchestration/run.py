import json
import time

from scenarios.common import aws_client


def run():
    sfn = aws_client("stepfunctions")

    state_machines = sfn.list_state_machines()
    sm = next(
        (m for m in state_machines.get("stateMachines", []) if m["name"] == "order-processing-workflow"),
        None,
    )
    if not sm:
        print("ERROR: State machine not found. Run setup first.")
        return

    sm_arn = sm["stateMachineArn"]
    print(f"State machine: {sm_arn}")
    print()

    test_orders = [
        {
            "order_id": "ORD-001",
            "customer": {"name": "Alice", "email": "alice@example.com"},
            "items": [
                {"sku": "WIDGET-A", "name": "Super Widget", "price": 29.99, "quantity": 2},
                {"sku": "GADGET-B", "name": "Mega Gadget", "price": 49.99, "quantity": 1},
            ],
        },
        {
            "order_id": "ORD-002",
            "customer": {"name": "Bob", "email": "bob@example.com"},
            "items": [
                {"sku": "WIDGET-A", "name": "Super Widget", "price": 29.99, "quantity": 1},
            ],
        },
    ]

    for order in test_orders:
        print("=" * 70)
        print(f"EXECUTING WORKFLOW FOR: {order['order_id']}")
        print("=" * 70)

        exec_resp = sfn.start_execution(
            stateMachineArn=sm_arn,
            name=order["order_id"],
            input=json.dumps(order),
        )
        exec_arn = exec_resp["executionArn"]
        print(f"  Execution started: {exec_arn}")

        for _ in range(20):
            desc = sfn.describe_execution(executionArn=exec_arn)
            status = desc["status"]
            if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
                break
            time.sleep(1)
        else:
            print("  WARNING: Execution did not complete within 20s")

        print(f"  Status: {status}")

        history = sfn.get_execution_history(executionArn=exec_arn)
        events = history.get("events", [])

        print(f"  Events ({len(events)} total):")
        state_transitions = [
            e for e in events
            if e.get("type") in ("TaskStateEntered", "TaskStateExited", "ParallelStateEntered", "ParallelStateExited", "ExecutionSucceeded", "ExecutionFailed")
        ]
        for e in state_transitions:
            ts = e.get("timestamp", "")
            etype = e.get("type", "")
            details = e.get("stateEnteredEventDetails") or e.get("stateExitedEventDetails") or {}
            name = details.get("name", "")
            output = details.get("output", "")
            result = ""
            if output:
                try:
                    parsed = json.loads(output)
                    if isinstance(parsed, dict):
                        result = parsed.get("final_status", parsed.get("payment_status", parsed.get("inventory_status", "")))
                except (json.JSONDecodeError, TypeError):
                    pass
            print(f"    [{ts[-12:]}] {etype:<30} {name:<25} {result}")

        if status == "SUCCEEDED":
            output = sfn.describe_execution(executionArn=exec_arn).get("output", "{}")
            try:
                parsed = json.loads(output)
                final_status = parsed.get("final_status", "UNKNOWN")
                print(f"  >>> FINAL STATUS: {final_status}")
            except json.JSONDecodeError:
                print(f"  Output: {output[:200]}")
        print()

    print("=" * 70)
    print("STEP FUNCTIONS ORCHESTRATION DEMONSTRATED")
    print("=" * 70)
    print("  Sequential: ValidateOrder -> [Parallel] -> EvaluateResults -> SendConfirmation")
    print("  Parallel:   CheckInventory + ProcessPayment run simultaneously")
    print("  Choice:     EvaluateResults routes to Confirmation or Failure")
    print()


if __name__ == "__main__":
    run()
