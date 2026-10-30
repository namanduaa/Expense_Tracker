from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Category, Transaction, RecurringEntry, Budget


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password', 'password_confirm')
        extra_kwargs = {
            'email': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password']
        )
        # Create default starter categories for new user
        Category.create_defaults_for_user(user)
        return user


from drf_spectacular.utils import extend_schema_field


class UserSerializer(serializers.ModelSerializer):
    total_transactions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'total_transactions')

    @extend_schema_field(serializers.IntegerField())
    def get_total_transactions(self, obj) -> int:
        return obj.transactions.count()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'category_type', 'color', 'icon', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Category name cannot be empty.")
        return name

    def validate(self, attrs):
        user = self.context['request'].user
        category_type = attrs.get('category_type', getattr(self.instance, 'category_type', 'EXPENSE'))
        name = attrs.get('name', getattr(self.instance, 'name', ''))

        qs = Category.objects.filter(user=user, name__iexact=name, category_type=category_type)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError({"name": "A category with this name and type already exists for your account."})

        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    category_type = serializers.CharField(source='category.category_type', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id',
            'transaction_type',
            'amount',
            'date',
            'category',
            'category_name',
            'category_color',
            'category_type',
            'description',
            'notes',
            'recurring_entry',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'recurring_entry', 'created_at', 'updated_at')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate_category(self, value):
        if value is not None:
            user = self.context['request'].user
            if value.user != user:
                raise serializers.ValidationError("Selected category does not belong to your account.")
        return value


class RecurringEntrySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)

    class Meta:
        model = RecurringEntry
        fields = (
            'id',
            'transaction_type',
            'amount',
            'description',
            'frequency',
            'category',
            'category_name',
            'category_color',
            'start_date',
            'end_date',
            'next_date',
            'is_active',
            'last_processed_date',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'last_processed_date', 'created_at', 'updated_at')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate_category(self, value):
        if value is not None:
            user = self.context['request'].user
            if value.user != user:
                raise serializers.ValidationError("Selected category does not belong to your account.")
        return value

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot be prior to start date."})

        if not attrs.get('next_date') and not getattr(self.instance, 'next_date', None):
            attrs['next_date'] = start_date

        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    spent_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    percentage_used = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    is_exceeded = serializers.BooleanField(read_only=True)

    class Meta:
        model = Budget
        fields = (
            'id',
            'category',
            'category_name',
            'category_color',
            'amount_limit',
            'month',
            'year',
            'spent_amount',
            'remaining_amount',
            'percentage_used',
            'is_exceeded',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'spent_amount',
            'remaining_amount',
            'percentage_used',
            'is_exceeded',
            'created_at',
            'updated_at',
        )

    def validate_amount_limit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Budget limit must be greater than 0.")
        return value

    def validate_month(self, value):
        if value < 1 or value > 12:
            raise serializers.ValidationError("Month must be between 1 and 12.")
        return value

    def validate_category(self, value):
        user = self.context['request'].user
        if value.user != user:
            raise serializers.ValidationError("Selected category does not belong to your account.")
        if value.category_type == 'INCOME':
            raise serializers.ValidationError("Budgets can only be set for Expense or Both type categories.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        category = attrs.get('category', getattr(self.instance, 'category', None))
        month = attrs.get('month', getattr(self.instance, 'month', None))
        year = attrs.get('year', getattr(self.instance, 'year', None))

        qs = Budget.objects.filter(user=user, category=category, month=month, year=year)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(
                {"category": f"A budget for {category.name} in {month}/{year} already exists."}
            )

        return attrs


class MonthlySummaryResponseSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_savings = serializers.DecimalField(max_digits=12, decimal_places=2)
    savings_rate = serializers.DecimalField(max_digits=6, decimal_places=2)
    total_transactions = serializers.IntegerField()
    income_count = serializers.IntegerField()
    expense_count = serializers.IntegerField()
    avg_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    max_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    min_expense = serializers.DecimalField(max_digits=12, decimal_places=2)


class CategoryBreakdownItemSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField()
    category_color = serializers.CharField()
    category_icon = serializers.CharField()
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_count = serializers.IntegerField()
    avg_transaction = serializers.DecimalField(max_digits=12, decimal_places=2)
    percentage_of_total = serializers.DecimalField(max_digits=6, decimal_places=2)
    budget_limit = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    budget_percentage_used = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    is_budget_exceeded = serializers.BooleanField()


class CategoryBreakdownResponseSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    total_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    categories_count = serializers.IntegerField()
    breakdown = CategoryBreakdownItemSerializer(many=True)


class MonthlyTrendItemSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    label = serializers.CharField()
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_savings = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_count = serializers.IntegerField()


class MonthlyTrendsResponseSerializer(serializers.Serializer):
    months_count = serializers.IntegerField()
    trends = MonthlyTrendItemSerializer(many=True)

