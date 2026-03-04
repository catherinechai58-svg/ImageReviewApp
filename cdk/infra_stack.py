"""InfraStack — DynamoDB、S3、Cognito、CloudFront、IAM (Bedrock Role)"""

import aws_cdk as cdk
from aws_cdk import (
    aws_dynamodb as dynamodb,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    RemovalPolicy,
)
from constructs import Construct


class InfraStack(cdk.Stack):
    """管理所有 AWS 基础设施资源：DynamoDB、S3、Cognito、CloudFront、IAM。"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── DynamoDB 表定义（统一 ImageReviewApp 前缀）──

        # 1. Users 表
        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name=f"ImageReviewApp-Users",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 2. PromptTemplates 表
        self.prompt_templates_table = dynamodb.Table(
            self,
            "PromptTemplatesTable",
            table_name=f"ImageReviewApp-PromptTemplates",
            partition_key=dynamodb.Attribute(
                name="template_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI: NameIndex — PK: name
        self.prompt_templates_table.add_global_secondary_index(
            index_name="NameIndex",
            partition_key=dynamodb.Attribute(
                name="name", type=dynamodb.AttributeType.STRING
            ),
        )

        # 3. PromptTemplateHistory 表
        self.prompt_template_history_table = dynamodb.Table(
            self,
            "PromptTemplateHistoryTable",
            table_name=f"ImageReviewApp-PromptTemplateHistory",
            partition_key=dynamodb.Attribute(
                name="template_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="version", type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 4. Tasks 表
        self.tasks_table = dynamodb.Table(
            self,
            "TasksTable",
            table_name=f"ImageReviewApp-Tasks",
            partition_key=dynamodb.Attribute(
                name="task_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI: StatusIndex — PK: status, SK: created_at
        self.tasks_table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
        )

        # 5. TaskResults 表
        self.task_results_table = dynamodb.Table(
            self,
            "TaskResultsTable",
            table_name=f"ImageReviewApp-TaskResults",
            partition_key=dynamodb.Attribute(
                name="task_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="image_name", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI: TaskStatusIndex — PK: task_id, SK: status
        self.task_results_table.add_global_secondary_index(
            index_name="TaskStatusIndex",
            partition_key=dynamodb.Attribute(
                name="task_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
        )

        # GSI: TaskReviewIndex — PK: task_id, SK: review_result
        self.task_results_table.add_global_secondary_index(
            index_name="TaskReviewIndex",
            partition_key=dynamodb.Attribute(
                name="task_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="review_result", type=dynamodb.AttributeType.STRING
            ),
        )

        # 6. TaskLogs 表
        self.task_logs_table = dynamodb.Table(
            self,
            "TaskLogsTable",
            table_name=f"ImageReviewApp-TaskLogs",
            partition_key=dynamodb.Attribute(
                name="task_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── Cognito User Pool ──

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="ImageReviewAppUserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.user_pool_client = self.user_pool.add_client(
            "UserPoolClient",
            user_pool_client_name="ImageReviewAppClient",
            auth_flows=cognito.AuthFlow(
                admin_user_password=True,
                user_password=True,
                user_srp=True,
            ),
            generate_secret=False,
        )

        # ── S3 — 图片存储桶（CDK 管理）──

        image_bucket_name = f"imagereviewapp-images-{cdk.Aws.ACCOUNT_ID}"
        self.image_bucket = s3.Bucket(
            self,
            "ImageBucket",
            bucket_name=image_bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
        )

        # 前端静态资源桶
        self.frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"imagereviewapp-frontend-{cdk.Aws.ACCOUNT_ID}",
            website_index_document="index.html",
            website_error_document="index.html",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── CloudFront Distribution (OAC) ──

        self.distribution = cloudfront.Distribution(
            self,
            "ImageReviewAppDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.frontend_bucket,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
            ],
        )

        # ── IAM — Bedrock 批量推理角色（CDK 管理）──

        self.bedrock_batch_role = iam.Role(
            self,
            "ImageReviewAppBedrockBatchRole",
            role_name="ImageReviewAppBedrockBatchRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for Bedrock batch inference jobs",
        )

        # 授予 Bedrock 批量推理角色对图片桶的读写权限
        self.image_bucket.grant_read_write(self.bedrock_batch_role)

        # Bedrock 模型调用权限
        self.bedrock_batch_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=["*"],
            )
        )

        # ── 导出所有资源 ──

        # DynamoDB
        cdk.CfnOutput(self, "UsersTableName", value=self.users_table.table_name)
        cdk.CfnOutput(self, "PromptTemplatesTableName", value=self.prompt_templates_table.table_name)
        cdk.CfnOutput(self, "PromptTemplateHistoryTableName", value=self.prompt_template_history_table.table_name)
        cdk.CfnOutput(self, "TasksTableName", value=self.tasks_table.table_name)
        cdk.CfnOutput(self, "TaskResultsTableName", value=self.task_results_table.table_name)
        cdk.CfnOutput(self, "TaskLogsTableName", value=self.task_logs_table.table_name)

        # Cognito
        cdk.CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        cdk.CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)

        # S3
        cdk.CfnOutput(self, "ImageBucketName", value=self.image_bucket.bucket_name)
        cdk.CfnOutput(self, "FrontendBucketName", value=self.frontend_bucket.bucket_name)

        # CloudFront
        cdk.CfnOutput(self, "DistributionDomainName", value=self.distribution.distribution_domain_name)
        cdk.CfnOutput(self, "DistributionId", value=self.distribution.distribution_id)

        # IAM
        cdk.CfnOutput(self, "BedrockBatchRoleArn", value=self.bedrock_batch_role.role_arn)
