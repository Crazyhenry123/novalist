import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_logs as logs,
    aws_s3_assets as s3_assets,
    aws_lambda as lambda_,
    custom_resources as cr,
    CustomResource,
)
from constructs import Construct


class BackendStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        novels_table: dynamodb.Table,
        chapters_table: dynamodb.Table,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        vpc = ec2.Vpc.from_lookup(
            self, "Vpc",
            is_default=True,
        )

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        # ── ECR Repository ───────────────────────────────────
        repo = ecr.Repository(
            self, "BackendRepo",
            repository_name="novalist-backend",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        # ── Upload backend source to S3 for CodeBuild ────────
        source_asset = s3_assets.Asset(
            self, "BackendSource",
            path="../backend",
        )

        # ── CodeBuild project — builds Docker image and pushes to ECR ──
        build_project = codebuild.Project(
            self, "BuildProject",
            project_name="novalist-backend-build",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,  # Required for docker builds
                compute_type=codebuild.ComputeType.SMALL,
            ),
            environment_variables={
                "ECR_REPO_URI": codebuild.BuildEnvironmentVariable(
                    value=repo.repository_uri,
                ),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(
                    value=cdk.Stack.of(self).account,
                ),
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(
                    value=cdk.Stack.of(self).region,
                ),
            },
            source=codebuild.Source.s3(
                bucket=source_asset.bucket,
                path=source_asset.s3_object_key,
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Logging in to Amazon ECR...",
                            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Building Docker image...",
                            "docker build -t $ECR_REPO_URI:latest .",
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Pushing Docker image...",
                            "docker push $ECR_REPO_URI:latest",
                            "echo Build completed on `date`",
                        ]
                    },
                },
            }),
            timeout=cdk.Duration.minutes(15),
        )

        # Grant CodeBuild permissions to push to ECR
        repo.grant_pull_push(build_project)
        source_asset.grant_read(build_project)

        # ── Custom Resource — triggers CodeBuild on each deploy ──
        trigger_fn = lambda_.Function(
            self, "TriggerBuildFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(TRIGGER_BUILD_CODE),
            timeout=cdk.Duration.minutes(15),
            environment={
                "PROJECT_NAME": build_project.project_name,
            },
        )
        trigger_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                resources=[build_project.project_arn],
            )
        )

        trigger_provider = cr.Provider(
            self, "TriggerBuildProvider",
            on_event_handler=trigger_fn,
            # is_complete_handler could be used for async, but we poll in the Lambda
        )

        # Force a new build on every deploy by using the source asset hash
        CustomResource(
            self, "TriggerBuild",
            service_token=trigger_provider.service_token,
            properties={
                "ProjectName": build_project.project_name,
                "SourceHash": source_asset.asset_hash,  # Changes when source changes
            },
        )

        # ── Fargate Service using ECR image ──────────────────
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "Service",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
                container_port=8000,
                environment={
                    "NOVELS_TABLE": novels_table.table_name,
                    "CHAPTERS_TABLE": chapters_table.table_name,
                    "AWS_REGION": cdk.Stack.of(self).region,
                    "LOG_LEVEL": "INFO",
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="novalist",
                    log_retention=logs.RetentionDays.ONE_WEEK,
                ),
            ),
            public_load_balancer=True,
            assign_public_ip=True,
            min_healthy_percent=100,
        )

        # Ensure Fargate deploys AFTER the image is built
        self.fargate_service.node.add_dependency(
            self.node.find_child("TriggerBuild")
        )

        # Health check
        self.fargate_service.target_group.configure_health_check(
            path="/health",
            interval=cdk.Duration.seconds(30),
        )

        # Grant DynamoDB access
        novels_table.grant_read_write_data(
            self.fargate_service.task_definition.task_role
        )
        chapters_table.grant_read_write_data(
            self.fargate_service.task_definition.task_role
        )

        # Grant Bedrock access
        self.fargate_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["*"],
            )
        )

        self.service_url = (
            f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}"
        )

        cdk.CfnOutput(self, "BackendUrl", value=self.service_url)


# ── Lambda: triggers CodeBuild and waits for completion ──────

TRIGGER_BUILD_CODE = '''
import os
import time
import json
import boto3
import cfnresponse

codebuild = boto3.client("codebuild")

def handler(event, context):
    if event["RequestType"] == "Delete":
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        return

    project_name = os.environ["PROJECT_NAME"]

    try:
        # Start the build
        resp = codebuild.start_build(projectName=project_name)
        build_id = resp["build"]["id"]
        print(f"Started build: {build_id}")

        # Poll until complete (Lambda has 15 min timeout)
        while True:
            time.sleep(10)
            builds = codebuild.batch_get_builds(ids=[build_id])
            build = builds["builds"][0]
            status = build["buildStatus"]
            phase = build.get("currentPhase", "UNKNOWN")
            print(f"Build status: {status}, phase: {phase}")

            if status == "SUCCEEDED":
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                    "BuildId": build_id,
                })
                return
            elif status in ("FAILED", "FAULT", "STOPPED", "TIMED_OUT"):
                reason = f"CodeBuild {status}: {build_id}"
                print(reason)
                cfnresponse.send(event, context, cfnresponse.FAILED, {}, reason=reason)
                return
            # IN_PROGRESS — keep polling

    except Exception as e:
        print(f"Error: {e}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, reason=str(e))
'''
