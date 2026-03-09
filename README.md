# Prestige Realty — Multi-Agent AI System

A real estate assistant built with Claude AI, featuring a team of specialized agents coordinated by an orchestrator.

---

## Agent Architecture

```
User
  ↓
Alex (Orchestrator)
  ↓           ↓           ↓
Lisa         Max         Vera
Listing    Mortgage    Viewing
Agent       Agent       Agent
```

| Agent | Name | Responsibility |
|-------|------|----------------|
| Orchestrator | Alex | Reads user intent, routes to the right specialist |
| Listing Agent | Lisa | Lists properties, searches listings |
| Mortgage Agent | Max | Calculates mortgage estimates |
| Viewing Agent | Vera | Schedules property viewings |

---

## Features

- Natural language conversation via REST API
- Automatic routing to the right specialist agent
- Save property listings to JSON database
- Search listings by type, price, bedrooms, location
- Schedule property viewings
- Calculate mortgage payments
- Beautiful web UI included
- Auto-deploy via Railway + GitHub

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/realestate-agent.git
cd realestate-agent
```

### 2. Install dependencies
```bash
pip install flask anthropic gunicorn
```

### 3. Set your API key
```bash
export ANTHROPIC_API_KEY=your_key_here
```

### 4. Run locally
```bash
python multi-agent-realestate.py
```

Visit: `http://localhost:5000`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web chat UI |
| POST | `/chat` | Talk to the agent |
| GET | `/listings` | View all listings |
| GET | `/viewings` | View all scheduled viewings |
| GET | `/health` | System status |

### Chat Example
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-1", "message": "I want to list my apartment"}'
```

### Response
```json
{
  "reply": "[Lisa - Listing Specialist]: I'd be happy to help you list your apartment...",
  "session_id": "user-1"
}
```

---

## Test the Routing

```bash
# Routes to Lisa (Listing Agent)
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "t1", "message": "I want to list my apartment"}'

# Routes to Max (Mortgage Agent)
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "t2", "message": "Calculate mortgage for $450000, $90000 down, 30 years"}'

# Routes to Vera (Viewing Agent)
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "t3", "message": "I want to schedule a viewing"}'
```

---

## Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variable: `ANTHROPIC_API_KEY=your_key`
4. Railway auto-deploys on every `git push` ✅

---

## Project Structure

```
realestate-agent/
├── multi-agent-realestate.py   # Main app — all agents
├── templates/
│   └── index.html              # Web chat UI
├── requirements.txt            # Python dependencies
├── Procfile                    # Railway start command
├── railway.json                # Railway config
├── .gitignore                  # Ignored files
└── README.md                   # This file
```

---

## Built With

- [Claude API](https://anthropic.com) — AI backbone for all agents
- [Flask](https://flask.palletsprojects.com) — REST API framework
- [Railway](https://railway.app) — Cloud deployment
- [Gunicorn](https://gunicorn.org) — Production WSGI server

---

## License

MIT
