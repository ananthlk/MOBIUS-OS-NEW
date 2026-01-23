# Mobius OS

AI-native, context-aware browser extension bridging financial and patient engagement with clinical care.

## Project Structure

```
Mobius OS/
├── backend/                    # Flask backend server
│   ├── app/
│   │   ├── agents/            # AI agent modules
│   │   ├── api/               # REST API endpoints
│   │   ├── models/            # SQLAlchemy models
│   │   ├── modes/             # Mini, Sidecar, Chat modes
│   │   ├── services/          # Business logic services
│   │   └── config.py          # Environment configuration
│   ├── migrations/            # Alembic database migrations
│   ├── scripts/               # Seed and utility scripts
│   ├── Dockerfile             # Cloud Run container
│   └── requirements.txt
├── extension/                  # Browser extension (TypeScript)
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   ├── services/          # API services
│   │   └── ...
│   └── package.json
├── cloudbuild.yaml            # GCP Cloud Build config
├── deploy.sh                  # Deployment automation script
└── README.md
```

## Local Development Setup

### Prerequisites

- Python 3.13+
- PostgreSQL 15+
- Node.js 18+
- gcloud CLI (for production deployment)

### Backend Setup

1. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Set up PostgreSQL:
   ```bash
   createdb mobius
   ```

4. Configure environment:
   ```bash
   # Create .env file in backend/
   cat > .env << EOF
   DATABASE_MODE=local
   POSTGRES_HOST_LOCAL=localhost
   POSTGRES_PORT_LOCAL=5432
   POSTGRES_DB_LOCAL=mobius
   POSTGRES_USER_LOCAL=postgres
   FLASK_DEBUG=1
   EOF
   ```

5. Run migrations:
   ```bash
   cd backend
   alembic upgrade head
   ```

6. Seed development data:
   ```bash
   python scripts/seed_attendance_patients.py
   ```

7. Run the server:
   ```bash
   python server.py
   ```
   
   Server runs on `http://localhost:5001`

### Frontend Setup

1. Install dependencies:
   ```bash
   cd extension
   npm install
   ```

2. Build the extension:
   ```bash
   npm run build
   ```

3. Load in Chrome:
   - Go to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `extension/dist` directory

### Watch Mode (Frontend)

```bash
cd extension
npm run dev
```

---

## Production Deployment (GCP)

### Quick Deploy

```bash
# First time setup
./deploy.sh setup

# Deploy application
./deploy.sh deploy

# Seed production database
./deploy.sh seed
```

### Manual Setup

See [backend/PRODUCTION_CONFIG.md](backend/PRODUCTION_CONFIG.md) for detailed instructions.

### Architecture

- **Cloud Run**: Containerized Flask application
- **Cloud SQL**: PostgreSQL 15 database
- **Secret Manager**: Secure credential storage
- **Cloud Build**: CI/CD pipeline

### Environment Variables (Production)

| Variable | Description |
|----------|-------------|
| `DATABASE_MODE` | Set to `cloud` for production |
| `CLOUDSQL_CONNECTION_NAME` | `project:region:instance` |
| `POSTGRES_DB_CLOUD` | Database name (default: `mobius`) |
| `POSTGRES_USER_CLOUD` | Database user |
| `POSTGRES_PASSWORD_CLOUD` | Via Secret Manager |
| `SECRET_KEY` | Flask secret key (via Secret Manager) |
| `ENABLE_FIRESTORE` | Enable Firestore integration |

---

## API Endpoints

### Core APIs

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `POST /api/v1/mini/state` | Get patient state for Mini widget |
| `POST /api/v1/sidecar/state` | Get full Sidecar state |
| `GET /api/v1/user/alerts` | Get user alerts |
| `POST /api/v1/resolution/step/:id/answer` | Submit step answer |

### Mock Pages

| Endpoint | Description |
|----------|-------------|
| `/mock-emr` | Mock EMR patient page |
| `/mock-crm` | Mock CRM scheduler page |

---

## Database Migrations

### Create New Migration
```bash
cd backend
alembic revision --autogenerate -m "description_of_changes"
```

### Run Migrations
```bash
alembic upgrade head
```

### Migration History
```bash
alembic history
```

---

## Seed Scripts

| Script | Description |
|--------|-------------|
| `seed_attendance_patients.py` | 3 attendance factor patients with L3/L4 data |
| `seed_production.py` | Production tenant, admin, sample data |
| `seed_demo.py` | Demo dataset for presentations |
| `seed_clean_start.py` | Clean database and reset |

---

## Development Notes

### Backend Architecture

- **Models**: SQLAlchemy ORM with PostgreSQL
- **Services**: Business logic layer (sidecar_state, patient_state, etc.)
- **Agents**: AI decision agents (policy, proceed, assignment, etc.)
- **Modes**: Surface-specific handlers (Mini, Sidecar, Chat)

### Data Model Layers

1. **L1 - Probability**: Payment probability calculations
2. **L2 - Resolution Plans**: Multi-step resolution workflows
3. **L3 - Plan Steps**: Individual questions/actions
4. **L4 - Evidence**: Facts and source documents

### Testing

```bash
cd backend
pytest
```

---

## License

Proprietary - Mobius Health, Inc.
