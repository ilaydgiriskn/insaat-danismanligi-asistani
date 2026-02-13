# Barter_v2 – Güllüoğlu İnşaat AI Emlak Asistanı
## 📖 İçindekiler
- [Proje Hakkında](#-proje-hakkında)
- [Mimari](#️-mimari)
- [Teknoloji Stack](#-teknoloji-stack)
- [Proje Yapısı](#-proje-yapısı)
- [Kurulum](#-kurulum)
  - [Docker ile Kurulum](#docker-ile-kurulum-önerilen)
  - [Manuel Kurulum](#manuel-kurulum-geliştirme-için)
- [Kullanım](#-kullanım)
- [API Dokümantasyonu](#-api-dokümantasyonu)
- [Geliştirme](#-geliştirme)
- [Sorun Giderme](#️-sorun-giderme)
---
## 🎯 Proje Hakkında
**Barter_v2**, Güllüoğlu İnşaat için geliştirilmiş yapay zeka destekli emlak danışmanı uygulamasıdır. Kullanıcılarla doğal dilde sohbet eder, ihtiyaç analizi yapar ve profesyonel PDF raporlar oluşturur.
### Temel Özellikler
- 🤖 **AI-Powered Conversation**: OpenAI GPT-4 ile doğal dil işleme
- 📊 **Structured Data Collection**: 18 predefined question ile sistematik bilgi toplama
- 🧠 **Smart State Management**: Conversation state machine ile akış kontrolü
- 📄 **PDF Report Generation**: Müşteri profili ve analiz raporu
- 📧 **Email Integration**: Otomatik rapor gönderimi
- 💾 **PostgreSQL Database**: Async SQLAlchemy ile veri yönetimi
- 🔄 **Real-time Chat**: WebSocket benzeri akışkan sohbet deneyimi
---
## 🏗️ Mimari
Proje **Clean Architecture** prensiplerine göre yapılandırılmıştır:
```
┌─────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Chat Router  │  │ Health Check │  │ Debug Routes │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Application Layer (Business Logic)          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ChatHandler: Main orchestrator                   │   │
│  │  ├─ QuestionTracker: Question flow management    │   │
│  │  ├─ StateMachine: Conversation state control     │   │
│  │  ├─ Prompts: AI system instructions              │   │
│  │  └─ SummaryManager: Conversation summarization   │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Domain Layer (Models)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ UserProfile  │  │ ChatMessage  │  │ LLMResponse  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│         Infrastructure Layer (External Services)         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ PostgreSQL   │  │ OpenAI LLM   │  │ SMTP Email   │  │
│  │ (AsyncPG)    │  │ (LangChain)  │  │ (Reports)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │ PDF Generator│  │ Analytics    │                    │
│  │ (ReportLab)  │  │ Logger       │                    │
│  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```
### Katman Açıklamaları
#### 1. **API Layer** (`src/api/`)
- FastAPI router'ları
- HTTP endpoint tanımları
- Request/Response validation (Pydantic)
#### 2. **Application Layer** (`src/application/`)
- **`chat_handler.py`**: Ana orkestratör, tüm akışı yönetir
- **`prompts.py`**: AI system role ve conversation rules
- **`state_machine.py`**: Conversation state transitions
- **`question_tracker.py`**: 18 soru akış kontrolü
- **`summary_manager.py`**: Conversation memory management
#### 3. **Domain Layer** (`src/domain/`)
- **`models.py`**: Core business entities (UserProfile, ChatMessage, etc.)
- Business logic ve validation rules
#### 4. **Infrastructure Layer** (`src/infrastructure/`)
- **`database/`**: PostgreSQL connection ve models
- **`llm_client.py`**: OpenAI/LangChain integration
- **`pdf_generator.py`**: ReportLab ile PDF oluşturma
- **`email_service.py`**: SMTP email gönderimi
- **`analytics_logger.py`**: Interaction tracking
#### 5. **Tools Layer** (`src/tools/`)
- **`extraction/`**: LLM function calling ile structured data extraction
- **`placeholders/`**: Future tool implementations (property search, mortgage calc, etc.)
---
## 🛠 Teknoloji Stack
### Backend
| Kategori | Teknoloji | Versiyon | Kullanım Amacı |
|----------|-----------|----------|----------------|
| **Framework** | FastAPI | 0.115.1 | Web API framework |
| **ASGI Server** | Uvicorn | 0.32.0 | Production server |
| **Database** | PostgreSQL | 16 | Ana veritabanı |
| **ORM** | SQLAlchemy | 2.0.36 | Async database ORM |
| **DB Driver** | AsyncPG | 0.30.0 | PostgreSQL async driver |
| **AI Framework** | LangChain | 0.3.7 | LLM orchestration |
| **LLM Provider** | OpenAI | 1.54.4 | GPT-4 API |
| **PDF Generation** | ReportLab | 4.2.5 | Customer reports |
| **Validation** | Pydantic | 2.9.2 | Data validation |
| **Testing** | Pytest | 8.3.4 | Unit/integration tests |
### Frontend
- **React** (Vite)
- **Axios** (HTTP client)
- Modern CSS (responsive design)
### DevOps
- **Docker** & **Docker Compose**
- **PostgreSQL 16 Alpine**
- **pgAdmin 4** (database management)
---
## 📁 Proje Yapısı
```
Barter_v2/
├── backend_v2/                     # Python Backend
│   ├── src/
│   │   ├── api/                    # FastAPI Routes
│   │   │   └── chat_router.py      # Chat endpoints
│   │   ├── application/            # Business Logic
│   │   │   ├── chat_handler.py     # Main orchestrator
│   │   │   ├── prompts.py          # AI system prompts
│   │   │   ├── state_machine.py    # State management
│   │   │   ├── question_tracker.py # Question flow
│   │   │   └── summary_manager.py  # Memory management
│   │   ├── domain/                 # Core Models
│   │   │   └── models.py           # UserProfile, ChatMessage, etc.
│   │   ├── infrastructure/         # External Services
│   │   │   ├── database/           # PostgreSQL setup
│   │   │   ├── llm_client.py       # OpenAI integration
│   │   │   ├── pdf_generator.py    # Report generation
│   │   │   ├── email_service.py    # SMTP service
│   │   │   └── analytics_logger.py # Tracking
│   │   ├── tools/                  # LLM Tools
│   │   │   ├── extraction/         # Data extraction tool
│   │   │   └── placeholders/       # Future tools
│   │   ├── config.py               # Settings management
│   │   └── main.py                 # FastAPI app entry
│   ├── tests/                      # Test suite
│   ├── customer_reports/           # Generated PDFs
│   ├── requirements.txt            # Python dependencies
│   ├── Dockerfile                  # Backend container
│   └── .env                        # Environment variables (CREATE THIS)
├── frontend/                       # React Frontend
│   ├── src/
│   │   ├── App.jsx                 # Main component
│   │   ├── services/api.js         # API client
│   │   └── assets/                 # Images, styles
│   ├── Dockerfile                  # Frontend container
│   └── package.json                # Node dependencies
├── docker-compose.yml              # Multi-container orchestration
└── README.md                       # This file
```
---
## 🚀 Kurulum
### Gereksinimler
- **Docker Desktop** (v20.10+) - [İndir](https://www.docker.com/products/docker-desktop/)
- **Git**
- **OpenAI API Key** - [Buradan alın](https://platform.openai.com/api-keys)
### Docker ile Kurulum (Önerilen)
#### 1. Projeyi Klonlayın
```bash
git clone <repository-url>
cd Barter_v2
```
#### 2. Environment Variables Ayarlayın
`backend_v2/.env` dosyası oluşturun:
```ini
# ============================================
# OPENAI CONFIGURATION (ZORUNLU)
# ============================================
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
LLM_CHAT_TEMPERATURE=0.7
LLM_CHAT_MAX_TOKENS=512
LLM_ANALYSIS_TEMPERATURE=0.3
LLM_ANALYSIS_MAX_TOKENS=1024
# ============================================
# DATABASE (Docker için değiştirmeyin)
# ============================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/barter_db
# ============================================
# EMAIL CONFIGURATION (Rapor gönderimi için)
# ============================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_RECIPIENT=recipient@company.com
# ============================================
# APPLICATION SETTINGS
# ============================================
APP_NAME=Güllüoğlu AI Emlak Asistanı
DEBUG=True
CORS_ORIGINS=["http://localhost","http://localhost:5173"]
```
#### 3. Docker Container'ları Başlatın
```bash
docker-compose up -d --build
```
#### 4. Servisleri Kontrol Edin
```bash
docker-compose ps
```
Çıktı şöyle olmalı:
```
NAME                    STATUS          PORTS
barter_postgres         Up              0.0.0.0:5432->5432/tcp
barter_pgadmin          Up              0.0.0.0:5050->80/tcp
barter_v2-backend-1     Up              0.0.0.0:8000->8000/tcp
barter_v2-frontend-1    Up              0.0.0.0:80->80/tcp
```
#### 5. Erişim Noktaları
- **Frontend (Chat UI)**: http://localhost
- **Backend API Docs**: http://localhost:8000/docs
- **Backend Health**: http://localhost:8000/api/health
- **pgAdmin (DB Management)**: http://localhost:5050
  - Email: `admin@barter.com`
  - Password: `admin`
---
### Manuel Kurulum (Geliştirme için)
#### Backend
```bash
cd backend_v2
# Virtual environment oluştur
python -m venv venv
venv\\Scripts\\activate  # Windows
# source venv/bin/activate  # Linux/Mac
# Dependencies kur
pip install -r requirements.txt
# .env dosyasını oluştur (yukarıdaki şablonu kullan)
# DATABASE_URL'i local PostgreSQL için değiştir:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/barter_db
# Sunucuyu başlat
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --app-dir src
```
#### Frontend
```bash
cd frontend
# Dependencies kur
npm install
# Development server başlat
npm run dev
```
---
## 💬 Kullanım
### 1. Frontend'den Sohbet
1. http://localhost adresine gidin
2. "Merhaba" yazarak sohbete başlayın
3. AI asistan size 18 soru soracak:
   - İsim/Soyisim
   - Konum bilgileri (şu anki şehir, hedef şehir/ilçe)
   - Meslek
   - Yatırım/Oturum tercihi
   - Oda sayısı
   - Medeni hal, çocuk durumu
   - Sosyal alanlar
   - Finansal bilgiler (gelir, birikim, kredi, takas, bütçe)
   - İletişim bilgileri
### 2. API Üzerinden Kullanım
```bash
curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "session_id": "user-123",
    "message": "Merhaba, ev arıyorum"
  }'
```
Response:
```json
{
  "response": "Merhaba! Ben Güllüoğlu İnşaat'tan emlak danışmanınızım...",
  "is_complete": false
}
```
---
## 📡 API Dokümantasyonu
### Endpoints
#### 1. Chat
**POST** `/api/chat`
Request:
```json
{
  "session_id": "unique-session-id",
  "message": "Kullanıcı mesajı"
}
```
Response:
```json
{
  "response": "AI yanıtı",
  "is_complete": false  // Konuşma tamamlandı mı?
}
```
#### 2. Chat History
**GET** `/api/chat/history/{session_id}`
Response:
```json
{
  "found": true,
  "messages": [
    {
      "role": "user",
      "content": "Merhaba",
      "timestamp": "2024-01-01T12:00:00"
    }
  ]
}
```
#### 3. Health Check
**GET** `/api/health`
Response:
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```
#### 4. Debug Endpoints (Development)
- **GET** `/api/debug/email-config` - Email yapılandırmasını kontrol et
- **POST** `/api/debug/test-email` - Test email gönder
---
## 🔧 Geliştirme
### Code Hot Reload
Docker Compose, backend kodunda değişiklik yaptığınızda otomatik reload yapar:
```yaml
volumes:
  - ./backend_v2/src:/app/src  # Hot reload aktif
```
### Database Migration (Alembic)
```bash
# Migration oluştur
alembic revision --autogenerate -m "description"
# Migration uygula
alembic upgrade head
```
### Testing
```bash
cd backend_v2
pytest
```
### Logs İzleme
```bash
# Tüm servislerin logları
docker-compose logs -f
# Sadece backend
docker-compose logs -f backend
# Son 100 satır
docker-compose logs --tail=100 backend
```
---
## ⚠️ Sorun Giderme
### 1. Port Çakışması
**Hata**: `Bind for 0.0.0.0:8000 failed: port is already allocated`
**Çözüm**:
```bash
# Windows'ta portu kullanan process'i bul
netstat -ano | findstr :8000
# Process'i kapat
taskkill /PID <process-id> /F
# Veya docker-compose.yml'de portu değiştir
ports:
  - "8001:8000"  # 8000 yerine 8001 kullan
```
### 2. Database Bağlantı Hatası
**Hata**: `Is the server running on host "postgres"?`
**Çözüm**:
```bash
# PostgreSQL container'ının hazır olmasını bekleyin
docker-compose logs postgres
# Backend'i yeniden başlatın
docker restart barter_v2-backend-1
```
### 3. Eski Kod Çalışıyor
**Çözüm**: Docker cache'i temizleyin
```bash
docker-compose down
docker system prune -a  # DİKKAT: Tüm kullanılmayan imajları siler
docker-compose up -d --build
```
### 4. .env Dosyası Algılanmıyor
**Kontrol**:
- Dosya yolu: `backend_v2/.env` (ana klasörde değil!)
- Dosya adı: `.env` (başında nokta var!)
- Encoding: UTF-8
### 5. OpenAI API Hatası
**Hata**: `AuthenticationError: Incorrect API key`
**Çözüm**:
- API key'i kontrol edin: https://platform.openai.com/api-keys
- `.env` dosyasında `OPENAI_API_KEY` değişkenini güncelleyin
- Container'ı yeniden başlatın: `docker-compose restart backend`
---
## 📝 Notlar
- **Production Deployment**: `DEBUG=False` yapın ve güvenli şifreler kullanın
- **Email**: Gmail kullanıyorsanız "App Password" oluşturun (2FA gerekli)
- **Database Backup**: `docker exec barter_postgres pg_dump -U postgres barter_db > backup.sql`
- **Performance**: Production'da `LLM_CHAT_MAX_TOKENS` değerini optimize edin
---
## 📄 Lisans
Proprietary - Güllüoğlu İnşaat
---
