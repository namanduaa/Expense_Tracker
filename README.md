# Minimal Django scaffold

This project is a simple Django app with a landing page and a GitHub-ready setup.

This repository has been updated with one more change for practice and version tracking.

## Quick start

1. Create a virtual environment and activate it:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations and start the server:

```bash
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ to view the app.

## GitHub upload

```bash
git init
git add .
git commit -m "Initial project setup"
git branch -M main
git remote add origin <your-github-repository-url>
git push -u origin main
```
