#!/usr/bin/env python3
import os
import subprocess
import json
import logging
import requests
# import helius_api_key from .env
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)



# import HELIUS_API_KEY from .env
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

def get_webhook_url_from_aws():
    """Get the webhook URL from AWS CloudFormation."""
    try:
        cmd = [
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", "helius-webhook-stack",
            "--query", "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue",
            "--output", "text"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        webhook_url = result.stdout.strip()
        
        if webhook_url:
            logger.info(f"Got webhook URL from AWS: {webhook_url}")
            return webhook_url
        else:
            logger.error("Webhook URL not found in CloudFormation outputs")
            return None
    except Exception as e:
        logger.error(f"Error getting webhook URL from AWS: {e}")
        return None

def get_existing_webhooks(api_key):
    """Retrieves all existing webhooks using the Helius API."""
    url = f"https://api.helius.xyz/v0/webhooks?api-key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            webhooks = response.json()
            logger.info(f"Retrieved {len(webhooks)} existing webhooks")
            return webhooks
        else:
            logger.error(f"Failed to get webhooks. Status code: {response.status_code}, response: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Exception while getting webhooks: {e}")
        return []

def update_webhook(webhook_id, new_url, original_data, api_key):
    """Updates only the URL of an existing Helius webhook."""
    url = f"https://api.helius.xyz/v0/webhooks/{webhook_id}?api-key={api_key}"
    
    # Create payload with original data but new URL
    payload = {
        "webhookURL": new_url,
        "transactionTypes": original_data.get("transactionTypes", ["SWAP"]),
        "accountAddresses": original_data.get("accountAddresses", []),
        "webhookType": original_data.get("webhookType", "enhanced"),
        "authHeader": original_data.get("authHeader", "")
    }
    
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            logger.info(f"Successfully updated webhook with new URL: {new_url}")
            return response.json()
        else:
            logger.error(f"Failed to update webhook. Status code: {response.status_code}, response: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception while updating webhook: {e}")
        return None

def main():
    # Get API key from environment variable
    api_key = os.getenv("HELIUS_API_KEY")
    if not api_key:
        logger.error("HELIUS_API_KEY environment variable is not set")
        return
    
    # Get new webhook URL from AWS
    new_url = get_webhook_url_from_aws()
    if not new_url:
        logger.error("Failed to get webhook URL from AWS")
        return
    
    # Get existing webhooks
    existing_webhooks = get_existing_webhooks(api_key)
    if not existing_webhooks or len(existing_webhooks) == 0:
        logger.error("No existing webhooks found")
        return
    
    # Update the first webhook with the new URL
    webhook = existing_webhooks[0]
    webhook_id = webhook.get("webhookID")
    old_url = webhook.get("webhookURL", "unknown")
    
    if webhook_id:
        logger.info(f"Updating webhook ID: {webhook_id}")
        logger.info(f"Old URL: {old_url}")
        logger.info(f"New URL: {new_url}")
        
        result = update_webhook(webhook_id, new_url, webhook, api_key)
        if result:
            logger.info("Webhook updated successfully!")
        else:
            logger.error("Failed to update webhook")
    else:
        logger.error("No webhook ID found in existing webhook data")

if __name__ == "__main__":
    main()