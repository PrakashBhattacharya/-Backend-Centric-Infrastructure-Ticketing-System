# InfraTick — Backend-Centric Infrastructure Ticketing System

A premium infrastructure ticketing system built with Flask (Backend) and Vanilla JS (Frontend). Fully deployment-ready.

## 🚀 Deployment Features
- **Unified Deployment**: Flask backend serves all frontend static files.
- **Production-Ready**: Uses Gunicorn WSGI and environment variables.
- **Docker Support**: Multi-stage build for containerized environments.
- **Centralized Config**: API URLs and database paths are globally configurable.

## 🛠️ Local Setup (Development)
1. Clone the repository.
2. `cd backend`
3. `pip install -r requirements.txt`
4. `python app.py`
5. Access the app at `http://127.0.0.1:5000`

## 🐳 Docker Deployment
1. Build the image: `docker build -t infratick .`
2. Run the container: `docker run -p 5000:5000 infratick`

## ☁️ Production Hosting (Heroku / Render)
1. Set the following environment variables:
   - `SECRET_KEY`: A complex secret string.
   - `DEBUG`: False
2. The `Procfile` (or Render `Start Command`) should use:
   `gunicorn --bind 0.0.0.0:$PORT backend.wsgi:app`

## 🔑 Admin Credentials
- **Email**: manik102@gmail.com
- **Password**: 123456
