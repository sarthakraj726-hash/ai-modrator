# Development Environment Setup

## Prerequisites
- Python 3.12+
- Git
- Optional: PostgreSQL and Redis (or use automated SQLite/In-memory fallback for local dev/testing)
- Optional: Docker

## Quickstart

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/sarthakraj726-hash/ai-modrator.git
   cd ai-modrator
   ```

2. **Create and Activate Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```

5. **Apply Database Migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Run Development Server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

7. **Verify Health**:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`
   - `GET http://localhost:8000/health`
