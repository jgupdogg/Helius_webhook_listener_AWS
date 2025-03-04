# helius_api.py
import os
import json
import logging
import requests
from db_helpers import fetch_addresses_from_db

def get_existing_webhooks():
    """
    Retrieves all existing webhooks using the Helius API.
    Returns a list of webhook objects.
    """
    api_key = os.getenv("HELIUS_API_KEY")
    if not api_key:
        logging.error("HELIUS_API_KEY is not set.")
        return []
    url = f"https://api.helius.xyz/v0/webhooks?api-key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            webhooks = response.json()
            logging.info("Retrieved existing webhooks: %s", webhooks)
            return webhooks
        else:
            logging.error("Failed to get webhooks. Status code: %s, response: %s",
                          response.status_code, response.text)
            return []
    except Exception as e:
        logging.error("Exception while getting webhooks: %s", e)
        return []

def create_webhook(new_url, addresses):
    """
    Creates a new Helius webhook using a POST request.
    """
    api_key = os.getenv("HELIUS_API_KEY")
    if not api_key:
        logging.error("HELIUS_API_KEY is not set.")
        return None
    url = f"https://api.helius.xyz/v0/webhooks?api-key={api_key}"
    
    transaction_types_env = os.getenv("HELIUS_TRANSACTION_TYPES", "SWAP")
    transaction_types = [x.strip() for x in transaction_types_env.split(",")]
    webhook_type = os.getenv("HELIUS_WEBHOOK_TYPE", "enhanced")
    txn_status = os.getenv("HELIUS_TXN_STATUS", "all")
    auth_header = os.getenv("HELIUS_AUTH_HEADER", "")

    payload = {
        "webhookURL": 'https://fg0tzavrei.execute-api.us-east-1.amazonaws.com/Prod/webhooks',
        "transactionTypes": transaction_types,
        "accountAddresses": addresses,  # Send as an array
        "webhookType": webhook_type,
        # "txnStatus": txn_status,
        "authHeader": auth_header
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            logging.info("Successfully created webhook.")
            return response.json()
        else:
            logging.error("Failed to create webhook. Status code: %s, response: %s",
                          response.status_code, response.text)
            return None
    except Exception as e:
        logging.error("Exception while creating webhook: %s", e)
        return None

def update_webhook(webhook_id, new_url, addresses):
    """
    Updates an existing Helius webhook using a PUT request.
    """
    api_key = os.getenv("HELIUS_API_KEY")
    if not api_key:
        logging.error("HELIUS_API_KEY is not set.")
        return None
    url = f"https://api.helius.xyz/v0/webhooks/{webhook_id}?api-key={api_key}"
    
    transaction_types_env = os.getenv("HELIUS_TRANSACTION_TYPES", "SWAP")
    transaction_types = [x.strip() for x in transaction_types_env.split(",")]
    webhook_type = os.getenv("HELIUS_WEBHOOK_TYPE", "enhanced")
    txn_status = os.getenv("HELIUS_TXN_STATUS", "all")
    auth_header = os.getenv("HELIUS_AUTH_HEADER", "")

    payload = {
        "webhookURL": 'https://fg0tzavrei.execute-api.us-east-1.amazonaws.com/Prod/webhooks',
        "transactionTypes": transaction_types,
        "accountAddresses": addresses,  # Send as an array
        "webhookType": webhook_type,
        "authHeader": auth_header
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            logging.info("Successfully updated webhook.")
            return response.json()
        else:
            logging.error("Failed to update webhook. Status code: %s, response: %s",
                          response.status_code, response.text)
            return None
    except Exception as e:
        logging.error("Exception while updating webhook: %s", e)
        return None

def update_or_create_webhook(new_url):
    """
    Uses the Helius API to retrieve existing webhooks.
    If one exists, updates it; if none exist, creates a new webhook.
    """
    addresses = fetch_addresses_from_db()
    if not addresses:
        logging.error("No addresses retrieved from the DB. Exiting.")
        return
    existing_webhooks = get_existing_webhooks()
    if existing_webhooks and len(existing_webhooks) > 0:
        webhook_id = existing_webhooks[0].get("webhookID")
        if webhook_id:
            logging.info("Updating existing webhook with ID: %s", webhook_id)
            result = update_webhook(webhook_id, new_url, addresses)
            logging.info("Webhook update result: %s", result)
        else:
            logging.error("Existing webhook found but no webhookID; creating a new webhook.")
            result = create_webhook(new_url, addresses)
            logging.info("Webhook creation result: %s", result)
    else:
        logging.info("No existing webhook found; creating a new webhook.")
        result = create_webhook(new_url, addresses)
        logging.info("Webhook creation result: %s", result)
