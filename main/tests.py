from datetime import date, timedelta
from decimal import Decimal
import io
import pandas as pd
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from main.models import Category, Transaction, RecurringEntry, Budget


class PersonalExpenseTrackerTests(APITestCase):
    def setUp(self):
        # Create primary test user
        self.user1 = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='Password123!',
            first_name='Alice',
            last_name='Smith'
        )
        Category.create_defaults_for_user(self.user1)

        # Create second test user for data isolation tests
        self.user2 = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='Password456!',
            first_name='Bob',
            last_name='Jones'
        )
        Category.create_defaults_for_user(self.user2)

        # JWT Tokens for Alice
        refresh1 = RefreshToken.for_user(self.user1)
        self.user1_access_token = str(refresh1.access_token)

        # JWT Tokens for Bob
        refresh2 = RefreshToken.for_user(self.user2)
        self.user2_access_token = str(refresh2.access_token)

        # Fetch some default categories for Alice
        self.cat_salary = Category.objects.get(user=self.user1, name='Salary')
        self.cat_food = Category.objects.get(user=self.user1, name='Food & Dining')
        self.cat_rent = Category.objects.get(user=self.user1, name='Housing & Rent')

    def authenticate_as_user1(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user1_access_token}')

    def authenticate_as_user2(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user2_access_token}')

    def clear_credentials(self):
        self.client.credentials()

    # -------------------------------------------------------------
    # 1. JWT Authentication Tests
    # -------------------------------------------------------------
    def test_user_registration(self):
        """Test user registration returns JWT tokens and creates default categories."""
        url = reverse('auth-register')
        data = {
            'username': 'charlie',
            'email': 'charlie@example.com',
            'password': 'ComplexPassword789!',
            'password_confirm': 'ComplexPassword789!',
            'first_name': 'Charlie',
            'last_name': 'Brown'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])

        # Verify default categories created for Charlie
        charlie_user = User.objects.get(username='charlie')
        self.assertTrue(Category.objects.filter(user=charlie_user, name='Food & Dining').exists())
        self.assertTrue(Category.objects.filter(user=charlie_user, name='Salary').exists())

    def test_jwt_login(self):
        """Test obtaining JWT token with username and password."""
        url = reverse('auth-login')
        data = {
            'username': 'alice',
            'password': 'Password123!'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_unauthenticated_request_rejected(self):
        """Endpoints are protected by JWT and reject unauthenticated requests."""
        self.clear_credentials()
        url = reverse('transaction-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -------------------------------------------------------------
    # 2. Data Isolation & Security Tests
    # -------------------------------------------------------------
    def test_user_can_only_access_their_own_transactions(self):
        """Test that Alice cannot see or edit Bob's transactions."""
        # Create transaction for Alice
        tx_alice = Transaction.objects.create(
            user=self.user1,
            category=self.cat_food,
            transaction_type='EXPENSE',
            amount=Decimal('45.50'),
            date=date.today(),
            description='Alice Lunch'
        )

        # Create transaction for Bob
        cat_bob_food = Category.objects.get(user=self.user2, name='Food & Dining')
        tx_bob = Transaction.objects.create(
            user=self.user2,
            category=cat_bob_food,
            transaction_type='EXPENSE',
            amount=Decimal('90.00'),
            date=date.today(),
            description='Bob Dinner'
        )

        # Alice views transaction list
        self.authenticate_as_user1()
        res = self.client.get(reverse('transaction-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get('results', res.data)
        tx_ids = [item['id'] for item in results]
        self.assertIn(tx_alice.id, tx_ids)
        self.assertNotIn(tx_bob.id, tx_ids)

        # Alice attempts to access Bob's transaction directly -> 404
        res_bob_tx = self.client.get(reverse('transaction-detail', kwargs={'pk': tx_bob.id}))
        self.assertEqual(res_bob_tx.status_code, status.HTTP_404_NOT_FOUND)

        # Alice attempts to update Bob's transaction -> 404
        res_bob_patch = self.client.patch(
            reverse('transaction-detail', kwargs={'pk': tx_bob.id}),
            {'amount': 10.00},
            format='json'
        )
        self.assertEqual(res_bob_patch.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_assign_another_users_category(self):
        """Alice cannot create a transaction with Bob's category."""
        self.authenticate_as_user1()
        cat_bob = Category.objects.get(user=self.user2, name='Food & Dining')
        res = self.client.post(
            reverse('transaction-list'),
            {
                'category': cat_bob.id,
                'transaction_type': 'EXPENSE',
                'amount': 30.00,
                'date': str(date.today()),
                'description': 'Attempting unauthorized category'
            },
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------
    # 3. Categories CRUD Tests
    # -------------------------------------------------------------
    def test_category_create_and_unique_constraint(self):
        """User can create custom category, and cannot duplicate existing one."""
        self.authenticate_as_user1()
        url = reverse('category-list')
        res = self.client.post(url, {
            'name': 'Gym & Fitness',
            'category_type': 'EXPENSE',
            'color': '#10B981'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Duplicate attempt
        res_dup = self.client.post(url, {
            'name': 'Gym & Fitness',
            'category_type': 'EXPENSE',
        }, format='json')
        self.assertEqual(res_dup.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------
    # 4. Recurring Entries & Processing Tests
    # -------------------------------------------------------------
    def test_recurring_entry_creation_and_processing(self):
        """Test recurring entry setup and transaction generation."""
        self.authenticate_as_user1()

        past_date = date.today() - timedelta(days=15)
        res = self.client.post(reverse('recurring-list'), {
            'category': self.cat_food.id,
            'transaction_type': 'EXPENSE',
            'amount': '25.00',
            'description': 'Weekly Groceries Plan',
            'frequency': 'WEEKLY',
            'start_date': str(past_date),
            'next_date': str(past_date),
            'is_active': True
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recurring_id = res.data['id']

        # Process due occurrences up to today
        process_url = reverse('recurring-process-single', kwargs={'pk': recurring_id})
        res_proc = self.client.post(process_url, {'target_date': str(date.today())}, format='json')
        self.assertEqual(res_proc.status_code, status.HTTP_200_OK)
        self.assertGreater(len(res_proc.data['transactions']), 0)

        # Verify generated transactions exist in Transaction table
        generated_txs = Transaction.objects.filter(recurring_entry_id=recurring_id)
        self.assertGreater(generated_txs.count(), 0)
        self.assertTrue(generated_txs.first().description.startswith('[Recurring]'))

    # -------------------------------------------------------------
    # 5. Budget Limits & Warnings Tests
    # -------------------------------------------------------------
    def test_budget_limits_and_exceeded_tracking(self):
        """Test budget limits per category and spending calculations."""
        self.authenticate_as_user1()
        today = date.today()

        # Create budget for Food & Dining with limit of 100.00
        budget_res = self.client.post(reverse('budget-list'), {
            'category': self.cat_food.id,
            'amount_limit': '100.00',
            'month': today.month,
            'year': today.year
        }, format='json')
        self.assertEqual(budget_res.status_code, status.HTTP_201_CREATED)

        # Add transaction of 60.00 (under budget)
        Transaction.objects.create(
            user=self.user1,
            category=self.cat_food,
            transaction_type='EXPENSE',
            amount=Decimal('60.00'),
            date=today,
            description='Dinner 1'
        )

        status_url = f"{reverse('budget-budget-status')}?year={today.year}&month={today.month}"
        res_status = self.client.get(status_url)
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)
        food_budget = next(b for b in res_status.data['budgets'] if b['category'] == self.cat_food.id)
        self.assertEqual(float(food_budget['spent_amount']), 60.00)
        self.assertEqual(float(food_budget['remaining_amount']), 40.00)
        self.assertFalse(food_budget['is_exceeded'])

        # Add another transaction of 50.00 (now 110.00 spent, exceeding 100.00 limit)
        Transaction.objects.create(
            user=self.user1,
            category=self.cat_food,
            transaction_type='EXPENSE',
            amount=Decimal('50.00'),
            date=today,
            description='Dinner 2'
        )

        res_status2 = self.client.get(status_url)
        food_budget2 = next(b for b in res_status2.data['budgets'] if b['category'] == self.cat_food.id)
        self.assertEqual(float(food_budget2['spent_amount']), 110.00)
        self.assertTrue(food_budget2['is_exceeded'])

    # -------------------------------------------------------------
    # 6. Monthly Spending Summaries & Category Breakdown (ORM aggregate & annotate)
    # -------------------------------------------------------------
    def test_monthly_summary_and_category_breakdown(self):
        """Test monthly summary via aggregate() and category breakdown via annotate()."""
        self.authenticate_as_user1()
        today = date.today()

        # Seed transactions:
        # Income: 5000.00 Salary
        Transaction.objects.create(
            user=self.user1,
            category=self.cat_salary,
            transaction_type='INCOME',
            amount=Decimal('5000.00'),
            date=today,
            description='Monthly Salary'
        )
        # Expenses: 1200.00 Rent, 300.00 Food
        Transaction.objects.create(
            user=self.user1,
            category=self.cat_rent,
            transaction_type='EXPENSE',
            amount=Decimal('1200.00'),
            date=today,
            description='Apartment Rent'
        )
        Transaction.objects.create(
            user=self.user1,
            category=self.cat_food,
            transaction_type='EXPENSE',
            amount=Decimal('300.00'),
            date=today,
            description='Supermarket'
        )

        # 1. Monthly Summary (uses Django ORM aggregate())
        summary_url = f"{reverse('analytics-monthly-summary')}?year={today.year}&month={today.month}"
        res_summary = self.client.get(summary_url)
        self.assertEqual(res_summary.status_code, status.HTTP_200_OK)
        self.assertEqual(float(res_summary.data['total_income']), 5000.00)
        self.assertEqual(float(res_summary.data['total_expense']), 1500.00)
        self.assertEqual(float(res_summary.data['net_savings']), 3500.00)
        self.assertEqual(float(res_summary.data['savings_rate']), 70.00)
        self.assertEqual(res_summary.data['total_transactions'], 3)

        # 2. Category Breakdown (uses Django ORM annotate())
        breakdown_url = f"{reverse('analytics-category-breakdown')}?year={today.year}&month={today.month}"
        res_breakdown = self.client.get(breakdown_url)
        self.assertEqual(res_breakdown.status_code, status.HTTP_200_OK)
        self.assertEqual(float(res_breakdown.data['total_expense']), 1500.00)

        breakdown_items = {item['category_name']: item for item in res_breakdown.data['breakdown']}
        self.assertIn('Housing & Rent', breakdown_items)
        self.assertIn('Food & Dining', breakdown_items)
        self.assertEqual(float(breakdown_items['Housing & Rent']['total_spent']), 1200.00)
        self.assertEqual(float(breakdown_items['Housing & Rent']['percentage_of_total']), 80.00)
        self.assertEqual(float(breakdown_items['Food & Dining']['total_spent']), 300.00)
        self.assertEqual(float(breakdown_items['Food & Dining']['percentage_of_total']), 20.00)

    # -------------------------------------------------------------
    # 7. CSV Export through Pandas Tests
    # -------------------------------------------------------------
    def test_csv_export_through_pandas(self):
        """Test transactions CSV export endpoint powered by Pandas."""
        self.authenticate_as_user1()
        today = date.today()

        Transaction.objects.create(
            user=self.user1,
            category=self.cat_food,
            transaction_type='EXPENSE',
            amount=Decimal('42.75'),
            date=today,
            description='CSV Test Transaction'
        )

        export_url = reverse('transaction-export-csv')
        response = self.client.get(export_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename=', response['Content-Disposition'])

        # Validate CSV content by reading back into Pandas
        csv_content = io.StringIO(response.content.decode('utf-8'))
        df = pd.read_csv(csv_content)

        self.assertIn('Transaction ID', df.columns)
        self.assertIn('Date', df.columns)
        self.assertIn('Amount', df.columns)
        self.assertIn('Category', df.columns)
        self.assertIn('Description', df.columns)

        # Check values in DataFrame
        row = df[df['Description'] == 'CSV Test Transaction']
        self.assertEqual(len(row), 1)
        self.assertEqual(row.iloc[0]['Category'], 'Food & Dining')
        self.assertEqual(float(row.iloc[0]['Amount']), 42.75)

    # -------------------------------------------------------------
    # 8. Swagger & OpenAPI Documentation Endpoints
    # -------------------------------------------------------------
    def test_swagger_and_openapi_endpoints(self):
        """Test OpenAPI schema, Swagger UI, and Redoc respond with HTTP 200."""
        schema_res = self.client.get(reverse('schema'))
        self.assertEqual(schema_res.status_code, status.HTTP_200_OK)

        swagger_res = self.client.get(reverse('swagger-ui'))
        self.assertEqual(swagger_res.status_code, status.HTTP_200_OK)

        redoc_res = self.client.get(reverse('redoc'))
        self.assertEqual(redoc_res.status_code, status.HTTP_200_OK)

