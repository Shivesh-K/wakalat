"""
Deployment Configuration and Scripts for ETL Pipeline

This module provides configuration and deployment scripts for setting up
the ETL pipeline on Google Cloud Platform.
"""

import os
import json
from typing import Dict, Any, List

# GCP Configuration
GCP_CONFIG = {
    "project_id": os.getenv("GCP_PROJECT_ID", "your-project-id"),
    "region": os.getenv("GCP_REGION", "us-central1"),
    "dataset_id": os.getenv("GCP_DATASET_ID", "wakalat_documents"),
    "documents_table_id": os.getenv("GCP_DOCUMENTS_TABLE_ID", "documents"),
    "credentials_path": os.getenv("GCP_CREDENTIALS_PATH"),
}

# Cloud Function Configuration
CLOUD_FUNCTION_CONFIG = {
    "name": "wakalat-etl-pipeline",
    "runtime": "python311",
    "timeout": "540s",  # 9 minutes (max for Cloud Functions)
    "memory": "1024MB",
    "environment_variables": {
        "GCP_PROJECT_ID": GCP_CONFIG["project_id"],
        "GCP_DATASET_ID": GCP_CONFIG["dataset_id"],
        "GCP_DOCUMENTS_TABLE_ID": GCP_CONFIG["documents_table_id"],
        "ETL_MAX_PAGES_PER_YEAR": "50",
        "PYTHONPATH": "/workspace/src"
    },
    "entry_point": "main"
}

# Pub/Sub Configuration
PUBSUB_CONFIG = {
    "topic_name": "wakalat-etl-trigger",
    "subscription_name": "wakalat-etl-trigger-sub"
}

# Cloud Scheduler Configuration
SCHEDULER_CONFIG = {
    "job_name": "wakalat-weekly-etl",
    "schedule": "0 2 * * 1",  # Every Monday at 2 AM UTC
    "timezone": "UTC",
    "description": "Weekly ETL pipeline for Wakalat document retrieval",
    "message_body": {
        "message": "Weekly ETL pipeline execution",
        "max_pages_per_year": 50,
        "max_documents_per_run": 1000
    }
}


def generate_deploy_script() -> str:
    """
    Generate a deployment script for setting up the ETL pipeline.

    Returns:
        Bash script content for deployment
    """
    script = f'''#!/bin/bash
# Deployment script for Wakalat ETL Pipeline
# Run this script from the project root directory

set -e  # Exit on any error

PROJECT_ID="{GCP_CONFIG["project_id"]}"
REGION="{GCP_CONFIG["region"]}"
FUNCTION_NAME="{CLOUD_FUNCTION_CONFIG["name"]}"
TOPIC_NAME="{PUBSUB_CONFIG["topic_name"]}"
JOB_NAME="{SCHEDULER_CONFIG["job_name"]}"
DATASET_ID="{GCP_CONFIG["dataset_id"]}"

echo "🚀 Starting Wakalat ETL Pipeline deployment..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

echo "🔐 Setting up project configuration..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable \
    cloudfunctions.googleapis.com \
    cloudscheduler.googleapis.com \
    pubsub.googleapis.com \
    bigquery.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com

# Create BigQuery dataset if it doesn't exist
echo "🗄️  Creating BigQuery dataset..."
bq show --dataset $PROJECT_ID:$DATASET_ID 2>/dev/null || \
bq mk --dataset \
    --description "Wakalat document retrieval system dataset" \
    --location=US \
    $PROJECT_ID:$DATASET_ID

# Create Pub/Sub topic
echo "📢 Creating Pub/Sub topic..."
gcloud pubsub topics create $TOPIC_NAME 2>/dev/null || \
echo "Topic $TOPIC_NAME already exists"

# Deploy Cloud Function
echo "☁️  Deploying Cloud Function..."
gcloud functions deploy $FUNCTION_NAME \
    --runtime=python311 \
    --trigger-topic=$TOPIC_NAME \
    --entry-point=main \
    --source=./src/etl \
    --timeout={CLOUD_FUNCTION_CONFIG["timeout"]} \
    --memory={CLOUD_FUNCTION_CONFIG["memory"]} \
    --region=$REGION \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_DATASET_ID=$DATASET_ID,GCP_DOCUMENTS_TABLE_ID={GCP_CONFIG["documents_table_id"]},ETL_MAX_PAGES_PER_YEAR=50"

# Create Cloud Scheduler job
echo "⏰ Creating Cloud Scheduler job..."
gcloud scheduler jobs create pubsub $JOB_NAME \
    --schedule="{SCHEDULER_CONFIG["schedule"]}" \
    --topic=$TOPIC_NAME \
    --message-body='{{
        "message": "Weekly ETL pipeline execution",
        "max_pages_per_year": 50,
        "max_documents_per_run": 1000
    }}' \
    --time-zone="{SCHEDULER_CONFIG["timezone"]}" \
    --description="{SCHEDULER_CONFIG["description"]}" \
    --location=$REGION \
    2>/dev/null || echo "Scheduler job $JOB_NAME already exists"

echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Summary:"
echo "  • Cloud Function: $FUNCTION_NAME"
echo "  • Pub/Sub Topic: $TOPIC_NAME" 
echo "  • Scheduler Job: $JOB_NAME"
echo "  • Schedule: {SCHEDULER_CONFIG["schedule"]} ({SCHEDULER_CONFIG["timezone"]})"
echo "  • BigQuery Dataset: $DATASET_ID"
echo ""
echo "🧪 To test the function manually:"
echo "  gcloud scheduler jobs run $JOB_NAME --location=$REGION"
echo ""
echo "📊 To check function logs:"
echo "  gcloud functions logs read $FUNCTION_NAME --region=$REGION"
'''

    return script


def generate_requirements_txt() -> str:
    """
    Generate requirements.txt file for the Cloud Function.

    Returns:
        Requirements.txt content
    """
    requirements = '''# Core dependencies from your existing codebase
google-cloud-bigquery>=3.11.4
google-cloud-scheduler>=2.13.3
google-cloud-pubsub>=2.18.1
requests>=2.31.0
beautifulsoup4>=4.12.2
python-dotenv>=1.0.0

# Cloud Function framework
functions-framework>=3.5.0

# Additional utilities
python-dateutil>=2.8.2
'''

    return requirements


def generate_main_py() -> str:
    """
    Generate main.py file for Cloud Function deployment.

    This creates a simplified main.py that imports and calls
    the handler from your ETL package.

    Returns:
        main.py content
    """
    main_content = '''"""
Main entry point for Wakalat ETL Cloud Function.

This file serves as the entry point for the Cloud Function deployment.
"""

import sys
import os

# Add src directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the main function from your ETL handler
try:
    from etl.handlers.cloud_function_handler import main
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {current_dir}")
    print(f"Python path: {sys.path}")
    raise

# Export the main function for Cloud Functions runtime
__all__ = ['main']
'''

    return main_content


def generate_cloudbuild_yaml() -> str:
    """
    Generate cloudbuild.yaml for automated deployment.

    Returns:
        cloudbuild.yaml content
    """
    cloudbuild = f'''# Cloud Build configuration for Wakalat ETL Pipeline
steps:
  # Install dependencies
  - name: 'python:3.11'
    entrypoint: pip
    args: ['install', '-r', 'requirements.txt', '--user']

  # Run tests (if any)
  - name: 'python:3.11'
    entrypoint: python
    args: ['-m', 'pytest', 'tests/', '--verbose']
    env:
      - 'PYTHONPATH=/workspace/src'

  # Deploy Cloud Function
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - functions
      - deploy
      - {CLOUD_FUNCTION_CONFIG["name"]}
      - --runtime=python311
      - --trigger-topic={PUBSUB_CONFIG["topic_name"]}
      - --entry-point=main
      - --source=.
      - --timeout={CLOUD_FUNCTION_CONFIG["timeout"]}
      - --memory={CLOUD_FUNCTION_CONFIG["memory"]}
      - --region={GCP_CONFIG["region"]}
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCP_DATASET_ID={GCP_CONFIG["dataset_id"]},GCP_DOCUMENTS_TABLE_ID={GCP_CONFIG["documents_table_id"]},ETL_MAX_PAGES_PER_YEAR=50

substitutions:
  _FUNCTION_NAME: {CLOUD_FUNCTION_CONFIG["name"]}
  _TOPIC_NAME: {PUBSUB_CONFIG["topic_name"]}

options:
  logging: CLOUD_LOGGING_ONLY

timeout: 1200s  # 20 minutes
'''

    return cloudbuild


def generate_env_template() -> str:
    """
    Generate .env.template file with required environment variables.

    Returns:
        Environment template content
    """
    env_template = '''# Wakalat ETL Pipeline Environment Variables
# Copy this file to .env and fill in your values

# Google Cloud Project Configuration
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
GCP_DATASET_ID=wakalat_documents
GCP_DOCUMENTS_TABLE_ID=documents
GCP_CREDENTIALS_PATH=/path/to/service-account-key.json

# ETL Configuration  
ETL_MAX_PAGES_PER_YEAR=50

# Alert System Configuration (from your existing base package)
ALERT_SENDER_EMAIL=your-alert-email@gmail.com
ALERT_SENDER_PASSWORD=your-app-password

# Optional: Environment identifier
ENVIRONMENT=production
'''

    return env_template


def generate_terraform_config() -> str:
    """
    Generate Terraform configuration for infrastructure as code.

    Returns:
        Terraform configuration content
    """
    terraform_config = f'''# Terraform configuration for Wakalat ETL Pipeline

terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 5.0"
    }}
  }}
  required_version = ">= 1.0"
}}

provider "google" {{
  project = var.project_id
  region  = var.region
}}

variable "project_id" {{
  description = "GCP Project ID"
  type        = string
}}

variable "region" {{
  description = "GCP Region"
  type        = string
  default     = "{GCP_CONFIG["region"]}"
}}

variable "dataset_id" {{
  description = "BigQuery Dataset ID"
  type        = string
  default     = "{GCP_CONFIG["dataset_id"]}"
}}

# Enable required APIs
resource "google_project_service" "required_apis" {{
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudscheduler.googleapis.com", 
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com"
  ])

  service            = each.key
  disable_on_destroy = false
}}

# BigQuery Dataset
resource "google_bigquery_dataset" "wakalat_dataset" {{
  dataset_id    = var.dataset_id
  description   = "Wakalat document retrieval system dataset"
  location      = "US"

  depends_on = [google_project_service.required_apis]
}}

# Pub/Sub Topic
resource "google_pubsub_topic" "etl_trigger" {{
  name = "{PUBSUB_CONFIG["topic_name"]}"

  depends_on = [google_project_service.required_apis]
}}

# Cloud Scheduler Job
resource "google_cloud_scheduler_job" "weekly_etl" {{
  name        = "{SCHEDULER_CONFIG["job_name"]}"
  description = "{SCHEDULER_CONFIG["description"]}"
  schedule    = "{SCHEDULER_CONFIG["schedule"]}"
  time_zone   = "{SCHEDULER_CONFIG["timezone"]}"
  region      = var.region

  pubsub_target {{
    topic_name = google_pubsub_topic.etl_trigger.id
    data = base64encode(jsonencode({{
      message                = "Weekly ETL pipeline execution"
      max_pages_per_year    = 50
      max_documents_per_run = 1000
    }}))
  }}

  depends_on = [google_project_service.required_apis]
}}

# Storage bucket for Cloud Function source code
resource "google_storage_bucket" "function_source" {{
  name     = "${{var.project_id}}-wakalat-etl-source"
  location = "US"

  uniform_bucket_level_access = true
}}

# Outputs
output "dataset_id" {{
  value = google_bigquery_dataset.wakalat_dataset.dataset_id
}}

output "topic_name" {{
  value = google_pubsub_topic.etl_trigger.name
}}

output "scheduler_job_name" {{
  value = google_cloud_scheduler_job.weekly_etl.name
}}
'''

    return terraform_config


# Utility functions for deployment
def create_deployment_files(output_dir: str = "./deployment"):
    """
    Create all deployment files in the specified directory.

    Args:
        output_dir: Directory to create files in
    """
    import os

    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    files = {
        "deploy.sh": generate_deploy_script(),
        "requirements.txt": generate_requirements_txt(),
        "main.py": generate_main_py(),
        "cloudbuild.yaml": generate_cloudbuild_yaml(),
        ".env.template": generate_env_template(),
        "terraform/main.tf": generate_terraform_config()
    }

    for file_path, content in files.items():
        full_path = os.path.join(output_dir, file_path)

        # Create subdirectories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, 'w') as f:
            f.write(content)

        # Make shell scripts executable
        if file_path.endswith('.sh'):
            os.chmod(full_path, 0o755)

    print(f"Deployment files created in {output_dir}")
    return list(files.keys())


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "./deployment"
        created_files = create_deployment_files(output_dir)
        print(f"Created {len(created_files)} deployment files:")
        for file in created_files:
            print(f"  • {file}")
    else:
        print("Usage: python deployment_config.py generate [output_dir]")