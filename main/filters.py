import django_filters
from .models import Transaction, Budget


class TransactionFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    is_recurring = django_filters.BooleanFilter(
        field_name='recurring_entry',
        lookup_expr='isnull',
        exclude=True
    )

    class Meta:
        model = Transaction
        fields = ['transaction_type', 'category', 'date', 'start_date', 'end_date', 'min_amount', 'max_amount', 'is_recurring']


class BudgetFilter(django_filters.FilterSet):
    class Meta:
        model = Budget
        fields = ['category', 'month', 'year']
