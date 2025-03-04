#!/bin/bash
set -e

echo "Creating SAM deployment bucket if it doesn't exist..."
aws s3 mb s3://sam-deployment-bucket-418295715028 --region us-east-1 || true

echo "Building SAM application..."
sam build

echo "Deploying SAM application..."
sam deploy

echo "Retrieving API Gateway URL..."
API_URL=$(aws cloudformation describe-stacks --stack-name helius-webhook-stack --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

echo "Webhook URL: $API_URL"
echo "Test with: curl -X POST -H \"Content-Type: application/json\" -d '{\"tokenTransfers\": [{\"fromUserAccount\": \"testuser\", \"mint\": \"testtoken\", \"tokenAmount\": 100}]}' $API_URL"