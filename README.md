# kata-aws-architecture

AWS Local Playground — emulating AWS services locally with [Floci](https://github.com/floci-io/floci).

Infrastructure is defined as [AWS CDK](https://aws.amazon.com/cdk/) stacks and deployed to Floci via CloudFormation.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 18+ (for CDK CLI — `npm install -g aws-cdk`)

## Quick Start

```bash
# Install Python dependencies
uv sync   # or: pip install -e .

# Start Floci + Cassandra
task up

# Deploy infrastructure for a scenario, then run it
task sqs-lambda:infrastructure   # deploy SQS queue, Lambda, ESM
task sqs-lambda:run              # send messages to trigger the flow

# Or deploy everything at once
task init

# Shut down
task down
```

## Scenarios

Each scenario has two phases — **infrastructure** (CDK stack) and **run** (code execution):

| Scenario | Infra task | Run task | Pattern |
|---|---|---|---|
| SQS → Lambda | `task sqs-lambda:infrastructure` | `task sqs-lambda:run` | Event source mapping |
| Lambda → S3 | `task image-upload:infrastructure` | `task image-upload:run` | Image upload processing |
| EC2 WordPress | `task ec2-wordpress:infrastructure` | `task ec2-wordpress:run` | EC2 with UserData |
| IAM API Auth | `task iam-api:infrastructure` | `task iam-api:run` | SigV4 API authorization |
| Cassandra Orders | `task cassandra-orders:infrastructure` | `task cassandra-orders:run` | NoSQL + SQS events |
| Step Functions | `task stepfunctions:infrastructure` | `task stepfunctions:run` | Parallel/sequential orchestration |
| DynamoDB Tickets | `task dynamodb-tickets:infrastructure` | `task dynamodb-tickets:run` | Conditional writes + API |
| Feature Flags | `task feature-flags:infrastructure` | `task feature-flags:run` | AppConfig feature flags with live UI dashboard |
| SNS Fanout Feed | `task sns-fanout:infrastructure` | `task sns-fanout:run` | Pub/sub with SNS → SQS → Lambda + frontend |
| Notification System | `task notification-system:infrastructure` | `task notification-system:run` | Package tracking + SNS notifications |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and descriptions.

## Project Structure

```
├── docker-compose.yml          # Floci + Cassandra
├── pyproject.toml              # Python deps (boto3, pillow, cdk, etc.)
├── Taskfile.yml                # All scenarios as tasks
├── infrastructure/             # AWS CDK infrastructure
│   ├── app.py                  # CDK app entry point
│   ├── cdk.json                # CDK config
│   ├── deploy.py               # Synth + deploy to Floci via CF
│   └── stacks/                 # CDK stacks (one per scenario)
├── scenarios/                  # Code artifacts (Lambda functions, run scripts)
│   ├── common.py               # Shared boto3 helpers
│   ├── sqs_lambda/             # SQS → Lambda ESM
│   ├── image_upload/           # Lambda → S3
│   ├── ec2_wordpress/          # EC2 + UserData
│   ├── iam_api_auth/           # IAM + API Gateway
│   ├── cassandra_orders/       # Cassandra + SQS
│   ├── stepfunctions_orchestration/  # Step Functions
│       ├── dynamodb_ticket_system/       # DynamoDB + API
    ├── notification_system/          # Package tracking + SNS notifications
    ├── sns_fanout/                   # SNS fanout + social feed
    └── feature_flags/                # AppConfig feature flags
└── ARCHITECTURE.md             # Architecture diagrams
```

## How it works

1. **`{scenario}:infrastructure`** — runs `infrastructure/deploy.py`, which synthesizes the CDK stack into a CloudFormation template, uploads Lambda code to Floci S3, and deploys the stack to Floci.
2. **`{scenario}:run`** — executes the scenario's `run.py`, which uses boto3 to interact with the now-provisioned resources on Floci.
