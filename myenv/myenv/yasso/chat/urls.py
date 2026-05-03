from django.urls import path
from . import views

app_name = 'chat'
urlpatterns = [
    path('<str:room_name>/', views.chat_room, name='room'),
    path('tasks/list/', views.task_list, name='task_list'),
    path('tasks/create/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>/update/', views.update_task, name='update_task'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='delete_task'),

    # Signaling & AI Meeting APIs
    path('api/call/start/<str:room_name>/', views.start_call_api, name='start_call_api'),
    path('api/call/check/<str:room_name>/', views.check_call_api, name='check_call_api'),
    path('api/call/end/<str:room_name>/', views.end_call_api, name='end_call_api'),
    
    # New Global Signaling & AI APIs
    path('api/call/post-signal/<int:session_id>/', views.post_signal_api, name='post_signal_api'),
    path('api/call/get-signals/<int:session_id>/', views.get_signals_api, name='get_signals_api'),
    path('api/ai/translate/', views.translate_api, name='translate_api'),
    
    path('api/message/<int:message_id>/reaction/', views.toggle_reaction_api, name='toggle_reaction_api'),
    path('api/message/delete/<int:message_id>/', views.delete_message_api, name='delete_message_api'),
    
    path('api/call/summarize/', views.summarize_call_api, name='summarize_call_api'),
    path('api/meeting/finalize/<str:room_name>/', views.finalize_meeting_api, name='finalize_meeting_api'),
    path('api/call/daily-room/<str:room_name>/', views.jitsi_room_api, name='jitsi_room_api'),
    path('api/summaries/<str:room_name>/', views.summaries_api, name='summaries_api'),
]
