"""
URL configuration for yasso project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, re_path
from django.views.static import serve
from django.contrib import admin
from django.contrib.auth import views as auth_views
from pages import views as pages_views

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          pages_views.landing_page_view, name='landing_page'),
    path('dashboard/',pages_views.dashboard_view, name='dashboard'),
    path('team/',     pages_views.team_list_view, name='team_list'),
    path('workplace/<int:dept_id>/', pages_views.workplace_view, name='workplace'),
    path('workplace/<int:dept_id>/action/', pages_views.smart_action_api, name='smart_action_api'),
    path('workspaces/<int:dept_id>/', pages_views.workplace_view), # Alias

    path('flownest/', pages_views.flownest_view, name='flownest'),


    path('flownest/ai-scan/', pages_views.flownest_ai_scan, name='flownest_ai_scan'),
    path('approvals/',       pages_views.approvals_view,     name='approvals'),
    path('analytics/',       pages_views.analytics_view,     name='analytics'),
    path('reports/',         pages_views.reports_view,        name='reports'),
    path('activity-log/',    pages_views.activity_log_view,   name='activity_log'),
    path('upload-center/',   pages_views.upload_data_view,    name='upload_center'),
    path('reports/ai/',      pages_views.generate_ai_report_api, name='ai_report_api'),
    path('delete-file/<int:file_id>/', pages_views.delete_file_view, name='delete_file'),
    path('analyze/<int:file_id>/', pages_views.analyze_file_view, name='analyze_file'),
    path('analyze/<int:file_id>/ai/', pages_views.generate_single_file_ai_report_api, name='single_file_ai_report'),
    path('register/', pages_views.register_view, name='register'),
    path('internal-dev-portal-access-2026/', pages_views.dev_register_view, name='dev_register'),
    path('internal/dev-portal-access-2026/', pages_views.dev_register_view),  # Alias to help with typos
    path('api/get-departments/', pages_views.api_get_departments, name='api_get_departments'),
    path('team/approve/<int:profile_id>/', pages_views.team_member_approve_view, name='team_member_approve'),
    path('team/delete/<int:profile_id>/', pages_views.team_member_delete_view, name='team_member_delete'),
    path('health/ai-test/', pages_views.ai_health_check_view, name='ai_health_check'),

    path('health/rag-diagnostic/', pages_views.rag_diagnostic_api, name='rag_diagnostic'),
    path('internal/auto-setup-admin-secret-2026/', pages_views.auto_setup_admin, name='auto_admin_setup'),
    path('api/post-to-finance/', pages_views.post_to_finance_view, name='post_to_finance'),
    path('health-center/', pages_views.health_center_view, name='health_center'),
    path('settings/', pages_views.account_settings_view, name='account_settings'),
    path('setup/',    pages_views.company_setup_view,    name='company_setup'),
    path('setup/api/',pages_views.company_setup_api,     name='company_setup_api'),
    path('login/',    auth_views.LoginView.as_view(), name='login'),
    path('logout/',   auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    path('products/', include('products.urls')),
    path('rag/',      include('rag.urls', namespace='rag')),
    path('chat/',     include('chat.urls', namespace='chat')),
    path('i18n/',     include('django.conf.urls.i18n')),
]

# Unconditionally serve media files in production (required for Railway Volume)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]