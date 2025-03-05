#!/bin/bash
set -e

# Use a stable stack name
STACK_NAME="helius-webhook-stack"
echo "Using stable stack name: $STACK_NAME"

# Load environment variables from .env file
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
else
  echo "Error: .env file not found!"
  exit 1
fi

# Check if required variables are set
if [ -z "$SNOWFLAKE_PASSWORD" ] || [ -z "$AIRFLOW_PASSWORD" ]; then
  echo "Error: Required environment variables are missing in .env file!"
  echo "Make sure SNOWFLAKE_PASSWORD and AIRFLOW_PASSWORD are set."
  exit 1
fi

# Get AWS account ID
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
DEPLOYMENT_BUCKET="helius-webhook-deployment-$AWS_ACCOUNT"

# Create deployment bucket if it doesn't exist
echo "Creating deployment bucket if it doesn't exist..."
if ! aws s3 ls "s3://$DEPLOYMENT_BUCKET" 2>&1 > /dev/null; then
  echo "Bucket doesn't exist. Creating it..."
  aws s3 mb "s3://$DEPLOYMENT_BUCKET" --region us-east-1
  
  # Wait for bucket to be available
  echo "Waiting for bucket to be available..."
  aws s3api wait bucket-exists --bucket "$DEPLOYMENT_BUCKET"
  
  # Additional sleep to ensure bucket is fully available
  echo "Bucket created. Waiting 5 seconds for propagation..."
  sleep 5
else
  echo "Bucket already exists."
fi

# Verify bucket is accessible
echo "Verifying bucket access..."
if ! aws s3 ls "s3://$DEPLOYMENT_BUCKET" > /dev/null; then
  echo "Error: Cannot access bucket. Please check permissions."
  exit 1
fi
echo "Bucket verification successful."

# Check if stack already exists
if aws cloudformation describe-stacks --stack-name $STACK_NAME &>/dev/null; then
  echo "Stack $STACK_NAME already exists. Will update it."
fi

# Prepare the lambda directory
echo "Preparing Lambda function code..."
mkdir -p lambda
cp lambda_function.py lambda/

# Build Lambda layers
echo "Building Lambda layers..."
chmod +x build_layers.sh
./build_layers.sh

echo "Building and deploying SAM application..."
sam build
sam deploy \
  --stack-name $STACK_NAME \
  --s3-bucket $DEPLOYMENT_BUCKET \
  --capabilities CAPABILITY_IAM \
  --no-resolve-s3 \
  --parameter-overrides \
  "SnowflakePassword=$SNOWFLAKE_PASSWORD" \
  "AirflowPassword=$AIRFLOW_PASSWORD" \
  "SnowflakeAccount=${SNOWFLAKE_ACCOUNT}" \
  "SnowflakeUser=${SNOWFLAKE_USER}" \
  "SnowflakeWarehouse=${SNOWFLAKE_WAREHOUSE:-DEV_WH}" \
  "SnowflakeDatabase=${SNOWFLAKE_DATABASE:-DEV}" \
  "SnowflakeSchema=${SNOWFLAKE_SCHEMA:-BRONZE}" \
  "SnowflakeRole=${SNOWFLAKE_ROLE:-AIRFLOW_ROLE}" \
  "AirflowEndpoint=${AIRFLOW_ENDPOINT:-http://52.205.187.101:8080}" \
  "AirflowUsername=${AIRFLOW_USERNAME:-admin}"

echo "Retrieving API Gateway URL..."
API_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

echo "Webhook URL: $API_URL"
echo "Test with: curl -X POST -H \"Content-Type: application/json\" -d '{\"tokenTransfers\": [{\"fromUserAccount\": \"testuser\", \"mint\": \"testtoken\", \"tokenAmount\": 100}]}' $API_URL"

echo "Deployment completed successfully!"