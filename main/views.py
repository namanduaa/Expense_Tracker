from datetime import date
from rest_framework import viewsets, generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import render
from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
)

from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Category, Transaction, RecurringEntry, Budget
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegisterSerializer,
    UserSerializer,
    CategorySerializer,
    TransactionSerializer,
    RecurringEntrySerializer,
    BudgetSerializer,
    MonthlySummaryResponseSerializer,
    CategoryBreakdownResponseSerializer,
    MonthlyTrendsResponseSerializer,
)
from .filters import TransactionFilter, BudgetFilter
from .analytics import (
    get_monthly_summary,
    get_category_breakdown,
    get_monthly_trends,
    export_transactions_csv_pandas,
    export_breakdown_csv_pandas,
)


@extend_schema(
    tags=['Authentication'],
    summary='Register a new user account',
    description='Registers a new user, automatically generates default income and expense categories, and returns JWT tokens for immediate access.'
)
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'User registered successfully. Default expense and income categories created.',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Authentication'],
    summary='Obtain JWT token pair using number or username and password',
    description='Authenticates a user with their registered phone number or username and password, returning JWT access and refresh tokens.'
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema(
    tags=['Authentication'],
    summary='Get / update current user profile',
    description='Retrieves or updates profile details for the currently authenticated user.'
)
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema_view(
    list=extend_schema(tags=['Categories'], summary='List all categories for user'),
    retrieve=extend_schema(tags=['Categories'], summary='Retrieve a single category'),
    create=extend_schema(tags=['Categories'], summary='Create a new custom category'),
    update=extend_schema(tags=['Categories'], summary='Update category details'),
    partial_update=extend_schema(tags=['Categories'], summary='Partial update category'),
    destroy=extend_schema(tags=['Categories'], summary='Delete category'),
)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.none()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category_type']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Category.objects.none()
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    list=extend_schema(tags=['Transactions'], summary='List transactions with query filters (date, category, amount, recurring)'),
    retrieve=extend_schema(tags=['Transactions'], summary='Retrieve a single transaction'),
    create=extend_schema(tags=['Transactions'], summary='Record a new transaction (Income or Expense)'),
    update=extend_schema(tags=['Transactions'], summary='Update transaction'),
    partial_update=extend_schema(tags=['Transactions'], summary='Partial update transaction'),
    destroy=extend_schema(tags=['Transactions'], summary='Delete transaction'),
)
class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.none()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TransactionFilter
    search_fields = ['description', 'notes', 'category__name']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date', '-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Transaction.objects.none()
        return Transaction.objects.filter(user=self.request.user).select_related(
            'category', 'recurring_entry'
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        tags=['Transactions'],
        summary='Export user transactions to CSV via Pandas',
        description='Exports all transactions matching the current filters as an RFC 4180 CSV attachment powered by Pandas.',
        responses={200: OpenApiResponse(description='CSV file download stream')}
    )
    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        return export_transactions_csv_pandas(queryset, request.user)


@extend_schema_view(
    list=extend_schema(tags=['Recurring Entries'], summary='List recurring transaction plans'),
    retrieve=extend_schema(tags=['Recurring Entries'], summary='Retrieve a recurring plan'),
    create=extend_schema(tags=['Recurring Entries'], summary='Create a recurring plan (daily, weekly, monthly, yearly)'),
    update=extend_schema(tags=['Recurring Entries'], summary='Update recurring plan'),
    partial_update=extend_schema(tags=['Recurring Entries'], summary='Partial update recurring plan'),
    destroy=extend_schema(tags=['Recurring Entries'], summary='Delete recurring plan'),
)
class RecurringEntryViewSet(viewsets.ModelViewSet):
    queryset = RecurringEntry.objects.none()
    serializer_class = RecurringEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['transaction_type', 'frequency', 'is_active']
    search_fields = ['description', 'category__name']
    ordering_fields = ['next_date', 'amount', 'created_at']
    ordering = ['next_date']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RecurringEntry.objects.none()
        return RecurringEntry.objects.filter(user=self.request.user).select_related('category')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        tags=['Recurring Entries'],
        summary='Process single recurring entry',
        description='Executes occurrences due up to target_date for this specific plan and generates transactions.'
    )
    @action(detail=True, methods=['post'], url_path='process')
    def process_single(self, request, pk=None):
        entry = self.get_object()
        target_date_str = request.data.get('target_date')
        if target_date_str:
            try:
                target_date = date.fromisoformat(target_date_str)
            except ValueError:
                return Response(
                    {'error': 'Invalid target_date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = date.today()

        created_txs = entry.process_due(target_date=target_date)
        return Response({
            'message': f"Processed {len(created_txs)} transactions.",
            'transactions': TransactionSerializer(created_txs, many=True).data,
            'next_date': entry.next_date,
            'is_active': entry.is_active,
        })

    @extend_schema(
        tags=['Recurring Entries'],
        summary='Process all due recurring entries',
        description='Executes occurrences due across all active recurring plans up to target_date.'
    )
    @action(detail=False, methods=['post'], url_path='process-all')
    def process_all(self, request):
        target_date_str = request.data.get('target_date')
        if target_date_str:
            try:
                target_date = date.fromisoformat(target_date_str)
            except ValueError:
                return Response(
                    {'error': 'Invalid target_date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = date.today()

        entries = RecurringEntry.objects.filter(user=request.user, is_active=True, next_date__lte=target_date)
        total_created = []
        for entry in entries:
            total_created.extend(entry.process_due(target_date=target_date))

        return Response({
            'message': f"Processed {len(total_created)} total transactions from {entries.count()} recurring entries.",
            'transactions_count': len(total_created),
            'transactions': TransactionSerializer(total_created, many=True).data,
        })


@extend_schema_view(
    list=extend_schema(tags=['Budgets'], summary='List category budgets'),
    retrieve=extend_schema(tags=['Budgets'], summary='Retrieve a category budget'),
    create=extend_schema(tags=['Budgets'], summary='Create a monthly category budget limit'),
    update=extend_schema(tags=['Budgets'], summary='Update category budget'),
    partial_update=extend_schema(tags=['Budgets'], summary='Partial update category budget'),
    destroy=extend_schema(tags=['Budgets'], summary='Delete category budget'),
)
class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.none()
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = BudgetFilter
    ordering_fields = ['year', 'month', 'amount_limit']
    ordering = ['-year', '-month']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Budget.objects.none()
        return Budget.objects.filter(user=self.request.user).select_related('category')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        tags=['Budgets'],
        summary='Get monthly budget status & exceeded warnings',
        description='Computes spending comparison, remaining amount, and exceeded flags for all category budgets in a given month.',
        parameters=[
            OpenApiParameter('year', OpenApiTypes.INT, description='Target year (e.g. 2026)', required=False),
            OpenApiParameter('month', OpenApiTypes.INT, description='Target month (1-12)', required=False),
        ]
    )
    @action(detail=False, methods=['get'], url_path='status')
    def budget_status(self, request):
        try:
            year = int(request.query_params.get('year', date.today().year))
            month = int(request.query_params.get('month', date.today().month))
        except ValueError:
            return Response({'error': 'Invalid year or month parameter.'}, status=status.HTTP_400_BAD_REQUEST)

        budgets = self.get_queryset().filter(year=year, month=month)
        serializer = self.get_serializer(budgets, many=True)

        total_budget = sum(b.amount_limit for b in budgets)
        total_spent = sum(b.spent_amount for b in budgets)
        exceeded_count = sum(1 for b in budgets if b.is_exceeded)

        return Response({
            'year': year,
            'month': month,
            'total_budget': total_budget,
            'total_spent': total_spent,
            'remaining_total': total_budget - total_spent,
            'exceeded_budgets_count': exceeded_count,
            'budgets': serializer.data,
        })


@extend_schema(
    tags=['Analytics'],
    summary='Monthly spending & savings summary (Django ORM aggregate)',
    description='Calculates total income, total expense, net savings, savings rate, and expense stats using Django ORM aggregate().',
    parameters=[
        OpenApiParameter('year', OpenApiTypes.INT, description='Target year (e.g. 2026)', required=False),
        OpenApiParameter('month', OpenApiTypes.INT, description='Target month (1-12)', required=False),
    ],
    responses={200: MonthlySummaryResponseSerializer}
)
class MonthlySummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get('year', date.today().year))
            month = int(request.query_params.get('month', date.today().month))
        except ValueError:
            return Response(
                {'error': 'year and month must be integers.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = get_monthly_summary(request.user, year=year, month=month)
        return Response(data)


@extend_schema(
    tags=['Analytics'],
    summary='Category spending breakdown (Django ORM annotate)',
    description='Aggregates expenses grouped by category, computing percentage of total and budget limits using Django ORM annotate().',
    parameters=[
        OpenApiParameter('year', OpenApiTypes.INT, description='Target year (e.g. 2026)', required=False),
        OpenApiParameter('month', OpenApiTypes.INT, description='Target month (1-12)', required=False),
    ],
    responses={200: CategoryBreakdownResponseSerializer}
)
class CategoryBreakdownAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get('year', date.today().year))
            month = int(request.query_params.get('month', date.today().month))
        except ValueError:
            return Response(
                {'error': 'year and month must be integers.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = get_category_breakdown(request.user, year=year, month=month)
        return Response(data)


@extend_schema(
    tags=['Analytics'],
    summary='Export category breakdown to CSV (Pandas)',
    description='Generates and streams category-wise expense breakdown as a CSV file using Pandas.',
    parameters=[
        OpenApiParameter('year', OpenApiTypes.INT, description='Target year (e.g. 2026)', required=False),
        OpenApiParameter('month', OpenApiTypes.INT, description='Target month (1-12)', required=False),
    ],
    responses={200: OpenApiResponse(description='CSV file stream')}
)
class CategoryBreakdownExportCSVAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get('year', date.today().year))
            month = int(request.query_params.get('month', date.today().month))
        except ValueError:
            return Response(
                {'error': 'year and month must be integers.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = get_category_breakdown(request.user, year=year, month=month)
        return export_breakdown_csv_pandas(data, request.user)


@extend_schema(
    tags=['Analytics'],
    summary='Multi-month financial trends (TruncMonth + annotate)',
    description='Retrieves historical income vs expense trends over a specified period using TruncMonth and annotate().',
    parameters=[
        OpenApiParameter('months', OpenApiTypes.INT, description='Number of months of history (default 6)', required=False),
    ],
    responses={200: MonthlyTrendsResponseSerializer}
)
class MonthlyTrendsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            months = int(request.query_params.get('months', 6))
            if months < 1 or months > 36:
                months = 6
        except ValueError:
            months = 6

        trends = get_monthly_trends(request.user, months_count=months)
        return Response({'months_count': months, 'trends': trends})


def index(request):
    """
    Serves the modern, interactive Personal Expense Tracker API Documentation & Web Console.
    """
    return render(request, 'index.html', {
        'title': 'Personal Expense Tracker API',
        'version': '1.0.0',
    })
