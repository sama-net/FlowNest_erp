import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__))) # scratch dir
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) # project root

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yasso.settings')
django.setup()

from chat.models import Message

msgs = Message.objects.filter(audio_file__icontains='recording.webm')
print(f"Found {msgs.count()} messages with recording.webm")
for m in msgs:
    print(f"ID: {m.id}, File: {m.audio_file.name}")
