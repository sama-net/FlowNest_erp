from django.urls import path
from . import views
from pages import views as pages_views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('files/', views.file_upload, name='file_upload'),
    path('delete-file/<int:file_id>/', pages_views.delete_file_view, name='delete_file'),
]