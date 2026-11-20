# Minimal Django scaffold

The app-specific landing page and routes have been cleared. The Django project
settings and bootstrap files remain as a starting point for a new design.

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

Start the server with `python manage.py runserver`. The root URL has no page
until you add a route and view.

## GitHub upload

```bash
git init
git add .
git commit -m "Initial project setup"
git branch -M main
git remote add origin <your-github-repository-url>
git push -u origin main
```
