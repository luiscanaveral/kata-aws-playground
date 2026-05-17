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

## 9. Feature Flags — AppConfig

```mermaid
flowchart LR
    subgraph AppConfig["AWS AppConfig"]
        APP[Application<br/>feature-flags-app]
        ENV[Environment<br/>production]
        PROF[Configuration Profile<br/>ui-layout]
        CFG[Hosted Config Version<br/>widget flags JSON]
        STRAT[Deployment Strategy<br/>quick-deploy]
    end

    CFG -->|deploy| ENV
    APP --> PROF
    PROF --> CFG

    subgraph Frontend
        BR[Browser<br/>HTML + JS]
    end

    BR -->|GET /| API[API Gateway]
    BR -->|GET /flags| API
    BR -->|POST /flags| API
    API -->|Proxy| L[Lambda<br/>feature-flags-handler]

    L -->|StartConfigurationSession<br/>GetLatestConfiguration| ACD[AppConfigData<br/>Data Plane]
    L -->|CreateHostedConfigurationVersion<br/>StartDeployment| ACC[AppConfig<br/>Control Plane]

    ACD -->|read flags| CFG
    ACC -->|update flags| CFG
    ACC -->|redeploy| ENV
```

**Flow:** A Lambda function serves a dashboard UI and a `/flags` API. `GET /flags` reads the current feature flag configuration via AppConfigData (data plane). Toggling a widget sends `POST /flags` which creates a new hosted configuration version and deploys it via AppConfig (control plane). The UI re-renders to reflect the new flag values.

**Key concepts:** AppConfig Application/Environment/Profile, hosted configuration versions, AppConfigData data-plane reads, AppConfig control-plane writes, deployment strategies, feature flag toggling in a live UI.

**Run:** `task feature-flags:infrastructure` then `task feature-flags:run`

---

## 10. SNS Fanout — Social Feed

```mermaid
flowchart LR
    subgraph Publisher
        PG[Post Generator<br/>run.py · every 15s]
    end

    PG -->|Publish| SNS[SNS Topic<br/>social-feed-topic]

    SNS -->|Fanout| FQ[SQS Queue<br/>feed-queue]
    SNS -->|Fanout| AQ[SQS Queue<br/>audit-queue]

    FQ -->|ESM| FP[Lambda<br/>feed-processor]
    AQ -->|ESM| AL[Lambda<br/>audit-logger]

    FP -->|PutItem| DDB[(DynamoDB<br/>social_posts)]
    AL -->|console.log| CW[CloudWatch Logs]

    subgraph Frontend
        FE[Browser<br/>HTML + JS]
    end

    FE -->|GET /| API[API Gateway]
    FE -->|GET /feed| API
    API -->|Proxy| FL[Lambda<br/>feed-api]
    FL -->|Scan| DDB
```

**Flow:** A Python script publishes a random post to SNS every 15 seconds. SNS fans out to two SQS queues: `feed-queue` triggers a Lambda that stores the post in DynamoDB, and `audit-queue` triggers a Lambda that logs the event to CloudWatch. A frontend (HTML+JS served by API Gateway) polls `/feed` and displays posts with a Refresh button.

**Key concepts:** SNS fanout pattern (one topic, multiple subscribers), SQS queues as subscribers, SQS-triggered Lambda, DynamoDB storage, API Gateway with simple frontend, polling refresh pattern.

**Run:** `task sns-fanout:infrastructure` then `task sns-fanout:run` (then open the printed URL)

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
