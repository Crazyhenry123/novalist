import aws_cdk as cdk
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cognito as cognito,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct


class FrontendStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        backend_alb: elbv2.IApplicationLoadBalancer,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        bucket = s3.Bucket(
            self, "WebBucket",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        oai = cloudfront.OriginAccessIdentity(self, "OAI")
        bucket.grant_read(oai)

        # ALB origin for /api/* — SSE streaming from backend
        # read_timeout=180s to handle long Bedrock agent responses
        alb_origin = origins.HttpOrigin(
            backend_alb.load_balancer_dns_name,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            read_timeout=cdk.Duration.seconds(60),
            keepalive_timeout=cdk.Duration.seconds(60),
        )

        distribution = cloudfront.Distribution(
            self, "CDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_identity(
                    bucket, origin_access_identity=oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                ),
                "/health": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_page_path="/index.html",
                    response_http_status=200,
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_page_path="/index.html",
                    response_http_status=200,
                ),
            ],
        )

        s3deploy.BucketDeployment(
            self, "Deploy",
            sources=[s3deploy.Source.asset("../frontend/dist")],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        cdk.CfnOutput(self, "DistributionUrl",
                       value=f"https://{distribution.distribution_domain_name}")
        cdk.CfnOutput(self, "CognitoUserPoolId",
                       value=user_pool.user_pool_id)
        cdk.CfnOutput(self, "CognitoClientId",
                       value=user_pool_client.user_pool_client_id)
