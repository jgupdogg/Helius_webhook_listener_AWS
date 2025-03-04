#!/usr/bin/env python3
"""
Snowflake Connection Diagnostics - Test every aspect of the Snowflake connection
"""
import os
import logging
import snowflake.connector
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def diagnose_snowflake_connection():
    """Run comprehensive diagnostics on Snowflake connection"""
    # Get Snowflake connection parameters
    snowflake_account = os.getenv('SNOWFLAKE_ACCOUNT')
    snowflake_user = os.getenv('SNOWFLAKE_USER')
    snowflake_password = os.getenv('SNOWFLAKE_PASSWORD')
    snowflake_warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', 'DEV_WH')
    snowflake_database = os.getenv('SNOWFLAKE_DATABASE', 'DEV')
    snowflake_schema = os.getenv('SNOWFLAKE_SCHEMA', 'BRONZE')
    snowflake_role = os.getenv('SNOWFLAKE_ROLE', 'AIRFLOW_ROLE')
    
    logger.info("Starting Snowflake connection diagnostics")
    logger.info(f"Account: {snowflake_account}")
    logger.info(f"User: {snowflake_user}")
    logger.info(f"Warehouse: {snowflake_warehouse}")
    logger.info(f"Database: {snowflake_database}")
    logger.info(f"Schema: {snowflake_schema}")
    logger.info(f"Role: {snowflake_role}")
    
    try:
        # Basic connection test
        logger.info("Attempting to connect to Snowflake...")
        conn = snowflake.connector.connect(
            user=snowflake_user,
            password=snowflake_password,
            account=snowflake_account,
            warehouse=snowflake_warehouse,
            role=snowflake_role  # Note: not specifying database or schema initially
        )
        logger.info("✅ Connected to Snowflake successfully!")
        
        cursor = conn.cursor()
        
        # Test 1: Check current session details
        logger.info("\n--- CHECKING SESSION DETAILS ---")
        cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
        user_role_wh = cursor.fetchone()
        logger.info(f"Current User: {user_role_wh[0]}")
        logger.info(f"Current Role: {user_role_wh[1]}")
        logger.info(f"Current Warehouse: {user_role_wh[2]}")
        
        # Test 2: Check user's roles
        logger.info("\n--- CHECKING USER ROLES ---")
        cursor.execute(f"SHOW GRANTS TO USER {snowflake_user}")
        roles = cursor.fetchall()
        logger.info(f"Found {len(roles)} role grants for {snowflake_user}")
        for role in roles:
            logger.info(f"  - {role[1]}")  # Role name is typically in column 1
            
        # Test 3: Check if database exists
        logger.info("\n--- CHECKING DATABASE ACCESS ---")
        cursor.execute(f"SHOW DATABASES LIKE '{snowflake_database}'")
        databases = cursor.fetchall()
        if databases:
            logger.info(f"✅ Database '{snowflake_database}' exists")
            
            # Test 3a: Try to use the database
            try:
                cursor.execute(f"USE DATABASE {snowflake_database}")
                logger.info(f"✅ Can use database '{snowflake_database}'")
            except Exception as e:
                logger.error(f"❌ Cannot use database '{snowflake_database}': {e}")
        else:
            logger.error(f"❌ Database '{snowflake_database}' does not exist or is not accessible")
            
        # Test 4: Check if schema exists
        logger.info("\n--- CHECKING SCHEMA ACCESS ---")
        try:
            cursor.execute(f"SHOW SCHEMAS LIKE '{snowflake_schema}' IN DATABASE {snowflake_database}")
            schemas = cursor.fetchall()
            if schemas:
                logger.info(f"✅ Schema '{snowflake_schema}' exists in database '{snowflake_database}'")
                
                # Test 4a: Try to use the schema
                try:
                    cursor.execute(f"USE SCHEMA {snowflake_database}.{snowflake_schema}")
                    logger.info(f"✅ Can use schema '{snowflake_database}.{snowflake_schema}'")
                except Exception as e:
                    logger.error(f"❌ Cannot use schema '{snowflake_database}.{snowflake_schema}': {e}")
            else:
                logger.error(f"❌ Schema '{snowflake_schema}' does not exist in database '{snowflake_database}' or is not accessible")
        except Exception as e:
            logger.error(f"❌ Error checking schema: {e}")
            
        # Test 5: Check if table exists
        logger.info("\n--- CHECKING TABLE ACCESS ---")
        try:
            cursor.execute(f"SHOW TABLES LIKE 'HELIUS_SWAPS' IN SCHEMA {snowflake_database}.{snowflake_schema}")
            tables = cursor.fetchall()
            if tables:
                logger.info("✅ Table 'HELIUS_SWAPS' exists")
                logger.info("Table details:")
                for col in range(len(tables[0])):
                    logger.info(f"  Column {col}: {tables[0][col]}")
                
                # Test 5a: Check for table access permissions
                try:
                    cursor.execute(f"SHOW GRANTS ON TABLE {snowflake_database}.{snowflake_schema}.HELIUS_SWAPS")
                    grants = cursor.fetchall()
                    logger.info("Table grants:")
                    for grant in grants:
                        logger.info(f"  - Privilege: {grant[1]}, Granted to: {grant[4]}")
                except Exception as e:
                    logger.error(f"❌ Cannot check grants on table: {e}")
                    
                # Test 5b: Try to query the table
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {snowflake_database}.{snowflake_schema}.HELIUS_SWAPS")
                    count = cursor.fetchone()[0]
                    logger.info(f"✅ Can query table. Current row count: {count}")
                except Exception as e:
                    logger.error(f"❌ Cannot query table: {e}")
                    
                # Test 5c: Test describe table
                try:
                    cursor.execute(f"DESCRIBE TABLE {snowflake_database}.{snowflake_schema}.HELIUS_SWAPS")
                    columns = cursor.fetchall()
                    logger.info("Table columns:")
                    for col in columns:
                        logger.info(f"  - {col[0]}: {col[1]}")
                except Exception as e:
                    logger.error(f"❌ Cannot describe table: {e}")
            else:
                logger.error("❌ Table 'HELIUS_SWAPS' does not exist or is not accessible")
                
                # List all tables in schema to see what's available
                try:
                    cursor.execute(f"SHOW TABLES IN SCHEMA {snowflake_database}.{snowflake_schema}")
                    all_tables = cursor.fetchall()
                    logger.info(f"Found {len(all_tables)} tables in schema {snowflake_database}.{snowflake_schema}:")
                    for table in all_tables:
                        logger.info(f"  - {table[1]}")  # Table name is typically in column 1
                except Exception as e:
                    logger.error(f"❌ Cannot list tables in schema: {e}")
        except Exception as e:
            logger.error(f"❌ Error checking table: {e}")
            
        # Test 6: Try creating a temporary table to test write permissions
        logger.info("\n--- TESTING WRITE PERMISSIONS ---")
        try:
            # First drop the temp table if it exists
            cursor.execute(f"DROP TABLE IF EXISTS {snowflake_database}.{snowflake_schema}.TEST_TEMP_TABLE")
            
            # Create a temp table
            cursor.execute(f"""
            CREATE TEMPORARY TABLE {snowflake_database}.{snowflake_schema}.TEST_TEMP_TABLE (
                ID NUMBER,
                NAME STRING
            )
            """)
            logger.info("✅ Successfully created temporary table")
            
            # Insert a row
            cursor.execute(f"""
            INSERT INTO {snowflake_database}.{snowflake_schema}.TEST_TEMP_TABLE (ID, NAME)
            VALUES (1, 'Test')
            """)
            logger.info("✅ Successfully inserted data into temporary table")
            
            # Clean up
            cursor.execute(f"DROP TABLE IF EXISTS {snowflake_database}.{snowflake_schema}.TEST_TEMP_TABLE")
            logger.info("✅ Successfully dropped temporary table")
        except Exception as e:
            logger.error(f"❌ Error testing write permissions: {e}")
        
        # Close the connection
        cursor.close()
        conn.close()
        logger.info("\nDiagnostics complete!")
        
    except Exception as e:
        logger.error(f"❌ Error during diagnostics: {e}")

if __name__ == "__main__":
    diagnose_snowflake_connection()