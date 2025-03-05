# Helius Webhook Handler with Lambda Layers

A serverless webhook handler for processing Helius transaction data, storing it in Snowflake, and triggering Airflow DAGs for further processing. Implemented using AWS Lambda with Lambda layers to solve dependency compatibility issues.

## Architecture

![Architecture Diagram](https://via.placeholder.com/800x400?text=Helius+Webhook+Architecture)

- **API Gateway**: Receives webhook requests from Helius
- **Lambda Function**: Processes transaction data
- **Lambda Layers**: Manage dependencies separately from function code
  - **Snowflake Layer**: Contains Snowflake-related dependencies with compatible versions
  - **Utility Layer**: Contains common utility libraries
- **Snowflake**: Stores processed transaction data
- **Airflow**: Handles workflow triggering

## Key Features

- **Real-time processing** of Helius transaction data
- **Direct insertion** into Snowflake tables
- **Automated DAG triggering** in Airflow
- **Robust dependency management** using Lambda layers to overcome compatibility issues
- **Serverless architecture** for scalability and cost efficiency

## Prerequisites

- AWS Account with CLI access
- Docker installed and running
- Python 3.11
- AWS SAM CLI

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/helius-webhook-handler.git
   cd helius-webhook-handler
   ```

2. **Set up environment variables**
   Create a `.env` file with:
   ```
   SNOWFLAKE_ACCOUNT=your-account
   SNOWFLAKE_USER=your-user
   SNOWFLAKE_PASSWORD=your-password
   SNOWFLAKE_WAREHOUSE=your-warehouse
   SNOWFLAKE_DATABASE=your-database
   SNOWFLAKE_SCHEMA=your-schema
   SNOWFLAKE_ROLE=your-role
   AIRFLOW_ENDPOINT=your-airflow-url
   AIRFLOW_USERNAME=your-airflow-username
   AIRFLOW_PASSWORD=your-airflow-password
   ```

3. **Build and deploy**
   ```bash
   chmod +x build_layers.sh deploy.sh
   ./deploy.sh
   ```

4. **Test the webhook**
   ```bash
   # Test with sample data
   curl -X POST \
     -H "Content-Type: application/json" \
     -d @test-event.json \
     <your-api-endpoint>
   ```

## Using Lambda Layers to Solve Dependency Issues

This project uses Lambda layers to solve common issues with the cryptography module and other dependencies. The layers are built using Docker to ensure compatibility with the Lambda runtime environment.

### Problem Solved

The cryptography module often causes errors in Lambda environments:
```
module 'cryptography.hazmat.bindings._rust.openssl' has no attribute 'hashes'
```

### Solution

We use two Lambda layers:

1. **Snowflake Layer**
   - Contains `snowflake-sqlalchemy`, `snowflake-connector-python`, `SQLAlchemy`
   - Uses a specific `cryptography` version (39.0.2) known to work in Lambda

2. **Utility Layer**
   - Contains common dependencies like `requests` and `boto3`

The layers are built in a Docker container that matches the Lambda runtime environment, ensuring compatibility.

## Directory Structure

```
├── build_layers.sh          # Script to build Lambda layers
├── deploy.sh                # Main deployment script
├── helius_api.py            # Helper for Helius API interactions
├── lambda/                  # Lambda function deployment package
├── lambda_function.py       # Main Lambda handler code
├── layers/                  # Lambda layers
│   ├── snowflake_layer/     # Snowflake dependencies layer
│   │   └── python/          # Python packages
│   │       └── requirements.txt
│   └── utility_layer/       # Utility dependencies layer
│       └── python/          # Python packages
│           └── requirements.txt
├── test-event.json          # Sample event for testing
├── template.yaml            # SAM template
└── update_helius_webhook.py # Script to update Helius webhook URL
```

## Deployment

The deployment process:

1. **Build Lambda layers** with Docker to ensure compatibility
2. **Package Lambda function** and dependencies
3. **Deploy with SAM** to create/update API Gateway and Lambda resources
4. **Update Helius webhook** URL automatically

## Testing

You can test the webhook with:

```bash
# Using curl
curl -X POST \
  -H "Content-Type: application/json" \
  -d @test-event.json \
  <your-api-endpoint>

# Or using AWS CLI to invoke Lambda directly
aws lambda invoke \
  --function-name <function-name> \
  --payload file://test-event.json \
  response.json
```

## Troubleshooting

**Common Issues:**

- **Cryptography Module Errors**: Ensure layers are built correctly with Docker
- **Snowflake Connection Issues**: Verify credentials and network access
- **Layer Size Limits**: Each layer must be under 250MB unzipped
- **Missing Modules**: Ensure requirements.txt files are complete

**Checking Logs:**

```bash
# Get the function name
FUNCTION=$(aws cloudformation describe-stack-resources --stack-name helius-webhook-stack --query "StackResources[?ResourceType=='AWS::Lambda::Function'].PhysicalResourceId" --output text)

# Get the latest log stream
LOG_GROUP="/aws/lambda/$FUNCTION"
LOG_STREAM=$(aws logs describe-log-streams --log-group-name $LOG_GROUP --order-by LastEventTime --descending --limit 1 --query "logStreams[0].logStreamName" --output text)

# View logs
aws logs get-log-events --log-group-name $LOG_GROUP --log-stream-name $LOG_STREAM
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [AWS SAM](https://aws.amazon.com/serverless/sam/)
- [Helius](https://helius.xyz/)
- [Snowflake](https://www.snowflake.com/)
- [Apache Airflow](https://airflow.apache.org/)