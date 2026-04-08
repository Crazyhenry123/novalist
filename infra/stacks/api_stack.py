import aws_cdk as cdk
from aws_cdk import (
    aws_apigatewayv2 as apigwv2,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_cognito as cognito,
    aws_logs as logs,
)
from constructs import Construct


class ApiStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        user_pool: cognito.UserPool,
        backend_url: str,
        connections_table: dynamodb.Table,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        common_env = {
            "CONNECTIONS_TABLE": connections_table.table_name,
            "BACKEND_URL": backend_url,
            "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
            "COGNITO_REGION": cdk.Stack.of(self).region,
        }

        connect_fn = lambda_.Function(
            self, "ConnectFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("../backend/lambda", bundling=None)
            if False
            else lambda_.Code.from_inline(CONNECT_CODE),
            environment=common_env,
            timeout=cdk.Duration.seconds(10),
        )

        disconnect_fn = lambda_.Function(
            self, "DisconnectFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(DISCONNECT_CODE),
            environment=common_env,
            timeout=cdk.Duration.seconds(10),
        )

        message_fn = lambda_.Function(
            self, "MessageFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(MESSAGE_CODE),
            environment=common_env,
            timeout=cdk.Duration.seconds(15),
            memory_size=512,
        )

        connections_table.grant_read_write_data(connect_fn)
        connections_table.grant_read_write_data(disconnect_fn)
        connections_table.grant_read_write_data(message_fn)

        # WebSocket API
        ws_api = apigwv2.CfnApi(
            self, "WebSocketApi",
            name="novalist-ws",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
        )

        # Integrations
        connect_integration = apigwv2.CfnIntegration(
            self, "ConnectIntegration",
            api_id=ws_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=(
                f"arn:aws:apigateway:{cdk.Stack.of(self).region}"
                f":lambda:path/2015-03-31/functions/{connect_fn.function_arn}/invocations"
            ),
        )
        disconnect_integration = apigwv2.CfnIntegration(
            self, "DisconnectIntegration",
            api_id=ws_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=(
                f"arn:aws:apigateway:{cdk.Stack.of(self).region}"
                f":lambda:path/2015-03-31/functions/{disconnect_fn.function_arn}/invocations"
            ),
        )
        message_integration = apigwv2.CfnIntegration(
            self, "MessageIntegration",
            api_id=ws_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=(
                f"arn:aws:apigateway:{cdk.Stack.of(self).region}"
                f":lambda:path/2015-03-31/functions/{message_fn.function_arn}/invocations"
            ),
        )

        # Routes
        apigwv2.CfnRoute(
            self, "ConnectRoute",
            api_id=ws_api.ref,
            route_key="$connect",
            authorization_type="NONE",
            target=f"integrations/{connect_integration.ref}",
        )
        apigwv2.CfnRoute(
            self, "DisconnectRoute",
            api_id=ws_api.ref,
            route_key="$disconnect",
            target=f"integrations/{disconnect_integration.ref}",
        )
        apigwv2.CfnRoute(
            self, "DefaultRoute",
            api_id=ws_api.ref,
            route_key="$default",
            target=f"integrations/{message_integration.ref}",
        )

        # Stage
        stage = apigwv2.CfnStage(
            self, "WsStage",
            api_id=ws_api.ref,
            stage_name="prod",
            auto_deploy=True,
        )

        # Lambda permissions for API Gateway
        for fn in [connect_fn, disconnect_fn, message_fn]:
            fn.add_permission(
                f"AllowApiGw-{fn.node.id}",
                principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
                source_arn=f"arn:aws:execute-api:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:{ws_api.ref}/*",
            )

        # Grant message_fn permission to post back to WebSocket connections
        message_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:{ws_api.ref}/prod/*"
                ],
            )
        )

        self.websocket_url = f"wss://{ws_api.ref}.execute-api.{cdk.Stack.of(self).region}.amazonaws.com/prod"

        cdk.CfnOutput(self, "WebSocketUrl", value=self.websocket_url)


# ── Lambda Code ──────────────────────────────────────────────

CONNECT_CODE = '''
import os, json, time, boto3

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["CONNECTIONS_TABLE"])

def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    # Extract token from query string for auth
    qs = event.get("queryStringParameters") or {}
    token = qs.get("token", "")
    table.put_item(Item={
        "connection_id": connection_id,
        "token": token,
        "connected_at": int(time.time()),
        "ttl": int(time.time()) + 86400,
    })
    return {"statusCode": 200}
'''

DISCONNECT_CODE = '''
import os, boto3

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["CONNECTIONS_TABLE"])

def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    table.delete_item(Key={"connection_id": connection_id})
    return {"statusCode": 200}
'''

MESSAGE_CODE = '''
import os, json, boto3, urllib.request, urllib.error, socket

BACKEND_URL = os.environ["BACKEND_URL"]

def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]
    callback_url = f"https://{domain}/{stage}"

    body = json.loads(event.get("body", "{}"))
    body["connection_id"] = connection_id
    body["callback_url"] = callback_url

    # Fire-and-forget: dispatch to Fargate backend with a very short timeout.
    # The backend handles all client communication via post_to_connection
    # directly, so we do NOT need to wait for the full response.
    req = urllib.request.Request(
        f"{BACKEND_URL}/agent/invoke",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # 2s timeout — just enough to confirm Fargate received the request.
        # The backend runs the pipeline asynchronously and streams results
        # back to the client via API Gateway Management API.
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except socket.timeout:
        # Timeout is expected — the pipeline takes minutes. This is normal
        # fire-and-forget behavior; the backend continues processing.
        pass
    except (urllib.error.URLError, ConnectionRefusedError, OSError) as e:
        # Connection errors mean the backend is unreachable — notify the client.
        print(f"Backend connection error: {e}")
        apigw = boto3.client(
            "apigatewaymanagementapi", endpoint_url=callback_url
        )
        try:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({"error": "Backend is temporarily unavailable. Please try again shortly."}).encode(),
            )
        except Exception:
            pass  # Client may have already disconnected
        return {"statusCode": 502}

    return {"statusCode": 200}
'''
