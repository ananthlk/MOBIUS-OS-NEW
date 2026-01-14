# Mobius OS

AI-native, context-aware browser extension bridging financial and patient engagement with clinical care.

## Project Structure

```
Mobius OS/
├── backend/              # Flask backend server
│   ├── app/
│   │   ├── agents/      # Agent modules (BaseAgent, modes)
│   │   └── routes/      # API routes
│   └── requirements.txt
├── extension/            # Browser extension (TypeScript)
│   ├── src/
│   │   ├── components/  # 27 reusable UI components
│   │   ├── services/    # API services
│   │   └── ...
│   └── package.json
├── venv/                 # Python virtual environment (root level)
└── README.md
```

## Setup

### Backend Setup

1. Create and activate virtual environment (if not already done):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Run the Flask server:
   ```bash
   cd backend
   source ../venv/bin/activate  # Activate venv from root
   python3 app.py
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

## Development

### Backend Development

The backend uses Flask with a modular agent architecture:
- Base agent with conversation agent sub-module
- Mode-based routing (`/api/v1/modes/chat/message`)
- CORS enabled for browser extension

### Frontend Development

The frontend is a TypeScript browser extension:
- Webpack for bundling
- TypeScript for type safety
- Component-based architecture (27 reusable components)
- Currently implements chat mode

### Watch Mode (Frontend)

```bash
cd extension
npm run dev
```

This will watch for changes and rebuild automatically.

## API Endpoints

### Chat Mode

- `POST /api/v1/modes/chat/message`
  - Body: `{ "message": "string", "session_id": "string" }`
  - Returns: Chat response with replayed message and acknowledgement

## Virtual Environment

The Python virtual environment is located at the **root** of the project (`/venv/`), not in the backend directory. This allows for a unified project structure.

To activate:
```bash
source venv/bin/activate  # From root directory
```
