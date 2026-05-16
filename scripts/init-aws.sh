#!/bin/bash
set -euo pipefail

AWS="aws --endpoint-url http://localhost:4566"

echo "=== Initializing AWS resources ==="

# Create IAM role for Lambda execution
$AWS iam create-role \
  --role-name lambda-exec-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || echo "IAM role already exists"

# Create S3 buckets
for bucket in uploads images; do
  $AWS s3 mb "s3://$bucket" 2>/dev/null || echo "Bucket $bucket already exists"
done

# Create SQS queues
$AWS sqs create-queue --queue-name order-events 2>/dev/null || echo "Queue order-events already exists"
$AWS sqs create-queue --queue-name order-notifications 2>/dev/null || echo "Queue order-notifications already exists"

# Create IAM role for EC2 WordPress
$AWS iam create-role \
  --role-name ec2-wordpress-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || echo "EC2 role already exists"

# Create instance profile for EC2
$AWS iam create-instance-profile --instance-profile-name ec2-wordpress-profile 2>/dev/null || echo "Instance profile already exists"
$AWS iam add-role-to-instance-profile \
  --instance-profile-name ec2-wordpress-profile \
  --role-name ec2-wordpress-role 2>/dev/null || echo "Role already attached to profile"

echo "=== Initialization complete ==="
