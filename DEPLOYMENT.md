# AI Automation Factory - Deployment Guide

This guide provides step-by-step instructions for deploying the AI Automation Factory in different environments.

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Git
- (Optional) Docker and Docker Compose for containerized deployment

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-automation-factory.git
cd ai-automation-factory
```

### 2. Set Up a Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Unix/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update it with your settings:

```bash
copy .env.example .env
```

Edit the `.env` file with your configuration:

```env
# Application Settings
APP_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite+aiosqlite:///./ai_factory.db

# AI Settings
AI_API_KEY=your-openai-api-key
DEFAULT_AI_MODEL=gpt-4

# Google Drive (Optional)
GOOGLE_DRIVE_ENABLED=False
# GOOGLE_DRIVE_CREDENTIALS=path/to/credentials.json
```

### 5. Initialize the Database

```bash
python -m models.database
```

### 6. Run the Application

```bash
uvicorn main:app --reload
```

The application will be available at `http://localhost:8000`

## Production Deployment

### 1. Set Up a Production Database

For production, use PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/ai_factory
```

### 2. Configure Gunicorn with Uvicorn Workers

Install Gunicorn:
```bash
pip install gunicorn
```

Create a Gunicorn config file `gunicorn_conf.py`:

```python
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8000"
timeout = 120
keepalive = 5
```

### 3. Run with Gunicorn

```bash
gunicorn -c gunicorn_conf.py main:app
```

## Docker Deployment

### 1. Build the Docker Image

```bash
docker build -t ai-automation-factory .
```

### 2. Run with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db/ai_factory
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:13
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=ai_factory
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  pgadmin:
    image: dpage/pgadmin4
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@example.com
      - PGADMIN_DEFAULT_PASSWORD=admin
    ports:
      - "5050:80"
    depends_on:
      - db
    restart: unless-stopped

volumes:
  postgres_data:
```

Start the services:

```bash
docker-compose up -d
```

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Application environment (development, production) | `development` |
| `DEBUG` | Enable debug mode | `False` |
| `SECRET_KEY` | Secret key for encryption | - |
| `DATABASE_URL` | Database connection URL | `sqlite+aiosqlite:///./ai_factory.db` |
| `AI_API_KEY` | OpenAI API key | - |
| `DEFAULT_AI_MODEL` | Default AI model to use | `gpt-4` |
| `GOOGLE_DRIVE_ENABLED` | Enable Google Drive integration | `False` |
| `GOOGLE_DRIVE_CREDENTIALS` | Path to Google Drive credentials | - |

## Monitoring and Maintenance

### Database Backups

For PostgreSQL, set up regular backups using `pg_dump`:

```bash
# Create backup
pg_dump -U postgres -d ai_factory > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -U postgres -d ai_factory < backup_20230101.sql
```

### Logs

Logs are stored in the `logs` directory by default. For production, consider using a log management system like ELK Stack or CloudWatch.

## Troubleshooting

### Database Connection Issues

- Verify the database server is running
- Check connection string format
- Ensure the database user has proper permissions

### AI API Issues

- Verify the API key is correct and has sufficient credits
- Check network connectivity to the AI service
- Review rate limits and quotas

### Performance Issues

- Monitor resource usage (CPU, memory, disk I/O)
- Check database query performance
- Consider scaling the application horizontally

## Support

For support, please open an issue on GitHub or contact the development team.
