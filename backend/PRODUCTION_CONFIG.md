# Mobius OS - Production Configuration Guide

## Environment Variables

Set these environment variables for production deployment (Cloud Run):

### Core Settings
```
DATABASE_MODE=cloud
FLASK_DEBUG=0
FLASK_ENV=production
SECRET_KEY=<secure-random-string-32-chars-min>
```

### PostgreSQL (Cloud SQL)
```
CLOUDSQL_CONNECTION_NAME=<project-id>:<region>:<instance-name>
POSTGRES_DB_CLOUD=mobius
POSTGRES_USER_CLOUD=mobius_app
POSTGRES_PASSWORD_CLOUD=<database-password>
```

### Firestore / GCP
```
GCP_PROJECT_ID=<project-id>
ENABLE_FIRESTORE=true
FIRESTORE_DATABASE_CLOUD=(default)
```

## GCP Setup Commands

### 1. Create Cloud SQL Instance
```bash
# Create PostgreSQL 15 instance
gcloud sql instances create mobius-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-size=10GB \
  --storage-auto-increase

# Create database
gcloud sql databases create mobius --instance=mobius-db

# Create application user
gcloud sql users create mobius_app \
  --instance=mobius-db \
  --password=YOUR_SECURE_PASSWORD
```

### 2. Store Secrets in Secret Manager
```bash
# Database password
echo -n "YOUR_SECURE_PASSWORD" | \
  gcloud secrets create db-password --data-file=-

# Flask secret key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
echo -n "YOUR_SECRET_KEY" | \
  gcloud secrets create app-secret-key --data-file=-
```

### 3. Enable Required APIs
```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com
```

### 4. Grant Permissions
```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Cloud Build service account permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Run service account permissions for Cloud SQL
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Deployment

### Manual Deployment
```bash
# From repository root
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_TAG=$(git rev-parse --short HEAD)
```

### Automatic Deployment (CI/CD)
Set up a Cloud Build trigger on push to main branch.

## Post-Deployment

### Run Initial Seed
After first deployment, seed the production database:

```bash
# Connect to Cloud SQL via proxy
cloud_sql_proxy -instances=PROJECT_ID:us-central1:mobius-db=tcp:5433 &

# Set environment and run seed
DATABASE_MODE=cloud \
POSTGRES_HOST_CLOUD=127.0.0.1 \
POSTGRES_PORT_CLOUD=5433 \
POSTGRES_DB_CLOUD=mobius \
POSTGRES_USER_CLOUD=mobius_app \
POSTGRES_PASSWORD_CLOUD=YOUR_PASSWORD \
python scripts/seed_production.py
```

### Verify Deployment
```bash
# Get service URL
gcloud run services describe mobius-os-backend --region=us-central1 --format='value(status.url)'

# Check health
curl https://YOUR_SERVICE_URL/health
```

## Migration Management

### Run Migrations Manually
```bash
# Via Cloud Build (migrations run automatically on deploy)
# Or via Cloud SQL Proxy for manual runs:

cloud_sql_proxy -instances=PROJECT_ID:us-central1:mobius-db=tcp:5433 &

DATABASE_MODE=cloud \
POSTGRES_HOST_CLOUD=127.0.0.1 \
POSTGRES_PORT_CLOUD=5433 \
alembic upgrade head
```

### Create New Migration
```bash
# Always create locally first, test, then commit
cd backend
alembic revision --autogenerate -m "description_of_changes"
```
