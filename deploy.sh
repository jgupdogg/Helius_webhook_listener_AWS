#!/bin/bash
set -e

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

# Generate a timestamp for unique stack name
TIMESTAMP=$(date +%Y%m%d%H%M%S)
STACK_NAME="helius-webhook-stack-$TIMESTAMP"
echo "Using stack name: $STACK_NAME"

# Get AWS account ID
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
DEPLOYMENT_BUCKET="helius-webhook-deployment-$AWS_ACCOUNT"

# Create deployment bucket if it doesn't exist
echo "Making sure deployment bucket exists..."
aws s3 mb s3://$DEPLOYMENT_BUCKET --region us-east-1 || true

# Install dependencies to a package directory
echo "Installing dependencies..."
rm -rf package/
mkdir -p package
pip install -r requirements.txt -t package/

# Copy lambda function to package directory
echo "Copying lambda function code..."
cp lambda_function.py package/

echo "Building SAM application..."
sam build

echo "Deploying SAM application..."
sam deploy \
  --stack-name $STACK_NAME \
  --s3-bucket $DEPLOYMENT_BUCKET \
  --capabilities CAPABILITY_IAM \
  --no-resolve-s3 \
  --parameter-overrides \
  "SnowflakePassword=$SNOWFLAKE_PASSWORD" \
  "AirflowPassword=$AIRFLOW_PASSWORD"

echo "Retrieving API Gateway URL..."
API_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

echo "Webhook URL: $API_URL"
echo "Test with: curl -X POST -H \"Content-Type: application/json\" -d '{\"tokenTransfers\": [{\"fromUserAccount\": \"testuser\", \"mint\": \"testtoken\", \"tokenAmount\": 100}]}' $API_URL"

# Save stack name for later reference
echo "LATEST_STACK_NAME=$STACK_NAME" > .stack_info