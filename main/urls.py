from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from . import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'transactions', views.TransactionViewSet, basename='transaction')
router.register(r'recurring', views.RecurringEntryViewSet, basename='recurring')
router.register(r'budgets', views.BudgetViewSet, basename='budget')

urlpatterns = [
    # Interactive Frontend Console & API Guide
    path('', views.index, name='index'),

    # Swagger / OpenAPI 3.0 Documentation Endpoints
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='api-docs'),
    path('apis/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='apis-docs'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Authentication & JWT Endpoints
    path('api/auth/register/', views.RegisterView.as_view(), name='auth-register'),
    path('api/auth/login/', views.CustomTokenObtainPairView.as_view(), name='auth-login'),
    path('api/auth/token/', views.CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api/auth/me/', views.UserProfileView.as_view(), name='auth-me'),

    # Analytics Endpoints (Django ORM aggregate() & annotate())
    path('api/analytics/monthly-summary/', views.MonthlySummaryAPIView.as_view(), name='analytics-monthly-summary'),
    path('api/analytics/category-breakdown/', views.CategoryBreakdownAPIView.as_view(), name='analytics-category-breakdown'),
    path('api/analytics/category-breakdown/export-csv/', views.CategoryBreakdownExportCSVAPIView.as_view(), name='analytics-category-breakdown-csv'),
    path('api/analytics/trends/', views.MonthlyTrendsAPIView.as_view(), name='analytics-trends'),

    # Router endpoints: /api/categories/, /api/transactions/, /api/recurring/, /api/budgets/
    path('api/', include(router.urls)),
]