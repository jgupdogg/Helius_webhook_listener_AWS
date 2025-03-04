import json
import boto3
import os
import uuid
import logging
import datetime
import requests
from requests.auth import HTTPBasicAuth
import snowflake.connector
from snowflake.connector.errors import ProgrammingError, DatabaseError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')

# Global variable to track the time of the last DAG trigger.
last_trigger_time = None

def lambda_handler(event, context):
    """
    Lambda handler for webhook events:
    1. Stores raw data in S3
    2. Processes the data 
    3. Stores the processed data in Snowflake
    4. Triggers Airflow DAG
    """
    try:
        # Get environment variables
        bucket_name = os.environ.get('S3_BUCKET')
        snowflake_account = os.environ.get('SNOWFLAKE_ACCOUNT')
        snowflake_user = os.environ.get('SNOWFLAKE_USER')
        snowflake_password = os.environ.get('SNOWFLAKE_PASSWORD')
        snowflake_warehouse = os.environ.get('SNOWFLAKE_WAREHOUSE', 'DEV_WH')
        snowflake_database = os.environ.get('SNOWFLAKE_DATABASE', 'DEV')
        snowflake_schema = os.environ.get('SNOWFLAKE_SCHEMA', 'BRONZE')
        snowflake_role = os.environ.get('SNOWFLAKE_ROLE', 'AIRFLOW_ROLE')
        airflow_endpoint = os.environ.get('AIRFLOW_ENDPOINT', 'http://52.205.187.101:8080')
        airflow_username = os.environ.get('AIRFLOW_USERNAME', 'admin')
        airflow_password = os.environ.get('AIRFLOW_PASSWORD', 'password')
        
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
        processed_records = []
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
                
                # Insert data into Snowflake
                insert_to_snowflake(processed_records, snowflake_account, snowflake_user, 
                                    snowflake_password, snowflake_warehouse, snowflake_database,
                                    snowflake_schema, snowflake_role)
                
                # Trigger Airflow DAG
                maybe_trigger_dag(airflow_endpoint, airflow_username, airflow_password)
            else:
                logger.info("No valid records to process")
            
        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            # Continue execution - we don't want to fail the webhook response
        
        return respond(200, {
            'message': 'Webhook received and processed successfully',
            's3_location': f"s3://{bucket_name}/{s3_key}",
            'records_processed': len(processed_records)
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

def insert_to_snowflake(records, account, user, password, warehouse, database, schema, role):
    """
    Insert processed records into Snowflake
    """
    if not records:
        logger.info("No records to insert into Snowflake")
        return
    
    conn = None
    try:
        # Connect to Snowflake
        conn = snowflake.connector.connect(
            user=user,
            password=password,
            account=account,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role
        )
        
        cursor = conn.cursor()
        
        # Explicitly set role and context
        cursor.execute(f"USE ROLE {role}")
        cursor.execute(f"USE DATABASE {database}")
        cursor.execute(f"USE SCHEMA {schema}")
        
        # Insert each record into the HELIUS_SWAPS table
        inserted_count = 0
        duplicate_count = 0
        
        for record in records:
            # Prepare the SQL statement with fully qualified table name
            sql = """
            INSERT INTO DEV.BRONZE.HELIUS_SWAPS (
                USER_ADDRESS, SWAPFROMTOKEN, SWAPFROMAMOUNT, 
                SWAPTOTOKEN, SWAPTOAMOUNT, SIGNATURE, 
                SOURCE, TIMESTAMP
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            
            # Execute the SQL with the record values
            try:
                cursor.execute(sql, (
                    record.get("user_address"),
                    record.get("swapfromtoken"),
                    record.get("swapfromamount"),
                    record.get("swaptotoken"),
                    record.get("swaptoamount"),
                    record.get("signature"),
                    record.get("source"),
                    record.get("timestamp")
                ))
                
                inserted_count += 1
            except (ProgrammingError, DatabaseError) as e:
                # Check if this is a primary key violation (already exists)
                error_msg = str(e)
                if "DUPLICATE" in error_msg or "UNIQUE" in error_msg or "PRIMARY KEY" in error_msg:
                    logger.warning(f"Record with signature {record.get('signature')} already exists in Snowflake")
                    duplicate_count += 1
                else:
                    # Log the full error for other issues
                    logger.error(f"Snowflake error: {error_msg}")
                    raise
            except Exception as e:
                logger.error(f"Error inserting record: {e}")
                raise
        
        # Commit the transaction
        conn.commit()
        
        logger.info(f"Snowflake insertion summary: {inserted_count} inserted, {duplicate_count} duplicates")
    
    except Exception as e:
        logger.error(f"Error inserting into Snowflake: {str(e)}")
        raise
    finally:
        # Ensure connection is closed properly
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing Snowflake connection: {e}")

def maybe_trigger_dag(airflow_endpoint, airflow_username, airflow_password, conf={}):
    """
    Triggers the DAG only if at least one minute has passed since the last trigger.
    """
    global last_trigger_time
    now = datetime.datetime.utcnow()
    if last_trigger_time is not None and (now - last_trigger_time) < datetime.timedelta(minutes=1):
        logger.info("DAG trigger skipped: triggered less than a minute ago.")
        return
    
    last_trigger_time = now
    trigger_airflow_dag(airflow_endpoint, airflow_username, airflow_password, conf)

def trigger_airflow_dag(airflow_endpoint, airflow_username, airflow_password, conf={}):
    """
    Triggers the Airflow DAG by calling its REST API endpoint.
    """
    dag_run_endpoint = f"{airflow_endpoint}/api/v1/dags/token_activity_notification_dag/dagRuns"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Generate a unique dag_run_id with the current UTC time.
    time_str = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    dag_run_id = f"webhooktrigger{time_str}"
    
    data = {
        "dag_run_id": dag_run_id,
        "conf": conf
    }
    
    try:
        response = requests.post(
            dag_run_endpoint,
            json=data,
            headers=headers,
            auth=HTTPBasicAuth(airflow_username, airflow_password),
            timeout=10  # Add timeout to prevent hanging
        )
        
        if response.status_code in [200, 201]:
            logger.info("Successfully triggered Airflow DAG")
        else:
            logger.error("Failed to trigger Airflow DAG. Status code: %s, response: %s",
                         response.status_code, response.text)
    except Exception as e:
        logger.error("Exception while triggering Airflow DAG: %s", e)

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