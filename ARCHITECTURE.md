# Architecture

All scenarios run against [Floci](https://github.com/floci-io/floci), an open-source AWS emulator available at `http://localhost:4566`. Services that require real container runtimes (Lambda, EC2) use Docker under the hood.

---

## 1. SQS → Lambda (Event Source Mapping)

```mermaid
flowchart LR
    C[Client / Producer] -->|SendMessage| Q[SQS Queue<br/>order-events]
    Q -->|Poll + Batch| ESM[Event Source Mapping]
    ESM -->|Invoke| L[Lambda Function<br/>sqs-order-processor]
    L -->|"console.log"| CW[CloudWatch Logs]
```

**Flow:** Messages sent to the SQS queue are automatically polled by Floci's Lambda event source mapping and delivered to the Lambda function in batches.

**Key concepts:** Event source mapping, batch processing, SQS visibility timeout, Lambda execution context.

**Run:** `task scenario:sqs-lambda`

---

## 2. Lambda Image Upload → S3

```mermaid
flowchart LR
    C[Client] -->|Invoke| L[Lambda Function<br/>image-upload-processor]
    L -->|base64 decode| B[Image Buffer]
    B -->|PutObject| S3[S3 Bucket<br/>images]
    S3 -->|Response| C
```

**Flow:** The Lambda function receives a base64-encoded image via direct invocation, decodes it, and stores it in an S3 bucket using `PutObject`.

**Key concepts:** Lambda invocation (RequestResponse), base64 encoding, S3 PutObject, environment variables.

**Run:** `task scenario:image-upload`

---

## 3. EC2 with WordPress

```mermaid
flowchart LR
    subgraph AWS
        V[VPC 10.0.0.0/16]
        subgraph SG[Security Group]
            EC2[EC2 Instance<br/>wordpress-server]
        end
        IGW[Internet Gateway]
        RT[Route Table<br/>0.0.0.0/0 → IGW]
    end
    USER[User] -->|HTTP :80| EC2
    USER -->|SSH :22| EC2
    EC2 -->|UserData| WP[Apache + PHP<br/>WordPress Landing]
    V --> IGW
    IGW --> RT
```

**Flow:** Floci EC2 launches a real Docker container with Apache + PHP via UserData. A WordPress-style landing page is served on port 80. SSH access is available via the generated key pair.

**Key concepts:** VPC/subnet/IGW/route table, Security Group, Key Pair, RunInstances, UserData, instance profile.

**Run:** `task scenario:ec2-wordpress`

---

## 4. IAM API Authorization

```mermaid
flowchart LR
    subgraph Users
        A[api-admin<br/>execute-api:Invoke ✓]
        R[api-readonly<br/>execute-api:Invoke ✗]
    end
    A -->|SigV4 Signed Request| GW[API Gateway<br/>AWS_IAM Auth]
    R -->|SigV4 Signed Request| GW
    GW -->|IAM Context| L[Lambda Function<br/>iam-orders-handler]
    L -->|Response| A
    GW -->|403 Denied| R
```

**Flow:** API Gateway is configured with `AWS_IAM` authorization. Requests must be SigV4-signed with valid IAM credentials. The `api-admin` user (with `execute-api:Invoke` permission) succeeds; the `api-readonly` user (no permission) receives 403.

**Key concepts:** IAM users, API Gateway AWS_IAM auth type, SigV4 request signing, Lambda proxy integration, IAM policy evaluation.

**Run:** `task scenario:iam-api`

---

## 5. Cassandra Orders API

```mermaid
flowchart LR
    C[Client] -->|CRUD| CS[Cassandra 4.1<br/>:9042]
    C -->|SendMessage| Q[SQS Queue<br/>order-notifications]
    Q -->|ESM| L[Lambda<br/>cassandra-order-processor]
    L --> CS
    subgraph docker-compose
        F[Floci :4566]
        CS
    end
```

**Flow:** Orders are stored in Cassandra (running as a sidecar container) with CRUD operations. Each order creation also sends a message to SQS, which triggers a Lambda function that reads from Cassandra for processing.

**Key concepts:** Apache Cassandra, CQL keyspace/table design, SQS event bus, Lambda + Cassandra integration, docker-compose sidecar pattern.

**Run:** `task scenario:cassandra-orders`

---

## 6. Step Functions Orchestration

```mermaid
flowchart TD
    START --> V[ValidateOrder<br/>Lambda]
    V --> PAR[Parallel]
    
    subgraph PAR [Parallel Branch]
        direction TB
        CI[CheckInventory<br/>Lambda]
        PP[ProcessPayment<br/>Lambda]
    end
    
    PAR --> EV{EvaluateResults<br/>Choice State}
    EV -->|inventory = OUT_OF_STOCK| FAIL[SendFailureNotification]
    EV -->|payment = DECLINED| FAIL
    EV -->|Both OK| SEND[SendConfirmation<br/>Lambda]
    
    FAIL --> END
    SEND --> END
```

**Flow:** Step Functions state machine orchestrates 4 Lambda functions. `ValidateOrder` runs first (sequential), then `CheckInventory` and `ProcessPayment` run in parallel. A `Choice` state evaluates results and routes to confirmation or failure notification.

**Key concepts:** Step Functions ASL definition, Parallel state, Choice state, Task state, execution history, sequential + parallel orchestration.

**Run:** `task scenario:stepfunctions`

---

## 7. DynamoDB Ticket Selling System

```mermaid
flowchart LR
    C[Client] -->|List GET /tickets| GW[API Gateway]
    C -->|"Details GET /tickets/{id}"| GW
    C -->|Reserve PUT .../reserve| GW
    C -->|Purchase PUT .../purchase| GW
    C -->|Release PUT .../release| GW
    
    GW -->|Proxy| L[Lambda<br/>ticket-system-handler]
    L -->|Conditional Write| DDB[DynamoDB<br/>tickets table]
    L -->|Response| C

    subgraph State Machine
        direction LR
        AV[available] -->|reserve| RS[reserved]
        RS -->|purchase| PU[purchased]
        RS -->|release| AV
        RS -->|TTL 15min| AV
    end
```

**Flow:** API Gateway routes ticket operations to Lambda, which uses DynamoDB conditional writes for atomic state transitions. Tickets flow through `available → reserved → purchased` (or back to `available` via release or TTL expiry). Race conditions are prevented by DynamoDB's `ConditionalCheckFailedException`.

**Key concepts:** DynamoDB conditional writes (`ConditionExpression`), atomic state machine, TTL-based auto-expiry, API Gateway REST API, pessimistic concurrency control.

**Run:** `task scenario:dynamodb-tickets`

---

## 8. Notification System (Package Tracking)

```mermaid
flowchart LR
    C[Customer] -->|POST /packages<br/>GET /packages/{id}| GW[API Gateway]
    D[Driver App] -->|POST .../events| GW
    C -->|GET/PUT /preferences| GW
    
    GW -->|Proxy| L[Lambda<br/>notification-system-handler]
    
    L -->|CRUD| PKG[(DynamoDB<br/>packages)]
    L -->|CRUD| PREF[(DynamoDB<br/>preferences)]
    L -->|Cache pref| REDIS[(Redis<br/>preference cache)]
    L -->|Enqueue event| SQS[SQS Queue<br/>driver-events]
    SQS -->|ESM| L
    
    L -->|Notification| SNS[SNS Topic<br/>notifications-topic]
    SNS -->|SMS| PHONE[(Phone)]
    SNS -->|Email| EMAIL[(Email)]
    
    subgraph "Driver Events"
        PU[package_picked_up]
        PL[package_location_change]
        PD[package_delivered]
        PU -->|Notify| L
        PL -->|Notify| L
        PD -->|No notification| L
    end
    
    subgraph "ElastiCache (Redis)"
        direction LR
        CACHE[Redis TTL: 300s]
        MISS[Cache Miss → Query DynamoDB]
        HIT[Cache Hit]
    end
```

**Flow:** Customers create packages and set notification preferences (SMS/Email priority). Drivers send location events via API, which update DynamoDB and enqueue to SQS. A Lambda processses the SQS events — for `package_picked_up` and `package_location_change` it checks the user's notification preference (cached in Floci's ElastiCache Redis with 300s TTL via `redis-py`), then dispatches via SNS to the preferred channel(s).

**Key concepts:** API Gateway REST API, DynamoDB conditional updates, SQS event source mapping, ElastiCache (Redis) caching pattern, SNS multi-channel notifications, async event processing.

**Run:** `task notification-system:infrastructure` then `task notification-system:run`

---

## Infrastructure

```mermaid
flowchart LR
    subgraph "docker compose"
        F[Floci :4566<br/>latest-compat]
        CS[Cassandra 4.1 :9042]
    end
    subgraph "Volumes"
        FD[(floci_data)]
        CD[(cassandra_data)]
    end
    F -->|Docker socket| DE[Docker Engine]
    F -->|S3, DynamoDB,<br/>SQS, IAM, Lambda,<br/>API Gateway, EC2,<br/>Step Functions| DE
    F --> FD
    CS --> CD
```

| Service | Image | Purpose |
|---|---|---|
| Floci | `floci/floci:latest-compat` | AWS emulator (S3, DynamoDB, SQS, SNS, Lambda, IAM, API Gateway, EC2, Step Functions, CloudWatch) |
| Cassandra | `cassandra:4.1` | NoSQL database for orders scenario |
