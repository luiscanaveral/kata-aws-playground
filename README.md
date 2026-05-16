# kata-aws-architecture

AWS Local Playground — emulating AWS services locally with [Floci](https://github.com/floci-io/floci).

## Quick Start

```bash
# Install dependencies
pip install -e .

# Start Floci + Cassandra
task up

# Run any scenario
task scenario:sqs-lambda
task scenario:image-upload
task scenario:ec2-wordpress
task scenario:iam-api
task scenario:cassandra-orders
task scenario:stepfunctions
task scenario:dynamodb-tickets

# Shut down
task down
```

## Scenarios

| Scenario | Task | Pattern |
|---|---|---|
| SQS → Lambda | `task scenario:sqs-lambda` | Event source mapping |
| Lambda → S3 | `task scenario:image-upload` | Image upload processing |
| EC2 WordPress | `task scenario:ec2-wordpress` | EC2 with UserData |
| IAM API Auth | `task scenario:iam-api` | SigV4 API authorization |
| Cassandra Orders | `task scenario:cassandra-orders` | NoSQL + SQS events |
| Step Functions | `task scenario:stepfunctions` | Parallel/sequential orchestration |
| DynamoDB Tickets | `task scenario:dynamodb-tickets` | Conditional writes + API |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and descriptions.

## Project Structure

```
├── docker-compose.yml      # Floci + Cassandra
├── pyproject.toml           # Python deps (boto3, pillow, cassandra-driver)
├── Taskfile.yml             # All scenarios as tasks
├── scenarios/               # Scenario Python modules
│   ├── common.py            # Shared boto3 helpers
│   ├── sqs_lambda/          # SQS → Lambda ESM
│   ├── image_upload/        # Lambda → S3
│   ├── ec2_wordpress/       # EC2 + UserData
│   ├── iam_api_auth/        # IAM + API Gateway
│   ├── cassandra_orders/    # Cassandra + SQS
│   ├── stepfunctions_orchestration/  # Step Functions
│   └── dynamodb_ticket_system/       # DynamoDB + API
├── lambda_functions/        # Hot-reload Lambda source copies
└── scripts/                 # init-aws.sh
```
