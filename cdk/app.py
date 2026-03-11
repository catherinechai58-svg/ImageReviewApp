#!/usr/bin/env python3
"""CDK 入口文件 — ImageReviewApp

支持通过 CDK context 参数指定部署区域:
  cdk deploy --all -c region=us-west-2
  cdk deploy --all -c region=ap-northeast-1

默认区域: ap-southeast-1
"""

import aws_cdk as cdk

from infra_stack import InfraStack
from app_stack import AppStack

app = cdk.App()

# 从 CDK context 读取 region，默认 ap-northeast-1
deploy_region = app.node.try_get_context("region") or "ap-southeast-1"

env = cdk.Environment(region=deploy_region)

# 全局 tag
cdk.Tags.of(app).add("Project", "ImageReviewApp")

infra_stack = InfraStack(app, "ImageReviewAppInfraStack", env=env)

app_stack = AppStack(
    app,
    "ImageReviewAppStack",
    infra_stack=infra_stack,
    env=env,
)
app_stack.add_dependency(infra_stack)

app.synth()
