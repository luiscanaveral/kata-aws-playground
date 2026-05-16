import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct


class ImageUploadStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        s3.CfnBucket(
            self,
            "UploadBucket",
            bucket_name="upload-bucket",
        )

        role = iam.Role(
            self,
            "ImageUploadRole",
            role_name="image-upload-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:*", "s3:*"],
                resources=["*"],
            )
        )

        fn = lambda_.Function(
            self,
            "ImageUploadProcessor",
            function_name="image-upload-processor",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/image_upload/lambda_function"
            ),
            role=role,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            environment={
                "UPLOAD_BUCKET": "upload-bucket",
                "AWS_ENDPOINT_URL": "http://floci:4566",
            },
        )
