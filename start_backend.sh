#!/bin/bash

# Load environment variables
export USERS_TABLE=ImageReviewApp-Users
export PROMPT_TEMPLATES_TABLE=ImageReviewApp-PromptTemplates
export PROMPT_TEMPLATE_HISTORY_TABLE=ImageReviewApp-PromptTemplateHistory
export TASKS_TABLE=ImageReviewApp-Tasks
export TASK_RESULTS_TABLE=ImageReviewApp-TaskResults
export TASK_LOGS_TABLE=ImageReviewApp-TaskLogs
export SETTINGS_TABLE=ImageReviewApp-Settings
export IMAGE_BUCKET=imagereviewapp-images-297126936078
export AWS_REGION=ap-southeast-1
export AWS_REGION_NAME=ap-southeast-1
export USER_POOL_ID=ap-southeast-1_za1D2xSah
export USER_POOL_CLIENT_ID=51f446m8lk6ieaeq6t13bnd1nt
export ROLE_ARN=arn:aws:iam::297126936078:role/ImageReviewAppBedrockBatchRole
export CONCURRENCY=3

echo "Starting backend server..."
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
