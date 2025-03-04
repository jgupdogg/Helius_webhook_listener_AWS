import json
import boto3
import os
import uuid
import logging
import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Lambda handler for webhook events:
    1. Stores raw data in S3
    2. Processes the data and stores the processed version
    """
    try:
        # Get environment variables
        bucket_name = os.environ.get('S3_BUCKET')
        
        # Extract body from API Gateway event
        if 'body' in event:
            # From API Gateway
            try:
                if isinstance(event['body'], str):
                    payload = json.loads(event['body'])
                else:
                    payload = event['body']
            except json.JSONDecodeError:
                return respond(400, {'message': 'Invalid JSON in request body'})
        else:
            # Direct invocation
            payload = event
        
        # Generate a unique filename for S3
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:8]
        s3_key = f"webhook-data/{timestamp}_{random_suffix}.json"
        
        # Store raw data in S3
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(payload),
            ContentType='application/json',
            Metadata={
                'processed': 'false',
                'timestamp': timestamp
            }
        )
        
        logger.info(f"Raw data stored in S3: {bucket_name}/{s3_key}")

        # Process the webhook data
        try:
            # Preprocess the data
            processed_records = process_transaction_data(payload)
            
            if processed_records:
                # Store processed data in S3
                processed_s3_key = f"processed-data/{timestamp}_{random_suffix}.json"
                s3.put_object(
                    Bucket=bucket_name,
                    Key=processed_s3_key,
                    Body=json.dumps(processed_records),
                    ContentType='application/json'
                )
                logger.info(f"Processed data stored in S3: {bucket_name}/{processed_s3_key}")
            else:
                logger.info("No valid records to process")
            
        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            # Continue execution - we don't want to fail the webhook response
        
        return respond(200, {
            'message': 'Webhook received and processed successfully',
            's3_location': f"s3://{bucket_name}/{s3_key}"
        })
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return respond(500, {'message': f'Error processing webhook: {str(e)}'})

def process_transaction_data(payload):
    """
    Process transaction data from webhook payload
    """
    transformed = []
    
    # Check if payload is a list or needs to be wrapped in a list
    transactions = payload if isinstance(payload, list) else [payload]
    
    for tx in transactions:
        # Handle case where this might be a nested list
        if isinstance(tx, list) and len(tx) > 0:
            tx = tx[0]
        
        # Get tokenTransfers if available
        token_transfers = tx.get("tokenTransfers", [])
        if not token_transfers:
            logger.warning(f"No tokenTransfers found in transaction: {tx.get('signature', 'unknown')}")
            continue
            
        # Extract first and last token transfer
        first_tt = token_transfers[0]
        last_tt = token_transfers[-1]
        
        # Convert timestamp
        ts = tx.get("timestamp")
        ts_str = None
        if ts:
            try:
                # Handle timestamp as seconds since epoch
                if isinstance(ts, (int, float)):
                    ts_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                # Handle timestamp as string
                elif isinstance(ts, str):
                    ts_str = ts
            except Exception as e:
                logger.warning(f"Error parsing timestamp: {e}")
        
        # Create transformed record
        transformed_record = {
            "user_address": first_tt.get("fromUserAccount"),
            "swapfromtoken": first_tt.get("mint"),
            "swapfromamount": first_tt.get("tokenAmount"),
            "swaptotoken": last_tt.get("mint"),
            "swaptoamount": last_tt.get("tokenAmount"),
            "signature": tx.get("signature"),
            "source": tx.get("source"),
            "timestamp": ts_str,
        }
        
        # Filter out PUMP_FUN source as in your DAG logic
        if transformed_record.get("source") != "PUMP_FUN":
            transformed.append(transformed_record)
    
    return transformed

def respond(status_code, body):
    """
    Create API Gateway response
    """
    return {
        'statusCode': status_code,
        'body': json.dumps(body),
        'headers': {
            'Content-Type': 'application/json',
        }
    }