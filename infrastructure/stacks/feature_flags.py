import json

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_appconfig as appconfig
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


INITIAL_FLAGS = {
    "widgets": [
        {"id": "weather", "title": "Weather", "visible": True, "order": 1},
        {"id": "news", "title": "News Feed", "visible": True, "order": 2},
        {"id": "stocks", "title": "Stock Ticker", "visible": False, "order": 3},
        {"id": "calendar", "title": "Calendar", "visible": True, "order": 4},
        {"id": "todo", "title": "To-Do List", "visible": True, "order": 5},
        {"id": "analytics", "title": "Analytics", "visible": False, "order": 6},
    ],
    "theme": "light",
}


class FeatureFlagsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        app = appconfig.CfnApplication(
            self,
            "FeatureFlagsApp",
            name="feature-flags-app",
            description="Feature flags managed by AppConfig",
        )

        env = appconfig.CfnEnvironment(
            self,
            "FeatureFlagsEnv",
            application_id=app.ref,
            name="production",
            description="Production environment",
        )

        profile = appconfig.CfnConfigurationProfile(
            self,
            "FeatureFlagsProfile",
            application_id=app.ref,
            location_uri="hosted",
            name="ui-layout",
            description="UI widget layout flags",
            type="AWS.Freeform",
        )

        version = appconfig.CfnHostedConfigurationVersion(
            self,
            "InitialConfigVersion",
            application_id=app.ref,
            configuration_profile_id=profile.ref,
            content=json.dumps(INITIAL_FLAGS),
            content_type="application/json",
        )

        strategy = appconfig.CfnDeploymentStrategy(
            self,
            "QuickDeploy",
            name="quick-deploy",
            description="Instant deployment for local testing",
            deployment_duration_in_minutes=0,
            growth_factor=100,
            final_bake_time_in_minutes=0,
            replicate_to="NONE",
        )

        appconfig.CfnDeployment(
            self,
            "InitialDeployment",
            application_id=app.ref,
            configuration_profile_id=profile.ref,
            configuration_version=version.ref,
            deployment_strategy_id=strategy.ref,
            environment_id=env.ref,
        )

        role = iam.Role(
            self,
            "FeatureFlagsRole",
            role_name="feature-flags-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:*",
                    "appconfig:*",
                    "appconfigdata:*",
                ],
                resources=["*"],
            )
        )

        fn = lambda_.Function(
            self,
            "FeatureFlagsHandler",
            function_name="feature-flags-handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "scenarios/feature_flags/lambda_function"
            ),
            role=role,
            timeout=Duration.seconds(15),
            memory_size=128,
            environment={
                "APPCFG_APP_ID": app.ref,
                "APPCFG_ENV_ID": env.ref,
                "APPCFG_PROFILE_ID": profile.ref,
                "APPCFG_STRATEGY_ID": strategy.ref,
                "AWS_ENDPOINT_URL": "http://floci:4566",
            },
        )

        api = apigw.LambdaRestApi(
            self,
            "FeatureFlagsApi",
            rest_api_name="feature-flags-api",
            handler=fn,
            proxy=False,
        )
        root = api.root
        root.add_method("GET")
        root.add_resource("flags").add_method("GET")
        root.add_resource("flags").add_method("POST")
