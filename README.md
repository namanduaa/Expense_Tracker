# Personal Expense Tracker API

> **Tech Stack:** Python, Django, Django REST Framework, PostgreSQL, JWT, Pandas

A REST API for tracking personal income and expenses, with categories, recurring entries, and budget limits per category. Secured endpoints with JWT authentication so each user can only read and modify their own transactions and budgets. Generates monthly spending summaries and category-wise breakdowns using Django ORM `aggregate()` and `annotate()`, with CSV export through Pandas.

---

## 🚀 Key Highlights & Resume Features

* **Income & Expense Tracking:** CRUD operations for transactions with decimal precision, filtering by category, date range, amount, and recurring status.
* **Custom & Default Categories:** Automatically provisions standard categories on user registration (Salary, Rent, Food, Utilities, Healthcare, etc.) while allowing unlimited custom categories.
* **Recurring Entries Engine:** Define daily, weekly, monthly, or yearly recurring plans. Automatically executes transactions on due dates via API action or background management command.
* **Category Budget Limits & Alerts:** Define monthly spending limits per category. Computes spent amount, remaining budget, usage percentage, and real-time exceeded flags.
* **Strict JWT Authentication & User Isolation:** Built with `djangorestframework-simplejwt`. All querysets and mutation actions are scoped to `request.user` to ensure zero cross-tenant data leaks.
* **Django ORM `aggregate()` & `annotate()`:**
  * Uses `aggregate()` for total income, total expenses, net savings, savings rate, and average/min/max expenses.
  * Uses `annotate()` with `values('category__name')` for category-wise breakdowns and `TruncMonth('date')` for historical spending trends.
* **Pandas CSV Export:** Streams filtered transactions and category breakdown reports into clean, standard RFC 4180 CSV files using Pandas DataFrames.
* **Database Flexibility:** Supports PostgreSQL for production/staging and zero-setup SQLite for rapid local testing.
* **Interactive Live Dashboard:** Modern developer console and API documentation dashboard served at root (`/`).

---

## 🛠️ Tech Stack & Dependencies

| Component | Technology |
| :--- | :--- |
| **Backend Framework** | Python 3.13 / Django 5+ / 6.1 |
| **API Framework** | Django REST Framework (DRF) |
| **API Documentation** | Swagger UI & OpenAPI 3.0 (`drf-spectacular`), Redoc |
| **Authentication** | JWT (`djangorestframework-simplejwt`) |
| **Database** | PostgreSQL (`psycopg2-binary`) / SQLite fallback |
| **Data Processing & Export** | Pandas |
| **Filtering** | `django-filter` |
| **Task Automation** | Django Management Commands (`process_recurring`) |

---

## 📦 Quick Start Guide

### 1. Clone & Set Up Virtual Environment

```bash
# Clone repository
git clone <repository-url>
cd EXPENSE_TRACKER

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Database Configuration

By default, the application runs on SQLite with zero setup required.

To connect to **PostgreSQL**, create a `.env` file (copied from `.env.example`):
```env
USE_POSTGRES=True
DB_NAME=expense_tracker_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Launch the Server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/** to view the interactive web console and API documentation.

### 📚 Interactive Swagger & OpenAPI Documentation

* **Swagger UI:** [http://127.0.0.1:8000/swagger/](http://127.0.0.1:8000/swagger/) or [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
* **Redoc UI:** [http://127.0.0.1:8000/redoc/](http://127.0.0.1:8000/redoc/)
* **OpenAPI 3.0 Schema:** [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)

---

## 🧪 Running Automated Tests

Run the test suite verifying JWT security, user isolation, recurring entries, budget limits, ORM aggregations, and Pandas CSV exports:

```bash
python manage.py test main
```

---

## ⚡ Background Tasks & Management Commands

### Process Due Recurring Entries
To process all active recurring entries due on or before today (can be configured as a daily cron job):

```bash
python manage.py process_recurring
```

Or process entries up to a target date:
```bash
python manage.py process_recurring --date 2026-11-01
```

---

## 📡 API Endpoints Reference

### 1. Authentication (`/api/auth/`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/register/` | Register user + auto-create default categories + return JWT tokens |
| `POST` | `/api/auth/login/` | Obtain JWT Access and Refresh token pair |
| `POST` | `/api/auth/refresh/` | Refresh JWT access token |
| `GET` | `/api/auth/me/` | Authenticated user profile and transaction count |

#### Register Request Example:
```json
POST /api/auth/register/
{
  "username": "alex",
  "email": "alex@example.com",
  "password": "SecurePassword123!",
  "password_confirm": "SecurePassword123!",
  "first_name": "Alex",
  "last_name": "Dev"
}
```

---

### 2. Transactions (`/api/transactions/`)

*All requests require header:* `Authorization: Bearer <access_token>`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/transactions/` | List user transactions (supports filters) |
| `POST` | `/api/transactions/` | Create income or expense transaction |
| `GET` | `/api/transactions/{id}/` | Retrieve specific transaction |
| `PATCH` | `/api/transactions/{id}/` | Update transaction |
| `DELETE` | `/api/transactions/{id}/` | Delete transaction |
| `GET` | `/api/transactions/export-csv/` | **Export filtered transactions to CSV (Pandas)** |

#### Supported Query Filters:
* `?transaction_type=EXPENSE` or `INCOME`
* `?category=<category_id>`
* `?start_date=2026-10-01&end_date=2026-10-31`
* `?min_amount=10.00&max_amount=500.00`
* `?is_recurring=true`
* `?search=grocery`

---

### 3. Categories (`/api/categories/`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/categories/` | List user categories |
| `POST` | `/api/categories/` | Create custom category (`name`, `category_type`, `color`, `icon`) |
| `DELETE` | `/api/categories/{id}/` | Delete custom category |

---

### 4. Budgets (`/api/budgets/`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/budgets/` | List user budgets |
| `POST` | `/api/budgets/` | Set budget limit for category in a month/year |
| `GET` | `/api/budgets/status/?year=2026&month=10` | Status overview with spent amount, remaining & exceeded flags |

---

### 5. Recurring Entries (`/api/recurring/`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/recurring/` | List recurring income and expense plans |
| `POST` | `/api/recurring/` | Create recurring entry (Daily, Weekly, Monthly, Yearly) |
| `POST` | `/api/recurring/{id}/process/` | Trigger processing for single recurring entry |
| `POST` | `/api/recurring/process-all/` | Process all due recurring entries for user |

---

### 6. Analytics (`/api/analytics/`) — ORM aggregate() & annotate()

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/analytics/monthly-summary/?year=2026&month=10` | Summary using **ORM `aggregate()`** |
| `GET` | `/api/analytics/category-breakdown/?year=2026&month=10` | Breakdown using **ORM `annotate()`** |
| `GET` | `/api/analytics/category-breakdown/export-csv/?year=2026&month=10` | Export breakdown to CSV using **Pandas** |
| `GET` | `/api/analytics/trends/?months=6` | Multi-month trend using **`TruncMonth` + `annotate()`** |

#### Monthly Summary Response Sample:
```json
{
  "year": 2026,
  "month": 10,
  "total_income": "6500.00",
  "total_expense": "2350.50",
  "net_savings": "4149.50",
  "savings_rate": 63.84,
  "total_transactions": 8,
  "income_count": 1,
  "expense_count": 7,
  "avg_expense": "335.79",
  "max_expense": "1850.00",
  "min_expense": "14.50"
}
```

---

## 💡 Implementation Details: ORM Queries & Pandas

### 1. Monthly Summary (`main/analytics.py`)
```python
# Django ORM aggregate()
summary = Transaction.objects.filter(
    user=user, date__year=year, date__month=month
).aggregate(
    total_income=Coalesce(Sum('amount', filter=Q(transaction_type='INCOME')), Value(Decimal('0.00'))),
    total_expense=Coalesce(Sum('amount', filter=Q(transaction_type='EXPENSE')), Value(Decimal('0.00'))),
    total_transactions=Count('id'),
    avg_expense=Coalesce(Avg('amount', filter=Q(transaction_type='EXPENSE')), Value(Decimal('0.00'))),
    max_expense=Coalesce(Max('amount', filter=Q(transaction_type='EXPENSE')), Value(Decimal('0.00'))),
)
```

### 2. Category-Wise Breakdown (`main/analytics.py`)
```python
# Django ORM annotate()
annotated_breakdown = (
    Transaction.objects.filter(user=user, transaction_type='EXPENSE', date__year=year, date__month=month)
    .values('category__id', 'category__name', 'category__color')
    .annotate(
        total_spent=Sum('amount'),
        transaction_count=Count('id'),
        avg_transaction=Avg('amount')
    )
    .order_by('-total_spent')
)
```

### 3. Pandas CSV Export (`main/analytics.py`)
```python
import pandas as pd
from django.http import HttpResponse

def export_transactions_csv_pandas(queryset, user):
    records = [
        {
            'Transaction ID': t.id,
            'Date': t.date.strftime('%Y-%m-%d'),
            'Type': t.transaction_type,
            'Category': t.category.name if t.category else 'Uncategorized',
            'Amount': float(t.amount),
            'Description': t.description,
            'Notes': t.notes,
            'Is Recurring': 'Yes' if t.recurring_entry_id else 'No',
            'Created At': t.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        for t in queryset.select_related('category', 'recurring_entry')
    ]
    df = pd.DataFrame(records)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{user.username}.csv"'
    df.to_csv(path_or_buf=response, index=False)
    return response
```

---

## 🔒 Security & Data Isolation
- JWT token pair generation via HMAC-SHA256 (`djangorestframework-simplejwt`).
- User scoping is strictly enforced at the queryset level (`queryset.filter(user=request.user)`).
- Relational validation ensures users cannot associate transactions or budgets with foreign category IDs.
- Passwords are validated using Django's standard validators and hashed using PBKDF2 with SHA-256.
