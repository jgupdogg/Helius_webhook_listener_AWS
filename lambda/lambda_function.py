import sys
import traceback
import json
import boto3
import os
import uuid
import logging
import datetime
import requests
from requests.auth import HTTPBasicAuth
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variable to track the time of the last DAG trigger.
last_trigger_time = None

def get_snowflake_connection_string(account, user, password, warehouse, database, schema, role):
    """
    Construct Snowflake connection string
    """
    return (
        f"snowflake://{quote_plus(user)}:{quote_plus(password)}@"
        f"{quote_plus(account)}/{database}/{schema}?warehouse={warehouse}&role={role}"
    )

def insert_to_snowflake(records, account, user, password, warehouse, database, schema, role):
    """
    Insert processed records into Snowflake using SQLAlchemy
    """
    if not records:
        logger.info("No records to insert into Snowflake")
        return
    
    try:
        # Create SQLAlchemy engine
        connection_string = get_snowflake_connection_string(
            account, user, password, warehouse, database, schema, role
        )
        
        engine = create_engine(
            connection_string, 
            pool_size=5,  
            max_overflow=0  
        )
        
        # Use a single connection for multiple inserts
        with engine.connect() as connection:
            # Prepare the insert statement
            insert_query = text("""
                INSERT INTO HELIUS_SWAPS (
                    USER_ADDRESS, SWAPFROMTOKEN, SWAPFROMAMOUNT, 
                    SWAPTOTOKEN, SWAPTOAMOUNT, SIGNATURE, 
                    SOURCE, TIMESTAMP
                ) VALUES (
                    :user_address, :swapfromtoken, :swapfromamount,
                    :swaptotoken, :swaptoamount, :signature,
                    :source, :timestamp
                )
            """)
            
            # Execute batch insert
            inserted_count = 0
            duplicate_count = 0
            
            for record in records:
                try:
                    connection.execute(insert_query, record)
                    inserted_count += 1
                except Exception as e:
                    error_msg = str(e)
                    if "DUPLICATE" in error_msg or "UNIQUE" in error_msg or "PRIMARY KEY" in error_msg:
                        logger.warning(f"Record with signature {record.get('signature')} already exists")
                        duplicate_count += 1
                    else:
                        logger.error(f"Error inserting record: {error_msg}")
                        raise
            
            # Commit the transaction
            connection.commit()
            
            logger.info(f"Snowflake insertion summary: {inserted_count} inserted, {duplicate_count} duplicates")
    
    except Exception as e:
        logger.error(f"Error inserting into Snowflake: {str(e)}")
        raise

def lambda_handler(event, context):
    """
    Lambda handler for webhook events:
    1. Processes the webhook data
    2. Stores the processed data in Snowflake
    3. Triggers Airflow DAG
    """
    try:
        # Get environment variables
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

        # Process the webhook data
        processed_records = []
        try:
            # Preprocess the data
            processed_records = process_transaction_data(payload)
            
            if processed_records:
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
            traceback.print_exc()
            return respond(500, {'message': f'Error processing data: {str(e)}'})
        
        return respond(200, {
            'message': 'Webhook received and processed successfully',
            'records_processed': len(processed_records)
        })
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        traceback.print_exc()
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