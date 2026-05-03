from django.db import models
from django.contrib.auth.models import User

# ─────────────────────────────────────────────
#  CHAT MODELS (Relational Company FK — Hardened)
# ─────────────────────────────────────────────

class Message(models.Model):
    sender = models.ForeignKey('products.Profile', on_delete=models.CASCADE, related_name='sent_messages')
    company = models.ForeignKey('products.Company', on_delete=models.CASCADE, related_name='messages', null=True, blank=True, db_index=True)
    room_type = models.CharField(max_length=50, db_index=True)
    company_name = models.CharField(max_length=100, db_index=True)  # Keep for migration safety
    content = models.TextField(blank=True, null=True)
    audio_file = models.FileField(upload_to='chat_audio/', blank=True, null=True)
    attachment = models.FileField(upload_to='chat_attachments/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(max_length=20, default='all')  # 'all', 'private'
    recipients = models.ManyToManyField(User, blank=True, related_name='received_messages')

    def __str__(self):
        return f"{self.sender.user.username}: {self.content[:20] if self.content else '[media]'}"

# ─────────────────────────────────────────────
#  TASKS & CALLS
# ─────────────────────────────────────────────

class Task(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    company = models.ForeignKey('products.Company', on_delete=models.CASCADE, related_name='tasks', null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=100)  # Keep for migration safety
    department = models.ForeignKey('products.CustomDepartment', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    status = models.CharField(max_length=20, default='pending')
    priority = models.CharField(max_length=20, default='medium', choices=[('low', 'منخفضة'), ('medium', 'متوسطة'), ('high', 'عالية')])
    due_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class CallSession(models.Model):
    room_name = models.CharField(max_length=100)
    company = models.ForeignKey('products.Company', on_delete=models.CASCADE, related_name='call_sessions', null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=100)  # Keep for migration safety
    caller = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    is_ringing = models.BooleanField(default=False)
    call_type = models.CharField(max_length=20, default='audio')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    participants = models.ManyToManyField(User, blank=True, related_name='invited_calls')

class CallSignal(models.Model):
    session = models.ForeignKey(CallSession, on_delete=models.CASCADE, related_name='signals')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_signals')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_signals', null=True, blank=True)
    signal_type = models.CharField(max_length=50)  # 'offer', 'answer', 'candidate', 'join'
    data = models.TextField()  # JSON
    created_at = models.DateTimeField(auto_now_add=True)

class MeetingRecord(models.Model):
    room_name = models.CharField(max_length=100)
    company = models.ForeignKey('products.Company', on_delete=models.CASCADE, related_name='meeting_records', null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=100)  # Keep for migration safety
    transcript = models.TextField()
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey('products.Profile', on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')
