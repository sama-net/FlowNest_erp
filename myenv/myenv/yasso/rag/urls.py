from django.urls import path
from . import views

app_name = "rag"

urlpatterns = [
    path("chat/",       views.chat_page, name="chat"),
    path("api/chat/",   views.chat_api,  name="chat_api"),
    path("api/sync/",   views.sync_db,   name="sync_db"),
]
