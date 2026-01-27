# Interstellar Mare - AI Real Estate Assistant

AI-powered real estate assistant using multi-agent architecture with LangChain and FastAPI.

## Architecture

This project follows **Clean Architecture** and **Domain-Driven Design** principles:

- **Domain Layer**: Pure business logic (entities, value objects, repository interfaces)
- **Application Layer**: Use cases, agents, business workflows
- **Infrastructure Layer**: Database, LLM integration, external services
- **Presentation Layer**: FastAPI REST API

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- LangChain
- OpenAI GPT-4

**Frontend:**
- React
- Vite

## Project Structure

```
backend/
├── src/
│   ├── domain/           # Business entities and rules
│   ├── application/      # Use cases and agents
│   ├── infrastructure/   # Database, LLM, config
│   └── presentation/     # FastAPI endpoints
├── main.py              # Application entry point
└── requirements.txt
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL
- OpenAI API key

### Installation

1. Clone the repository
2. Create virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
```

5. Update `.env` with your settings:
```
OPENAI_API_KEY=your-api-key-here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/interstellar_mare
```

### Running

```bash
# Development
python main.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: http://localhost:8000

API Documentation: http://localhost:8000/docs

## API Endpoints

### Chat
- `POST /api/v1/chat/message` - Send a message and get response

### Health
- `GET /api/v1/health` - Health check

## Multi-Agent System

### Question Agent
Selects the next most relevant question to ask the user based on their profile.

### Validation Agent
Validates if the user profile has sufficient information for analysis.

### Analysis Agent
Generates property recommendations and insights based on complete user profile.

## Development

### Code Style
- Follow PEP 8
- Use type hints
- Write docstrings

### Testing
```bash
pytest
```

## License

MIT
