import os
import logging
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_snowflake_connection_string():
    """
    Construct Snowflake connection string from environment variables
    """
    # Retrieve connection parameters
    account = os.getenv('SNOWFLAKE_ACCOUNT', '')
    user = os.getenv('SNOWFLAKE_USER', '')
    password = os.getenv('SNOWFLAKE_PASSWORD', '')
    warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', 'DEV_WH')
    database = os.getenv('SNOWFLAKE_DATABASE', 'DEV')
    schema = os.getenv('SNOWFLAKE_SCHEMA', 'BRONZE')
    role = os.getenv('SNOWFLAKE_ROLE', 'AIRFLOW_ROLE')

    # Validate inputs
    if not all([account, user, password]):
        raise ValueError("Missing required Snowflake connection parameters")

    # Ensure inputs are strings
    account = str(account)
    user = str(user)
    password = str(password)

    # Construct connection string
    connection_string = (
        f"snowflake://{quote_plus(user)}:{quote_plus(password)}@"
        f"{quote_plus(account)}/{database}/{schema}?warehouse={warehouse}&role={role}"
    )
    
    return connection_string

def test_snowflake_connection():
    """
    Test Snowflake connection using SQLAlchemy
    """
    try:
        # Print out environment variables for debugging (be careful with passwords!)
        logger.info("Snowflake Connection Parameters:")
        logger.info(f"Account: {os.getenv('SNOWFLAKE_ACCOUNT')}")
        logger.info(f"User: {os.getenv('SNOWFLAKE_USER')}")
        logger.info(f"Warehouse: {os.getenv('SNOWFLAKE_WAREHOUSE', 'DEV_WH')}")
        logger.info(f"Database: {os.getenv('SNOWFLAKE_DATABASE', 'DEV')}")
        logger.info(f"Schema: {os.getenv('SNOWFLAKE_SCHEMA', 'BRONZE')}")
        logger.info(f"Role: {os.getenv('SNOWFLAKE_ROLE', 'AIRFLOW_ROLE')}")

        # Create engine with minimal connection pooling
        connection_string = get_snowflake_connection_string()
        engine = create_engine(
            connection_string, 
            pool_size=5,  # Minimal connection pool
            max_overflow=0  # Prevent creating additional connections
        )
        
        # Attempt to connect and execute a simple query
        with engine.connect() as connection:
            # Test basic connectivity
            result = connection.execute(text("SELECT CURRENT_WAREHOUSE()"))
            warehouse = result.scalar()
            logger.info(f"Successfully connected to warehouse: {warehouse}")
            
            # Test table existence and basic query
            result = connection.execute(text(
                "SELECT COUNT(*) FROM HELIUS_SWAPS"
            ))
            count = result.scalar()
            logger.info(f"Current row count in HELIUS_SWAPS: {count}")
    
    except Exception as e:
        logger.error(f"Snowflake connection error: {e}")
        # Log full traceback
        import traceback
        logger.error(traceback.format_exc())
        raise

def insert_records(records):
    """
    Insert records into Snowflake using SQLAlchemy
    
    :param records: List of dictionaries containing record data
    """
    if not records:
        logger.info("No records to insert")
        return
    
    try:
        # Create engine with minimal connection pooling
        connection_string = get_snowflake_connection_string()
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
            for record in records:
                connection.execute(insert_query, record)
            
            # Commit transaction
            connection.commit()
            
            logger.info(f"Successfully inserted {len(records)} records")
    
    except Exception as e:
        logger.error(f"Error inserting records: {e}")
        # Log full traceback
        import traceback
        logger.error(traceback.format_exc())
        raise

# Example usage
if __name__ == "__main__":
    # Use python-dotenv to load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()

    # First test connection
    test_snowflake_connection()
    
    # Example records (modify as needed)
    sample_records = [
        {
            "user_address": "example_address_1",
            "swapfromtoken": "TOKEN1",
            "swapfromamount": 100.0,
            "swaptotoken": "TOKEN2",
            "swaptoamount": 50.0,
            "signature": "sample_signature_1",
            "source": "WEBHOOK",
            "timestamp": "2024-03-05 12:00:00"
        }
    ]
    
    # Then try inserting records
    insert_records(sample_records)