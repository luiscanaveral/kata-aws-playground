import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct


class BaseStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        iam.CfnRole(
            self,
            "LambdaExecRole",
            role_name="lambda-exec-role",
            assume_role_policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
        )

        for bucket_name in ["uploads", "images"]:
            s3.CfnBucket(
                self,
                f"Bucket{bucket_name.title()}",
                bucket_name=bucket_name,
            )

        ec2_role = iam.CfnRole(
            self,
            "Ec2WordpressRole",
            role_name="ec2-wordpress-role",
            assume_role_policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
        )

        iam.CfnInstanceProfile(
            self,
            "Ec2WordpressProfile",
            instance_profile_name="ec2-wordpress-profile",
            roles=[ec2_role.ref],
        )
