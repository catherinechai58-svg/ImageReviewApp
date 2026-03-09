#!/bin/bash

STACK_NAME="ImageReviewAppInfraStack"
REGION="ap-southeast-1"

echo "Fetching outputs from $STACK_NAME..."

OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

if [ $? -ne 0 ]; then
  echo "Error: Failed to fetch stack outputs"
  exit 1
fi

IMAGE_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ImageBucketName") | .OutputValue')
USER_POOL_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolId") | .OutputValue')
USER_POOL_CLIENT_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolClientId") | .OutputValue')
ROLE_ARN=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="BedrockBatchRoleArn") | .OutputValue')

cat << EOF
export USERS_TABLE=ImageReviewApp-Users
export PROMPT_TEMPLATES_TABLE=ImageReviewApp-PromptTemplates
export PROMPT_TEMPLATE_HISTORY_TABLE=ImageReviewApp-PromptTemplateHistory
export TASKS_TABLE=ImageReviewApp-Tasks
export TASK_RESULTS_TABLE=ImageReviewApp-TaskResults
export TASK_LOGS_TABLE=ImageReviewApp-TaskLogs
export SETTINGS_TABLE=ImageReviewApp-Settings
export IMAGE_BUCKET=$IMAGE_BUCKET
export AWS_REGION_NAME=$REGION
export USER_POOL_ID=$USER_POOL_ID
export USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID
export ROLE_ARN=$ROLE_ARN
export CONCURRENCY=3
EOF
