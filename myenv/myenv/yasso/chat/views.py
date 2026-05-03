import json
import datetime
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Message, Task, CallSession, MeetingRecord, CallSignal, MessageReaction

# ─────────────────────────────────────────────
#  CHAT ROOM
# ─────────────────────────────────────────────
@login_required
def chat_room(request, room_name):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_approved:
        return render(request, 'pages/pending.html', {'profile': profile})

    if room_name != 'general':
        user_dept_name = profile.department.name.lower() if profile.department else ""
        if profile.role not in ['owner', 'developer'] and user_dept_name != room_name.lower():
            return render(request, 'pages/unauthorized.html')
    
    if request.method == 'POST':
        content    = request.POST.get('content', '').strip()
        audio_file = request.FILES.get('audio_file')
        attachment = request.FILES.get('attachment')
        visibility = request.POST.get('visibility', 'all')
        
        if content or audio_file or attachment:
            if attachment and attachment.name.endswith('.webm'):
                audio_file = attachment
                attachment = None

            msg = Message.objects.create(
                sender=profile,
                company=profile.company,
                room_type=room_name,
                company_name=profile.company_name,
                content=content,
                audio_file=audio_file,
                attachment=attachment,
                visibility=visibility
            )
            recipient_ids = request.POST.getlist('recipients')
            if recipient_ids:
                msg.recipients.set(recipient_ids)
                msg.visibility = 'private'
                msg.save()
        return redirect('chat:room', room_name=room_name)

    from django.db.models import Q
    if profile.company:
        messages_qs = Message.objects.filter(
            room_type=room_name,
            company=profile.company
        ).select_related('sender__user').prefetch_related('reactions', 'recipients')
    else:
        messages_qs = Message.objects.filter(
            room_type=room_name,
            company_name=profile.company_name
        ).select_related('sender__user').prefetch_related('reactions', 'recipients')
    
    if profile.role not in ['owner', 'developer']:
        messages_qs = messages_qs.filter(
            Q(visibility='all') | Q(recipients=request.user) | Q(sender=profile)
        )

    if profile.company:
        company_users = User.objects.filter(
            profile__company=profile.company,
            profile__is_approved=True
        ).exclude(id=request.user.id).select_related('profile')
    else:
        company_users = User.objects.filter(
            profile__company_name=profile.company_name,
            profile__is_approved=True
        ).exclude(id=request.user.id).select_related('profile')

    if profile.company:
        meeting_summaries = MeetingRecord.objects.filter(
            room_name=room_name,
            company=profile.company
        ).order_by('-created_at')[:5]
    else:
        meeting_summaries = MeetingRecord.objects.filter(
            room_name=room_name,
            company_name=profile.company_name
        ).order_by('-created_at')[:5]

    from products.models import CustomDepartment
    display_name = "النقاش العام"
    
    try:
        if profile.company:
            dept = CustomDepartment.objects.filter(name__iexact=room_name, company=profile.company).first()
        else:
            dept = CustomDepartment.objects.filter(name__iexact=room_name, company_name=profile.company_name).first()
        if dept:
            display_name = f"فريق {dept.name}"
        elif room_name == 'general':
            display_name = "النقاش العام"
    except:
        pass

    return render(request, 'chat/room.html', {
        'messages': messages_qs,
        'room_name': room_name,
        'display_name': display_name,
        'profile': profile,
        'company_users': company_users,
        'meeting_summaries': meeting_summaries,
    })


@login_required
def toggle_reaction_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)
        data = json.loads(request.body)
        emoji = data.get('emoji')
        profile = request.user.profile
        if not emoji:
            return JsonResponse({'error': 'No emoji'}, status=400)
        reaction, created = MessageReaction.objects.get_or_create(
            message=message, user=profile, emoji=emoji
        )
        if not created:
            reaction.delete()
            return JsonResponse({'status': 'removed'})
        return JsonResponse({'status': 'added'})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def delete_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)
        if message.sender.user != request.user:
            return JsonResponse({'error': 'Unauthorized deletion attempt'}, status=403)
        message.delete()
        return JsonResponse({'status': 'deleted'})
    return JsonResponse({'error': 'POST required'}, status=405)


# ─────────────────────────────────────────────
#  CALL SIGNALING — FIXED
# ─────────────────────────────────────────────

@login_required
def start_call_api(request, room_name):
    """
    FIX 1: Now accepts POST (was GET) to match the JS fetch call.
    FIX 2: Reads call_type and participants from JSON body (not query string).
    FIX 3: Auto-cleans ghost calls older than 2 minutes before creating new one.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    profile = request.user.profile

    # Parse body — JS sends JSON
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        body = {}

    call_type = body.get('type', 'audio')
    participant_ids = body.get('participants', [])

    # Clean up ghost calls: any active session not updated in 2 minutes is dead
    two_min_ago = timezone.now() - datetime.timedelta(minutes=2)
    ghost_qs = CallSession.objects.filter(
        room_name=room_name,
        is_active=True,
        updated_at__lt=two_min_ago
    )
    if profile.company:
        ghost_qs = ghost_qs.filter(company=profile.company)
    else:
        ghost_qs = ghost_qs.filter(company_name=profile.company_name)
    ghost_qs.update(is_active=False, is_ringing=False)

    # Also close any active session started by me (re-dial scenario)
    my_qs = CallSession.objects.filter(
        room_name=room_name,
        is_active=True,
        caller=request.user
    )
    if profile.company:
        my_qs = my_qs.filter(company=profile.company)
    else:
        my_qs = my_qs.filter(company_name=profile.company_name)
    my_qs.update(is_active=False, is_ringing=False)

    call = CallSession.objects.create(
        room_name=room_name,
        company=profile.company,
        company_name=profile.company_name,
        caller=request.user,
        is_active=True,
        call_type=call_type,
        is_ringing=True,
    )

    if participant_ids:
        valid_ids = [p for p in participant_ids if str(p).isdigit()]
        call.participants.set(valid_ids)

    return JsonResponse({'status': 'ok', 'session_id': call.id})


@login_required
def post_signal_api(request, session_id):
    """
    FIX: Added session.updated_at heartbeat via save().
    This keeps active sessions alive and lets ghost-call cleanup work correctly.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    session = get_object_or_404(CallSession, pk=session_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    receiver_id = data.get('receiver_id')
    receiver = None
    if receiver_id:
        receiver = User.objects.filter(pk=receiver_id).first()

    CallSignal.objects.create(
        session=session,
        sender=request.user,
        receiver=receiver,
        signal_type=data.get('type', ''),
        data=json.dumps(data.get('data', {}))
    )

    # Heartbeat: update session timestamp so it's not cleaned as a ghost call
    session.save()

    return JsonResponse({'status': 'ok'})


@login_required
def get_signals_api(request, session_id):
    """
    FIX: Added session heartbeat on every poll so the caller's session
    stays alive even while waiting for the other side to join.
    Signals filtered to: directed at ME, or broadcast (no receiver).
    """
    since_id = int(request.GET.get('since_id', 0))

    session = get_object_or_404(CallSession, pk=session_id)

    # Heartbeat: touching updated_at keeps the session alive for ghost-call cleanup
    session.save()

    signals = CallSignal.objects.filter(
        session_id=session_id,
        id__gt=since_id
    ).filter(
        models.Q(receiver=request.user) | models.Q(receiver__isnull=True)
    ).exclude(
        sender=request.user
    ).order_by('created_at')

    data = []
    for s in signals:
        try:
            signal_data = json.loads(s.data)
        except (json.JSONDecodeError, Exception):
            signal_data = {}
        data.append({
            'id': s.id,
            'type': s.signal_type,
            'data': signal_data,
            'sender_id': s.sender.id,
            'receiver_id': s.receiver.id if s.receiver else None,
        })

    return JsonResponse({'signals': data})


@login_required
def check_call_api(request, room_name):
    """
    FIX: Ghost calls now expire after 2 minutes automatically via updated_at check.
    The session heartbeat in get_signals_api/post_signal_api keeps legit calls alive.
    """
    profile = request.user.profile
    # 10 minutes window: Jitsi has no heartbeat, so we give more time
    ten_min_ago = timezone.now() - datetime.timedelta(minutes=10)

    if profile.company:
        company_qs = models.Q(company=profile.company)
    else:
        company_qs = models.Q(company_name=profile.company_name)

    call = CallSession.objects.filter(
        company_qs,
        room_name=room_name,
        is_active=True,
        is_ringing=True,                       # Only ring for sessions that are ringing
        updated_at__gte=ten_min_ago            # Ghost calls expire after 10 minutes
    ).filter(
        models.Q(participants__isnull=True) |
        models.Q(participants=request.user)
    ).exclude(
        caller=request.user
    ).select_related('caller').prefetch_related('participants').distinct().first()

    if call:
        return JsonResponse({
            'active': True,
            'session_id': call.id,
            'caller': call.caller.username,
            'type': call.call_type,
        })
    return JsonResponse({'active': False})


@login_required
def end_call_api(request, room_name):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    profile = request.user.profile
    qs = CallSession.objects.filter(room_name=room_name, is_active=True)
    if profile.company:
        qs = qs.filter(company=profile.company)
    else:
        qs = qs.filter(company_name=profile.company_name)
    qs.update(is_active=False, is_ringing=False)
    return JsonResponse({'status': 'ok'})


# ─────────────────────────────────────────────
#  AI FEATURES
# ─────────────────────────────────────────────

@login_required
def finalize_meeting_api(request, room_name):
    if request.method == 'POST':
        data = json.loads(request.body)
        transcript = data.get('transcript', '')
        profile = request.user.profile
        if not transcript or len(transcript) < 20:
            return JsonResponse({'error': 'Too short'}, status=400)
        try:
            from django.conf import settings
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            res = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": f"Summarize this meeting transcript briefly in Arabic: {transcript}"}]
            )
            summary = res.choices[0].message.content
            MeetingRecord.objects.create(
                room_name=room_name,
                company=profile.company,
                company_name=profile.company_name,
                transcript=transcript,
                summary=summary
            )
            return JsonResponse({'summary': summary})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def translate_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        if not text:
            return JsonResponse({'translation': ''})
        try:
            from django.conf import settings
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            completion = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Translate Arabic to English. Output only translation."},
                    {"role": "user", "content": text}
                ]
            )
            return JsonResponse({'translation': completion.choices[0].message.content})
        except:
            return JsonResponse({'translation': 'Error'})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def summarize_call_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transcript = data.get('transcript', '').strip()
            room_name = data.get('room_name', 'general')

            if not transcript:
                return JsonResponse({'summary': '', 'tasks': []})

            from django.conf import settings as dj_settings
            from groq import Groq

            client = Groq(api_key=dj_settings.GROQ_API_KEY, timeout=30.0)
            prompt = (
                "You are an AI meeting assistant. Based on the following raw conversation transcript in Arabic, "
                "provide a concise structured summary in professional Arabic and a JSON array of specific "
                "actionable tasks that were agreed upon.\n\n"
                "Format your response as exactly JSON:\n"
                "{\n"
                "  \"summary\": \"(Arabic text summary)\",\n"
                "  \"tasks\": [\"Task 1\", \"Task 2\"]\n"
                "}\n\n"
                f"Transcript:\n{transcript}"
            )

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=dj_settings.GROQ_MODEL,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result_json = json.loads(chat_completion.choices[0].message.content)
            summary = result_json.get('summary', '')
            tasks = result_json.get('tasks', [])

            profile = request.user.profile

            # 1. Save the Summary to MeetingRecord
            if summary:
                MeetingRecord.objects.create(
                    room_name=room_name,
                    company=profile.company,
                    company_name=profile.company_name,
                    transcript=transcript[:5000], # Cap transcript length for DB safety
                    summary=summary
                )

            # 2. Save Tasks
            for t in tasks:
                if t:
                    Task.objects.create(
                        title=t,
                        assigned_to=request.user,
                        assigned_by=request.user,
                        company=profile.company,
                        company_name=profile.company_name,
                        department=profile.department,
                        priority='medium'
                    )

            return JsonResponse({
                'summary': summary,
                'tasks': tasks
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'POST required'}, status=405)


# ─────────────────────────────────────────────
#  TASKS
# ─────────────────────────────────────────────

@login_required
def task_list(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_approved:
        return render(request, 'pages/pending.html')

    tasks_assigned = Task.objects.filter(assigned_by=request.user)
    tasks_my = Task.objects.filter(assigned_to=request.user)

    if profile.role in ['owner', 'developer']:
        if profile.company:
            company_users = User.objects.filter(profile__company=profile.company, profile__is_approved=True)
        else:
            company_users = User.objects.filter(profile__company_name=profile.company_name, profile__is_approved=True)
    elif profile.role == 'manager':
        if profile.company:
            company_users = User.objects.filter(
                profile__company=profile.company,
                profile__department=profile.department,
                profile__is_approved=True
            )
        else:
            company_users = User.objects.filter(
                profile__company_name=profile.company_name,
                profile__department=profile.department,
                profile__is_approved=True
            )
    else:
        company_users = User.objects.filter(id=request.user.id)

    return render(request, 'chat/tasks.html', {
        'tasks_assigned': tasks_assigned,
        'tasks_my': tasks_my,
        'profile': profile,
        'company_users': company_users.select_related('profile')
    })


@login_required
def create_task(request):
    profile = request.user.profile
    if request.method == 'POST':
        data = json.loads(request.body)
        assignee_ids = data.get('assigned_to')

        if not isinstance(assignee_ids, list):
            assignee_ids = [assignee_ids]

        if not assignee_ids or (len(assignee_ids) == 1 and assignee_ids[0] == 'ALL'):
            assignee_ids = list(User.objects.filter(
                profile__company_name=profile.company_name,
                profile__is_approved=True
            ).values_list('id', flat=True))

        created_tasks = []
        for uid in assignee_ids:
            if not uid:
                continue
            assignee = get_object_or_404(User, pk=uid)

            if profile.role == 'engineer' and assignee != request.user:
                return JsonResponse({'error': 'Engineers can only assign tasks to themselves.'}, status=403)

            if profile.role == 'manager':
                if assignee.profile.department != profile.department or (
                    assignee.profile.company != profile.company and
                    assignee.profile.company_name != profile.company_name
                ):
                    return JsonResponse({'error': 'Managers can only assign tasks to their department members.'}, status=403)

            task = Task.objects.create(
                title=data.get('title'),
                description=data.get('description'),
                assigned_to=assignee,
                assigned_by=request.user,
                company=profile.company,
                company_name=profile.company_name,
                department=profile.department,
                priority=data.get('priority', 'medium'),
                due_date=data.get('due_date') or None
            )
            created_tasks.append(task.pk)

        return JsonResponse({'status': 'ok', 'count': len(created_tasks)})
    return JsonResponse({'error': 'POST'}, status=405)


@login_required
def update_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if request.method == 'POST':
        data = json.loads(request.body)
        task.status = data.get('status')
        task.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'Invalid'}, status=400)


@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if task.assigned_by == request.user:
        task.delete()
        return JsonResponse({'status': 'deleted'})
    return JsonResponse({'error': 'Unauthorized'}, status=403)


@login_required
def summaries_api(request, room_name):
    """Returns JSON list of meeting summaries for this company+room."""
    profile = request.user.profile
    qs = MeetingRecord.objects.filter(room_name=room_name).order_by('-created_at')[:20]
    if profile.company:
        qs = MeetingRecord.objects.filter(room_name=room_name, company=profile.company).order_by('-created_at')[:20]
    elif profile.company_name:
        qs = MeetingRecord.objects.filter(room_name=room_name, company_name=profile.company_name).order_by('-created_at')[:20]

    return JsonResponse({'summaries': [
        {'summary': s.summary, 'date': s.created_at.strftime('%Y-%m-%d %H:%M')}
        for s in qs
    ]})


# ─────────────────────────────────────────────
#  JITSI MEET CALLING SYSTEM (Free, No API Key)
# ─────────────────────────────────────────────
@login_required
def jitsi_room_api(request, room_name):
    """
    POST: Returns a secure Jitsi Meet room name.
    Uses SHA256 hash of company name for unique, hard-to-guess rooms.
    No API key or payment required.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import hashlib
    profile = request.user.profile
    body = {}
    try:
        body = json.loads(request.body)
    except Exception:
        pass

    # ── Heartbeat-only mode: just refresh the session timestamp ──────────────
    if body.get('heartbeat'):
        qs = CallSession.objects.filter(room_name=room_name, is_active=True)
        if profile.company:
            qs = qs.filter(company=profile.company)
        else:
            qs = qs.filter(company_name=profile.company_name)
        qs.filter(caller=request.user).update(updated_at=timezone.now())
        return JsonResponse({'status': 'heartbeat_ok'})

    is_joining = body.get('joining', False)

    # Generate secure, deterministic room name per company
    company_raw  = (profile.company_name or 'co').lower().strip()
    company_hash = hashlib.sha256(company_raw.encode()).hexdigest()[:10]
    room_slug    = ''.join(c for c in room_name.lower() if c.isalnum())[:12]
    jitsi_room   = f"fn-{company_hash}-{room_slug}"

    # Track session in DB
    session_id = None
    if not is_joining:
        ghost_qs = CallSession.objects.filter(room_name=room_name, is_active=True)
        if profile.company:
            ghost_qs = ghost_qs.filter(company=profile.company)
        else:
            ghost_qs = ghost_qs.filter(company_name=profile.company_name)
        ghost_qs.update(is_active=False, is_ringing=False)

        session = CallSession.objects.create(
            room_name=room_name,
            company=profile.company,
            company_name=profile.company_name,
            caller=request.user,
            is_active=True,
            call_type=body.get('type', 'audio'),
            is_ringing=True,
        )
        session_id = session.id
        
        # FIX: Save participants for targeted calls
        participant_ids = body.get('participants', [])
        if participant_ids:
            # Filter out empty/invalid IDs
            valid_ids = [p for p in participant_ids if str(p).isdigit()]
            session.participants.set(valid_ids)
    else:
        qs = CallSession.objects.filter(room_name=room_name, is_active=True)
        if profile.company:
            qs = qs.filter(company=profile.company)
        else:
            qs = qs.filter(company_name=profile.company_name)
        session = qs.first()
        session_id = session.id if session else None

    # Heartbeat: keep session alive while caller is in Jitsi
    if not is_joining:
        session.save()  # Refreshes updated_at
    else:
        # When joining, also stop the ringing flag so others don't see it
        if session:
            session.is_ringing = False
            session.save()

    return JsonResponse({
        'jitsi_room': jitsi_room,
        'display_name': request.user.get_full_name() or request.user.username,
        'session_id': session_id,
    })
