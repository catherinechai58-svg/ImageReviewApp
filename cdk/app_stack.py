"""AppStack — ECS Fargate 服务、VPC、ALB、IAM 权限、前端部署"""

import os

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_s3_deployment as s3deploy,
)
from constructs import Construct

from infra_stack import InfraStack


class AppStack(cdk.Stack):
    """ECS Fargate 后端服务和前端静态资源部署。"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        infra_stack: InfraStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.infra = infra_stack

        # ── 公共环境变量（引用 CDK 管理的资源）──
        common_env = {
            "USERS_TABLE": self.infra.users_table.table_name,
            "PROMPT_TEMPLATES_TABLE": self.infra.prompt_templates_table.table_name,
            "PROMPT_TEMPLATE_HISTORY_TABLE": self.infra.prompt_template_history_table.table_name,
            "TASKS_TABLE": self.infra.tasks_table.table_name,
            "TASK_RESULTS_TABLE": self.infra.task_results_table.table_name,
            "TASK_LOGS_TABLE": self.infra.task_logs_table.table_name,
            "SETTINGS_TABLE": self.infra.settings_table.table_name,
            "IMAGE_BUCKET": self.infra.image_bucket.bucket_name,
            "AWS_REGION_NAME": self.region,
            "USER_POOL_ID": self.infra.user_pool.user_pool_id,
            "USER_POOL_CLIENT_ID": self.infra.user_pool_client.user_pool_client_id,
            "ROLE_ARN": self.infra.bedrock_batch_role.role_arn,
            "CONCURRENCY": "3",
        }

        backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")

        # ══════════════════════════════════════════════
        # VPC
        # ══════════════════════════════════════════════

        vpc = ec2.Vpc(
            self, "ImageReviewAppVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
            ],
        )

        # ══════════════════════════════════════════════
        # ECS Cluster
        # ══════════════════════════════════════════════

        cluster = ecs.Cluster(self, "ImageReviewAppCluster", vpc=vpc)

        # ══════════════════════════════════════════════
        # Docker Image
        # ══════════════════════════════════════════════

        image = ecr_assets.DockerImageAsset(
            self, "ImageReviewAppBackendImage", 
            directory=backend_path,
            platform=ecr_assets.Platform.LINUX_AMD64  # 强制使用 x86_64 架构
        )

        # ══════════════════════════════════════════════
        # ALB + Fargate Service
        # ══════════════════════════════════════════════

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "ImageReviewAppService",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(image),
                container_port=8000,
                environment=common_env,
            ),
            public_load_balancer=True,
        )

        # ALB 健康检查
        fargate_service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
        )

        # ══════════════════════════════════════════════
        # ECS Task Role IAM 权限
        # ══════════════════════════════════════════════

        task_role = fargate_service.task_definition.task_role

        # DynamoDB 全表读写
        self.infra.users_table.grant_read_write_data(task_role)
        self.infra.prompt_templates_table.grant_read_write_data(task_role)
        self.infra.prompt_template_history_table.grant_read_write_data(task_role)
        self.infra.tasks_table.grant_read_write_data(task_role)
        self.infra.task_results_table.grant_read_write_data(task_role)
        self.infra.task_logs_table.grant_read_write_data(task_role)
        self.infra.settings_table.grant_read_write_data(task_role)

        # S3 读写
        self.infra.image_bucket.grant_read_write(task_role)

        # Bedrock invoke + converse + batch
        task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:Converse",
                    "bedrock:CreateModelInvocationJob",
                    "bedrock:GetModelInvocationJob",
                ],
                resources=["*"],
            )
        )

        # Cognito
        task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminDeleteUser",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:ListUsers",
                    "cognito-idp:ChangePassword",
                ],
                resources=[self.infra.user_pool.user_pool_arn],
            )
        )

        # iam:PassRole（Bedrock 批量推理需要传递角色）
        task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[self.infra.bedrock_batch_role.role_arn],
            )
        )

        # ══════════════════════════════════════════════
        # 前端静态资源部署
        # ══════════════════════════════════════════════

        frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

        s3deploy.BucketDeployment(
            self, "ImageReviewAppFrontendDeployment",
            sources=[s3deploy.Source.asset(frontend_dist_path)],
            destination_bucket=self.infra.frontend_bucket,
            distribution=self.infra.distribution,
            distribution_paths=["/*"],
        )

        # ── 输出 ALB DNS ──
        cdk.CfnOutput(self, "ALBDnsName", value=fargate_service.load_balancer.load_balancer_dns_name)
