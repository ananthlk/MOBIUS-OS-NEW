#!/bin/bash
# =============================================================================
# MOBIUS OS - GCP DEPLOYMENT SCRIPT
# =============================================================================
#
# This script handles the complete deployment of Mobius OS to GCP.
#
# Usage:
#   ./deploy.sh setup    # First-time setup (creates Cloud SQL, secrets, etc.)
#   ./deploy.sh deploy   # Deploy the application
#   ./deploy.sh migrate  # Run migrations only
#   ./deploy.sh seed     # Seed production database
#   ./deploy.sh status   # Check deployment status
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Project ID set: gcloud config set project YOUR_PROJECT_ID
# =============================================================================

set -e

# Configuration
SERVICE_NAME="mobius-os-backend"
REGION="us-central1"
CLOUDSQL_INSTANCE="mobius-db"
DB_NAME="mobius"
DB_USER="mobius_app"

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: No project ID set. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "========================================"
echo "MOBIUS OS DEPLOYMENT"
echo "========================================"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "========================================"

# =============================================================================
# FUNCTIONS
# =============================================================================

enable_apis() {
    echo ""
    echo "--- Enabling Required APIs ---"
    gcloud services enable \
        cloudbuild.googleapis.com \
        run.googleapis.com \
        sqladmin.googleapis.com \
        secretmanager.googleapis.com \
        containerregistry.googleapis.com
    echo "✓ APIs enabled"
}

create_cloud_sql() {
    echo ""
    echo "--- Creating Cloud SQL Instance ---"
    
    # Check if instance exists
    if gcloud sql instances describe $CLOUDSQL_INSTANCE --quiet 2>/dev/null; then
        echo "✓ Cloud SQL instance already exists"
    else
        echo "Creating Cloud SQL instance (this may take several minutes)..."
        gcloud sql instances create $CLOUDSQL_INSTANCE \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region=$REGION \
            --storage-size=10GB \
            --storage-auto-increase
        echo "✓ Cloud SQL instance created"
    fi
    
    # Create database
    if gcloud sql databases describe $DB_NAME --instance=$CLOUDSQL_INSTANCE --quiet 2>/dev/null; then
        echo "✓ Database '$DB_NAME' already exists"
    else
        gcloud sql databases create $DB_NAME --instance=$CLOUDSQL_INSTANCE
        echo "✓ Database '$DB_NAME' created"
    fi
    
    # Create user (prompt for password)
    echo ""
    echo "Enter password for database user '$DB_USER':"
    read -s DB_PASSWORD
    
    if gcloud sql users describe $DB_USER --instance=$CLOUDSQL_INSTANCE --quiet 2>/dev/null; then
        echo "Updating existing user password..."
        gcloud sql users set-password $DB_USER \
            --instance=$CLOUDSQL_INSTANCE \
            --password="$DB_PASSWORD"
    else
        gcloud sql users create $DB_USER \
            --instance=$CLOUDSQL_INSTANCE \
            --password="$DB_PASSWORD"
    fi
    echo "✓ Database user configured"
    
    # Store password in Secret Manager
    echo ""
    echo "--- Storing Secrets ---"
    if gcloud secrets describe db-password --quiet 2>/dev/null; then
        echo "Updating existing db-password secret..."
        echo -n "$DB_PASSWORD" | gcloud secrets versions add db-password --data-file=-
    else
        echo -n "$DB_PASSWORD" | gcloud secrets create db-password --data-file=-
    fi
    echo "✓ Database password stored in Secret Manager"
    
    # Generate and store app secret key
    APP_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    if gcloud secrets describe app-secret-key --quiet 2>/dev/null; then
        echo "✓ App secret key already exists"
    else
        echo -n "$APP_SECRET" | gcloud secrets create app-secret-key --data-file=-
        echo "✓ App secret key created"
    fi
}

setup_iam() {
    echo ""
    echo "--- Configuring IAM Permissions ---"
    
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
    
    # Cloud Build permissions
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
        --role="roles/run.admin" --quiet
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
        --role="roles/cloudsql.client" --quiet
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" --quiet
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
        --role="roles/iam.serviceAccountUser" --quiet
    
    # Cloud Run permissions
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/cloudsql.client" --quiet
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" --quiet
    
    echo "✓ IAM permissions configured"
}

deploy() {
    echo ""
    echo "--- Deploying to Cloud Run ---"
    
    TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
    echo "Deploying version: $TAG"
    
    gcloud builds submit \
        --config cloudbuild.yaml \
        --substitutions="_TAG=$TAG"
    
    echo ""
    echo "✓ Deployment complete!"
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
        --region=$REGION \
        --format='value(status.url)' 2>/dev/null || echo "")
    
    if [ -n "$SERVICE_URL" ]; then
        echo ""
        echo "Service URL: $SERVICE_URL"
        echo "Health Check: $SERVICE_URL/health"
    fi
}

run_migrations() {
    echo ""
    echo "--- Running Database Migrations ---"
    
    # This requires Cloud SQL Proxy running locally
    echo "Make sure Cloud SQL Proxy is running:"
    echo "  cloud_sql_proxy -instances=$PROJECT_ID:$REGION:$CLOUDSQL_INSTANCE=tcp:5433 &"
    echo ""
    read -p "Press Enter when ready, or Ctrl+C to cancel..."
    
    cd backend
    DATABASE_MODE=cloud \
    POSTGRES_HOST_CLOUD=127.0.0.1 \
    POSTGRES_PORT_CLOUD=5433 \
    POSTGRES_DB_CLOUD=$DB_NAME \
    POSTGRES_USER_CLOUD=$DB_USER \
    alembic upgrade head
    cd ..
    
    echo "✓ Migrations complete"
}

seed_production() {
    echo ""
    echo "--- Seeding Production Database ---"
    
    echo "Make sure Cloud SQL Proxy is running:"
    echo "  cloud_sql_proxy -instances=$PROJECT_ID:$REGION:$CLOUDSQL_INSTANCE=tcp:5433 &"
    echo ""
    read -p "Press Enter when ready, or Ctrl+C to cancel..."
    
    cd backend
    DATABASE_MODE=cloud \
    POSTGRES_HOST_CLOUD=127.0.0.1 \
    POSTGRES_PORT_CLOUD=5433 \
    POSTGRES_DB_CLOUD=$DB_NAME \
    POSTGRES_USER_CLOUD=$DB_USER \
    python scripts/seed_production.py
    cd ..
    
    echo "✓ Seeding complete"
}

check_status() {
    echo ""
    echo "--- Deployment Status ---"
    
    # Cloud SQL
    echo ""
    echo "Cloud SQL Instance:"
    gcloud sql instances describe $CLOUDSQL_INSTANCE \
        --format='table(name,state,databaseVersion,region)' 2>/dev/null || echo "  Not found"
    
    # Cloud Run
    echo ""
    echo "Cloud Run Service:"
    gcloud run services describe $SERVICE_NAME \
        --region=$REGION \
        --format='table(metadata.name,status.conditions[0].status,status.url)' 2>/dev/null || echo "  Not deployed"
    
    # Secrets
    echo ""
    echo "Secrets:"
    gcloud secrets list --format='table(name,createTime)' 2>/dev/null | grep -E "^(NAME|db-password|app-secret)" || echo "  None configured"
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-help}" in
    setup)
        echo "Starting first-time setup..."
        enable_apis
        create_cloud_sql
        setup_iam
        echo ""
        echo "========================================"
        echo "✓ SETUP COMPLETE"
        echo "========================================"
        echo ""
        echo "Next steps:"
        echo "  1. Run: ./deploy.sh deploy"
        echo "  2. Run: ./deploy.sh seed"
        ;;
    
    deploy)
        deploy
        ;;
    
    migrate)
        run_migrations
        ;;
    
    seed)
        seed_production
        ;;
    
    status)
        check_status
        ;;
    
    help|*)
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  setup    First-time setup (Cloud SQL, secrets, IAM)"
        echo "  deploy   Deploy application to Cloud Run"
        echo "  migrate  Run database migrations (requires Cloud SQL Proxy)"
        echo "  seed     Seed production database (requires Cloud SQL Proxy)"
        echo "  status   Check deployment status"
        echo ""
        ;;
esac
