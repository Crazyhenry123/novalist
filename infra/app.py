#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.auth_stack import AuthStack
from stacks.backend_stack import BackendStack
from stacks.api_stack import ApiStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", app.node.try_get_context("account")),
    region=os.environ.get("CDK_DEFAULT_REGION", app.node.try_get_context("region") or "us-east-1"),
)

storage = StorageStack(app, "NovalistStorage", env=env)
auth = AuthStack(app, "NovalistAuth", env=env)
backend = BackendStack(
    app, "NovalistBackend",
    env=env,
    novels_table=storage.novels_table,
    chapters_table=storage.chapters_table,
    data_bucket=storage.data_bucket,
)
api = ApiStack(
    app, "NovalistApi",
    env=env,
    user_pool=auth.user_pool,
    backend_url=backend.service_url,
    connections_table=storage.connections_table,
)
frontend = FrontendStack(
    app, "NovalistFrontend",
    env=env,
    user_pool=auth.user_pool,
    user_pool_client=auth.user_pool_client,
    backend_alb=backend.fargate_service.load_balancer,
)

app.synth()
