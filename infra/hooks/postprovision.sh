#!/bin/bash

set -e

# Output environment variables to .env file using azd env get-values
azd env get-values > .env

# Retrieve service names, resource group name, and other values from environment variables
resourceGroupName=$AZURE_RESOURCE_GROUP
openAiService=$AZURE_OPENAI_NAME
subscriptionId=$AZURE_SUBSCRIPTION_ID

# Ensure all required environment variables are set
if [ -z "$resourceGroupName" ] || [ -z "$openAiService" ] || [ -z "$subscriptionId" ]; then
    echo "One or more required environment variables are not set."
    echo "Ensure that AZURE_RESOURCE_GROUP, AZURE_OPENAI_NAME, AZURE_SUBSCRIPTION_ID are set."
    exit 1
fi

# Set additional environment variables expected by app
# TODO: Standardize these and remove need for setting here
azd env set AZURE_OPENAI_API_VERSION 2024-08-01-preview
azd env set REACT_APP_API_BASE_URL $WEB_SERVICE_ACA_URI
