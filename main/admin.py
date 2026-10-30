from django.contrib import admin
from .models import Category, Transaction, RecurringEntry, Budget


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'user', 'color', 'created_at')
    list_filter = ('category_type', 'user')
    search_fields = ('name', 'user__username')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'transaction_type', 'amount', 'category', 'date', 'description')
    list_filter = ('transaction_type', 'date', 'category', 'user')
    search_fields = ('description', 'notes', 'user__username', 'category__name')
    date_hierarchy = 'date'


@admin.register(RecurringEntry)
class RecurringEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'user', 'transaction_type', 'amount', 'frequency', 'next_date', 'is_active')
    list_filter = ('frequency', 'is_active', 'transaction_type', 'user')
    search_fields = ('description', 'user__username')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'amount_limit', 'month', 'year', 'spent_amount', 'remaining_amount', 'is_exceeded')
    list_filter = ('year', 'month', 'user')
    search_fields = ('category__name', 'user__username')
