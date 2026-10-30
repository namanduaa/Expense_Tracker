from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum


class Category(models.Model):
    TYPE_CHOICES = (
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
        ('BOTH', 'Both'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='EXPENSE')
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex code for charts/UI
    icon = models.CharField(max_length=50, blank=True, default='tag')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        unique_together = ('user', 'name', 'category_type')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_category_type_display()})"

    @classmethod
    def create_defaults_for_user(cls, user):
        """Creates starter categories for newly registered users."""
        default_categories = [
            # Income
            ('Salary', 'INCOME', '#10B981', 'briefcase'),
            ('Freelance', 'INCOME', '#06B6D4', 'laptop'),
            ('Investments', 'INCOME', '#8B5CF6', 'trending-up'),
            ('Other Income', 'INCOME', '#14B8A6', 'plus-circle'),
            # Expenses
            ('Food & Dining', 'EXPENSE', '#F59E0B', 'coffee'),
            ('Housing & Rent', 'EXPENSE', '#EF4444', 'home'),
            ('Utilities', 'EXPENSE', '#F97316', 'zap'),
            ('Transportation', 'EXPENSE', '#3B82F6', 'truck'),
            ('Entertainment', 'EXPENSE', '#EC4899', 'film'),
            ('Healthcare', 'EXPENSE', '#E11D48', 'activity'),
            ('Shopping', 'EXPENSE', '#6366F1', 'shopping-bag'),
            ('Education', 'EXPENSE', '#84CC16', 'book'),
        ]
        created = []
        for name, cat_type, color, icon in default_categories:
            cat, _ = cls.objects.get_or_create(
                user=user,
                name=name,
                category_type=cat_type,
                defaults={'color': color, 'icon': icon}
            )
            created.append(cat)
        return created


class RecurringEntry(models.Model):
    FREQUENCY_CHOICES = (
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
    )

    TRANSACTION_TYPE_CHOICES = (
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recurring_entries'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_entries'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='MONTHLY')
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(null=True, blank=True)
    next_date = models.DateField()
    is_active = models.BooleanField(default=True)
    last_processed_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_date']
        verbose_name_plural = 'Recurring entries'

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.frequency})"

    def save(self, *args, **kwargs):
        if not self.next_date:
            self.next_date = self.start_date
        super().save(*args, **kwargs)

    @staticmethod
    def get_next_date_for_frequency(current_date, frequency):
        if frequency == 'DAILY':
            return current_date + relativedelta(days=1)
        elif frequency == 'WEEKLY':
            return current_date + relativedelta(weeks=1)
        elif frequency == 'MONTHLY':
            return current_date + relativedelta(months=1)
        elif frequency == 'YEARLY':
            return current_date + relativedelta(years=1)
        return current_date + relativedelta(months=1)

    def process_due(self, target_date=None):
        """
        Processes any due occurrences up to target_date (defaults to today).
        Generates corresponding Transaction records and advances next_date.
        """
        if not self.is_active:
            return []

        if target_date is None:
            target_date = date.today()

        created_transactions = []
        while self.next_date <= target_date:
            if self.end_date and self.next_date > self.end_date:
                self.is_active = False
                break

            tx = Transaction.objects.create(
                user=self.user,
                category=self.category,
                recurring_entry=self,
                transaction_type=self.transaction_type,
                amount=self.amount,
                date=self.next_date,
                description=f"[Recurring] {self.description}",
                notes=f"Generated from recurring plan #{self.id} ({self.frequency})"
            )
            created_transactions.append(tx)
            self.last_processed_date = self.next_date
            self.next_date = self.get_next_date_for_frequency(self.next_date, self.frequency)

            if self.end_date and self.next_date > self.end_date:
                self.is_active = False
                break

        self.save()
        return created_transactions


class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    recurring_entry = models.ForeignKey(
        RecurringEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=date.today)
    description = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['user', 'category']),
        ]

    def __str__(self):
        return f"{self.date} | {self.transaction_type} | {self.amount} | {self.description}"


class Budget(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    amount_limit = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.PositiveSmallIntegerField()  # 1-12
    year = models.PositiveSmallIntegerField()   # e.g. 2026
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'category', 'month', 'year')
        ordering = ['-year', '-month', 'category__name']

    def __str__(self):
        return f"{self.category.name} Budget ({self.month}/{self.year}): {self.amount_limit}"

    @property
    def spent_amount(self):
        """Calculates total expense for this category in this month/year."""
        total = Transaction.objects.filter(
            user=self.user,
            category=self.category,
            transaction_type='EXPENSE',
            date__year=self.year,
            date__month=self.month
        ).aggregate(total=Sum('amount'))['total']
        return total or Decimal('0.00')

    @property
    def remaining_amount(self):
        return self.amount_limit - self.spent_amount

    @property
    def percentage_used(self):
        if self.amount_limit > 0:
            return round((self.spent_amount / self.amount_limit) * 100, 2)
        return Decimal('0.00')

    @property
    def is_exceeded(self):
        return self.spent_amount > self.amount_limit
