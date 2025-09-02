# 💝 LoveLush Backend

Backend service for Lovelush application built with FastAPI.

## 🚀 Development Setup

### 📋 Prerequisites

- Python 3.11+
- pip (Python package installer)
- MongoDB (local installation or cloud instance)
- ngrok (for webhook testing)

### ⚡ Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd lovelush_backend

# Copy environment configuration
cp .env.example .env

# ⚠️ Important: Edit .env file with your configuration
# - Set up MongoDB connection
# - Configure Telegram bot token
# - Generate secure SECRET_KEY
# - Install and configure ngrok for webhook testing

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Set up development environment (installs dependencies and pre-commit hooks)
make setup
```

### 🌍 Environment Configuration

After copying `.env.example` to `.env`, you need to configure:

**🔑 Required Configuration:**

- `TELEGRAM_BOT_TOKEN` - Get from @BotFather on Telegram
- `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
- `MONGO_URI` - Your MongoDB connection string

**🌐 ngrok Setup:**
> **Why ngrok?** Used for webhook testing by creating secure tunnels to your local development server.

- Install ngrok:
  - macOS: `brew install ngrok/ngrok/ngrok`
  - Other platforms: [Download ngrok](https://ngrok.com/download)
- Sign up for a free ngrok account
- Authenticate: `ngrok config add-authtoken <your-auth-token>`
- Start tunnel: `ngrok http http://localhost:8000` (for local development)
- For multiple tunnels: `ngrok config check` and `ngrok config edit`, then add new tunnels, and use `ngrok start --all`

```bash
# Example ngrok configuration file
version: "3"
agent:
    authtoken: "<your-auth-token>"
endpoints:
  - name: miniapp
    upstream:
      url: http://localhost:8080
  - name: app
    upstream:
      url: http://localhost:8000
```

**🔧 Optional Configuration:**

- `TELEGRAM_WEBHOOK_SECRET` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `CORS_ORIGINS` - Update with your frontend URLs
- `LOG_LEVEL` - Set to DEBUG for development

### 🔧 Manual Setup

```bash
# Install with development dependencies
pip install -e .[dev]

# Install pre-commit hooks
pre-commit install
```

## 🛠️ Available Commands

Run `make help` to see all available commands:

- `make setup` - Set up development environment (recommended for first setup)
- `make install` - Install project dependencies only
- `make dev` - Install project with development dependencies
- `make lint` - Run code linting checks (isort, black)
- `make format` - Format code automatically
- `make run` - Run the development server
- `make clean` - Clean up build artifacts

## ▶️ Running the Application

```bash
# Start development server
make run

# Or manually with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or use python directly
python -m main
```

The API will be available at:

- <http://localhost:8000> - Main API
- <http://localhost:8000/docs> - Swagger UI documentation
- <http://localhost:8000/redoc> - ReDoc documentation

## 🎨 Code Formatting

This project uses `black` and `isort` for code formatting:

```bash
# Check formatting
make lint

# Auto-format code
make format
```

## 🐳 Docker

Build and run with Docker:

```bash
# Build image
docker build -t lovelush-backend .

# Run container
docker run -p 8000:8000 lovelush-backend
```

## 📋 GitHub Workflow

### 🔄 Code Merge Flow

1. **Create Feature Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes & Commit**

   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

3. **Push to Remote**

   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request**
   - Open PR from your feature branch to `dev`
   - Ensure all CI checks pass
   - Request code review

5. **Merge Process**
   - Squash and merge after approval
   - Delete feature branch after merge (automatically done by GitHub)

### 🏗️ Build Commands

**CI/CD Pipeline:**
Our GitHub workflow automatically builds and publishes Docker images:

```bash
# Automatic triggers:
# - Push to main/dev branches
# - Pull requests to dev branch
# - Semver tags (v*.*.*)
# - Manual trigger with comment: /build-image

# Images are published to GitHub Container Registry:
# ghcr.io/lovelush/lovelush_backend
```

**Manual Docker Build:**

```bash
# Build production image
docker build -t lovelush-backend:latest .

# Build with specific tag
docker build -t lovelush-backend:v1.0.0 .

# Build and push to registry
docker build -t ghcr.io/your-username/lovelush_backend:latest .
docker push ghcr.io/your-username/lovelush_backend:latest
```

**Trigger Manual Build:**

```bash
# Comment on any PR to trigger image build
# Just comment: /build-image
# This will build and push a tagged image for testing
```

**Local Development Build:**

```bash
# Install and run locally
make setup
make run

# Format and lint before committing
make format
make lint
```
