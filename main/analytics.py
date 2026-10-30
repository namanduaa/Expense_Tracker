from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
from django.db.models import (
    Sum,
    Count,
    Avg,
    Max,
    Min,
    Q,
    Value,
    DecimalField,
)
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from .models import Transaction, Category, Budget


def get_monthly_summary(user, year=None, month=None):
    """
    Computes spending and income summary for a given month and year using Django ORM aggregate().
    
    Resume highlight:
    'Generated monthly spending summaries and category-wise breakdowns using Django ORM aggregate() and annotate()'
    """
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    qs = Transaction.objects.filter(
        user=user,
        date__year=year,
        date__month=month
    )

    # Explicit use of Django ORM aggregate()
    summary = qs.aggregate(
        total_income=Coalesce(
            Sum('amount', filter=Q(transaction_type='INCOME')),
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        total_expense=Coalesce(
            Sum('amount', filter=Q(transaction_type='EXPENSE')),
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        income_count=Count('id', filter=Q(transaction_type='INCOME')),
        expense_count=Count('id', filter=Q(transaction_type='EXPENSE')),
        total_transactions=Count('id'),
        avg_expense=Coalesce(
            Avg('amount', filter=Q(transaction_type='EXPENSE')),
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        max_expense=Coalesce(
            Max('amount', filter=Q(transaction_type='EXPENSE')),
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        min_expense=Coalesce(
            Min('amount', filter=Q(transaction_type='EXPENSE')),
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
    )

    total_income = summary['total_income']
    total_expense = summary['total_expense']
    net_savings = total_income - total_expense
    savings_rate = (
        round((net_savings / total_income) * Decimal('100.00'), 2)
        if total_income > 0
        else Decimal('0.00')
    )

    return {
        'year': year,
        'month': month,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_savings': net_savings,
        'savings_rate': savings_rate,
        'total_transactions': summary['total_transactions'],
        'income_count': summary['income_count'],
        'expense_count': summary['expense_count'],
        'avg_expense': round(summary['avg_expense'], 2),
        'max_expense': summary['max_expense'],
        'min_expense': summary['min_expense'],
    }


def get_category_breakdown(user, year=None, month=None):
    """
    Computes category-wise expense breakdown using Django ORM annotate().
    
    Resume highlight:
    'category-wise breakdowns using Django ORM aggregate() and annotate()'
    """
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    qs = Transaction.objects.filter(
        user=user,
        transaction_type='EXPENSE',
        date__year=year,
        date__month=month
    )

    # 1. Total expense for the month via aggregate() to calculate percentages
    total_expense = qs.aggregate(
        total=Coalesce(Sum('amount'), Value(Decimal('0.00'), output_field=DecimalField()))
    )['total']

    # 2. Category-wise aggregation via annotate()
    annotated_breakdown = (
        qs.values(
            'category__id',
            'category__name',
            'category__color',
            'category__icon'
        )
        .annotate(
            total_spent=Sum('amount'),
            transaction_count=Count('id'),
            avg_transaction=Avg('amount')
        )
        .order_by('-total_spent')
    )

    # Also fetch budgets for this month to include budget limits and status
    user_budgets = {
        b.category_id: b.amount_limit
        for b in Budget.objects.filter(user=user, year=year, month=month)
    }

    results = []
    for item in annotated_breakdown:
        cat_id = item['category__id']
        cat_name = item['category__name'] or 'Uncategorized'
        spent = item['total_spent']
        percentage = (
            round((spent / total_expense) * Decimal('100.00'), 2)
            if total_expense > 0
            else Decimal('0.00')
        )
        budget_limit = user_budgets.get(cat_id)
        budget_percentage = (
            round((spent / budget_limit) * Decimal('100.00'), 2)
            if budget_limit and budget_limit > 0
            else None
        )

        results.append({
            'category_id': cat_id,
            'category_name': cat_name,
            'category_color': item['category__color'] or '#94A3B8',
            'category_icon': item['category__icon'] or 'tag',
            'total_spent': spent,
            'transaction_count': item['transaction_count'],
            'avg_transaction': round(item['avg_transaction'], 2),
            'percentage_of_total': percentage,
            'budget_limit': budget_limit,
            'budget_percentage_used': budget_percentage,
            'is_budget_exceeded': (spent > budget_limit) if budget_limit else False,
        })

    return {
        'year': year,
        'month': month,
        'total_expense': total_expense,
        'categories_count': len(results),
        'breakdown': results,
    }


def get_monthly_trends(user, months_count=6):
    """
    Computes monthly income vs expense history using TruncMonth and annotate().
    """
    from datetime import timedelta
    start_date = date.today().replace(day=1) - relativedelta(months=months_count - 1)

    trends = (
        Transaction.objects.filter(user=user, date__gte=start_date)
        .annotate(month_trunc=TruncMonth('date'))
        .values('month_trunc')
        .annotate(
            total_income=Coalesce(
                Sum('amount', filter=Q(transaction_type='INCOME')),
                Value(Decimal('0.00'), output_field=DecimalField())
            ),
            total_expense=Coalesce(
                Sum('amount', filter=Q(transaction_type='EXPENSE')),
                Value(Decimal('0.00'), output_field=DecimalField())
            ),
            count=Count('id')
        )
        .order_by('month_trunc')
    )

    formatted_trends = []
    for item in trends:
        month_dt = item['month_trunc']
        inc = item['total_income']
        exp = item['total_expense']
        formatted_trends.append({
            'year': month_dt.year,
            'month': month_dt.month,
            'label': month_dt.strftime('%b %Y'),
            'income': inc,
            'expense': exp,
            'net_savings': inc - exp,
            'transaction_count': item['count'],
        })

    return formatted_trends


def export_transactions_csv_pandas(queryset, user):
    """
    Exports a queryset of transactions to a CSV file using Pandas.
    
    Resume highlight:
    'with CSV export through Pandas.'
    """
    # Build list of dictionaries for Pandas DataFrame
    records = []
    for t in queryset.select_related('category', 'recurring_entry'):
        records.append({
            'Transaction ID': t.id,
            'Date': t.date.strftime('%Y-%m-%d'),
            'Type': t.transaction_type,
            'Category': t.category.name if t.category else 'Uncategorized',
            'Amount': float(t.amount),
            'Description': t.description,
            'Notes': t.notes,
            'Recurring Plan ID': t.recurring_entry_id or '',
            'Created At': t.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        })

    # Create Pandas DataFrame
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=[
            'Transaction ID',
            'Date',
            'Type',
            'Category',
            'Amount',
            'Description',
            'Notes',
            'Recurring Plan ID',
            'Created At',
        ])

    response = HttpResponse(content_type='text/csv')
    filename = f"transactions_{user.username}_{date.today().strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Export using Pandas
    df.to_csv(path_or_buf=response, index=False, encoding='utf-8')
    return response


def export_breakdown_csv_pandas(breakdown_data, user):
    """
    Exports category breakdown data to CSV using Pandas.
    """
    rows = []
    for item in breakdown_data['breakdown']:
        rows.append({
            'Category': item['category_name'],
            'Total Spent': float(item['total_spent']),
            'Percentage of Total Expense': f"{float(item['percentage_of_total']):.2f}%",
            'Transaction Count': item['transaction_count'],
            'Average Transaction': float(item['avg_transaction']),
            'Budget Limit': float(item['budget_limit']) if item['budget_limit'] else 'N/A',
            'Budget Used %': f"{float(item['budget_percentage_used']):.2f}%" if item['budget_percentage_used'] else 'N/A',
            'Budget Exceeded': 'YES' if item['is_budget_exceeded'] else 'NO',
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            'Category',
            'Total Spent',
            'Percentage of Total Expense',
            'Transaction Count',
            'Average Transaction',
            'Budget Limit',
            'Budget Used %',
            'Budget Exceeded',
        ])

    response = HttpResponse(content_type='text/csv')
    filename = f"category_breakdown_{user.username}_{breakdown_data['year']}_{breakdown_data['month']}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    df.to_csv(path_or_buf=response, index=False, encoding='utf-8')
    return response
