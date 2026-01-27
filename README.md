# Interstellar Mare - AI Real Estate Assistant

AI-powered real estate assistant using multi-agent architecture with LangChain and FastAPI.

## 🏗️ Architecture

**Clean Architecture + Domain-Driven Design**

- **Domain Layer**: Pure business logic (entities, value objects, repository interfaces)
- **Application Layer**: Use cases, agents, business workflows  
- **Infrastructure Layer**: Database, LLM integration, external services
- **Presentation Layer**: FastAPI REST API

## 🛠️ Tech Stack

**Backend:**
- Python 3.11+
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- LangChain
- OpenAI GPT-4

**DevOps:**
- Docker
- Docker Compose

## 📁 Project Structure

```
interstellar-mare/
├── backend/
│   ├── src/
│   │   ├── domain/           # Business entities and rules
│   │   ├── application/      # Use cases and agents
│   │   ├── infrastructure/   # Database, LLM, config
│   │   └── presentation/     # FastAPI endpoints
│   ├── main.py              # Application entry point
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key

### Setup

1. **Clone and configure:**
```bash
git clone <repository-url>
cd interstellar-mare
cp .env.example .env
```

2. **Add your OpenAI API key to `.env`:**
```
OPENAI_API_KEY=sk-your-key-here
```

3. **Start services:**
```bash
docker-compose up -d
```

4. **Check status:**
```bash
docker-compose ps
```

### Access

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

## 📡 API Endpoints

### Chat
```bash
POST /api/v1/chat/message
{
  "session_id": "user-123",
  "message": "Merhaba, ev arıyorum"
}
```

### Health
```bash
GET /api/v1/health
```

## 🤖 Multi-Agent System

### Question Agent
Selects the next most relevant question based on user profile.

### Validation Agent  
Validates if user profile has sufficient information for analysis.

### Analysis Agent
Generates property recommendations and insights.

## 🔧 Development

### Local Development (without Docker)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
python main.py
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

### Stop Services

```bash
docker-compose down
```

### Reset Database

```bash
docker-compose down -v
docker-compose up -d
```

## 📝 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | *required* |
| `DATABASE_URL` | PostgreSQL connection string | Auto-configured in Docker |
| `DEBUG` | Debug mode | `True` |
| `LOG_LEVEL` | Logging level | `INFO` |

## 🧪 Testing

```bash
cd backend
pytest
```

## 📄 License

MIT
