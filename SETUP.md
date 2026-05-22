# Development Setup Instructions

## Windows Setup

1. **Install Python 3.11+**
   ```powershell
   # Using Windows Package Manager
   winget install Python.Python.3.11
   ```

2. **Install PostgreSQL**
   ```powershell
   winget install PostgreSQL.PostgreSQL
   # Or download from https://www.postgresql.org/download/windows/
   ```

3. **Install Redis**
   ```powershell
   # Using Chocolatey
   choco install redis-64
   # Or use Windows Subsystem for Linux (WSL2)
   ```

4. **Setup Virtual Environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

5. **Install Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

## macOS Setup

1. **Install using Homebrew**
   ```bash
   brew install python@3.11
   brew install postgresql
   brew install redis
   ```

2. **Setup Virtual Environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Linux Setup

1. **Ubuntu/Debian**
   ```bash
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-venv
   sudo apt-get install postgresql postgresql-contrib
   sudo apt-get install redis-server
   ```

2. **Setup Virtual Environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Database Setup

### Create Database and User

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE voice_ai_db;

-- Create user
CREATE USER voice_ai_user WITH PASSWORD 'secure_password';

-- Grant privileges
ALTER ROLE voice_ai_user SET client_encoding TO 'utf8';
ALTER ROLE voice_ai_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE voice_ai_user SET default_transaction_deferrable TO on;
ALTER ROLE voice_ai_user SET default_transaction_read_only TO off;
ALTER ROLE voice_ai_user SET timezone TO 'UTC';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE voice_ai_db TO voice_ai_user;

-- Connect to database
\c voice_ai_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO voice_ai_user;
```

### Update Environment Variables

```bash
# .env
DATABASE_URL=postgresql://voice_ai_user:secure_password@localhost:5432/voice_ai_db
```

## Docker Setup

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Docker Commands

```bash
# Build image
docker build -t voice-ai-agent .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:password@db:5432/voice_ai_db \
  -e REDIS_URL=redis://redis:6379/0 \
  voice-ai-agent
```

## Environment Configuration

### .env File

```env
# API Settings
DEBUG=True
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=postgresql://voice_ai_user:secure_password@localhost:5432/voice_ai_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Whisper STT
WHISPER_MODEL=base  # tiny, base, small, medium, large

# Languages
SUPPORTED_LANGUAGES=en,es,fr,de,zh,ja,hi
DEFAULT_LANGUAGE=en

# Security
SECRET_KEY=your-super-secret-key-change-in-production
```

## Verification

### Check Installations

```bash
# Python
python --version

# PostgreSQL
psql --version

# Redis
redis-cli --version

# FFmpeg (required for Whisper)
ffmpeg -version
```

### Start Services

```bash
# Terminal 1: PostgreSQL
postgres -D /usr/local/var/postgres  # macOS
# or use Windows/Linux package managers

# Terminal 2: Redis
redis-server

# Terminal 3: FastAPI
uvicorn backend.main:app --reload
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# List appointments
curl http://localhost:8000/api/appointments/
```

## IDE Setup

### VS Code

1. Install Python extension
2. Select Python interpreter from virtual environment
3. Install Pylance for IntelliSense
4. Add to `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "[python]": {
    "editor.defaultFormatter": "ms-python.python",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### PyCharm

1. Create new project
2. Configure Python interpreter: Settings → Project → Python Interpreter
3. Select existing environment → navigate to `venv`

## Troubleshooting

### Module Import Errors

```bash
# Reinstall packages
pip install -r requirements.txt --force-reinstall
```

### PostgreSQL Connection Issues

```bash
# Check PostgreSQL service
# Windows: Services → PostgreSQL
# macOS: brew services list
# Linux: sudo systemctl status postgresql

# Test connection
psql -U voice_ai_user -d voice_ai_db -c "SELECT 1"
```

### Redis Connection Issues

```bash
# Test Redis
redis-cli ping
# Should return: PONG

# Check Redis service
redis-server --version
```

### Whisper Model Download Issues

```bash
# Pre-download model
python -c "import whisper; whisper.load_model('base')"

# Alternatively, set smaller model
# .env: WHISPER_MODEL=tiny
```

## Performance Tips

1. Use smaller Whisper model initially (`tiny` or `base`)
2. Enable Redis caching for frequent queries
3. Use connection pooling
4. Monitor with: `top`, `htop`, or `Resource Monitor`

## Next Steps

1. Review API documentation: [API_EXAMPLES.md](API_EXAMPLES.md)
2. Run tests: `pytest tests/`
3. Start development server: `uvicorn backend.main:app --reload`
4. Explore WebSocket endpoint: `ws://localhost:8000/ws/session-id`
