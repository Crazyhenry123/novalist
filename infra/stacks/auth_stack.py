import aws_cdk as cdk
from aws_cdk import (
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_iam as iam,
    custom_resources as cr,
    CustomResource,
)
from constructs import Construct


class AuthStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="novalist-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.user_pool_client = cognito.UserPoolClient(
            self, "WebClient",
            user_pool=self.user_pool,
            user_pool_client_name="novalist-web",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            id_token_validity=cdk.Duration.hours(1),
            access_token_validity=cdk.Duration.hours(1),
            refresh_token_validity=cdk.Duration.days(30),
        )

        # Lambda to create admin user on deploy
        admin_fn = lambda_.Function(
            self, "CreateAdminFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(ADMIN_USER_LAMBDA_CODE),
            timeout=cdk.Duration.seconds(30),
        )
        self.user_pool.grant(
            admin_fn,
            "cognito-idp:AdminCreateUser",
            "cognito-idp:AdminSetUserPassword",
        )

        provider = cr.Provider(self, "AdminUserProvider", on_event_handler=admin_fn)

        CustomResource(
            self, "AdminUser",
            service_token=provider.service_token,
            properties={
                "UserPoolId": self.user_pool.user_pool_id,
                "Username": "admin@novalist.ai",
                "TempPassword": "Admin123!Change",
            },
        )

        cdk.CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        cdk.CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)


ADMIN_USER_LAMBDA_CODE = '''
import boto3
import cfnresponse

def handler(event, context):
    if event["RequestType"] == "Delete":
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        return
    try:
        client = boto3.client("cognito-idp")
        props = event["ResourceProperties"]
        pool_id = props["UserPoolId"]
        username = props["Username"]
        temp_pw = props["TempPassword"]
        try:
            client.admin_create_user(
                UserPoolId=pool_id,
                Username=username,
                TemporaryPassword=temp_pw,
                MessageAction="SUPPRESS",
                UserAttributes=[
                    {"Name": "email", "Value": username},
                    {"Name": "email_verified", "Value": "true"},
                ],
            )
        except client.exceptions.UsernameExistsException:
            pass
        client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password=temp_pw,
            Permanent=True,
        )
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {"Username": username})
    except Exception as e:
        print(e)
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)})
'''
