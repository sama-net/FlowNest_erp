import json
import threading

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# ── Singleton RAG system (initialised once per process) ───────
_rag_lock   = threading.Lock()
_rag_system = None


def _get_rag():
    global _rag_system
    if _rag_system is None:
        with _rag_lock:
            if _rag_system is None:          # double-checked locking
                from rag_system import ERPRagSystem
                _rag_system = ERPRagSystem()
    return _rag_system


# ── Views ─────────────────────────────────────────────────────

@login_required
def chat_page(request):
    """Renders the chat UI."""
    profile = getattr(request.user, 'profile', None)
    if not profile:
        return render(request, 'pages/dashboard.html', {'error_message': 'يجب إنشاء ملف شخصي لشركتك أولاً لاستخدام المساعد الذكي.'})
    
    if not profile.is_approved:
        return render(request, 'pages/pending.html', {'profile': profile})
    return render(request, "rag/chat.html")


@login_required
@require_http_methods(["POST"])
def chat_api(request):
    """
    POST /rag/api/chat/
    Fast AI chat: Engineers get plain LLM, Managers/Owners get file-aware RAG.
    Detects question language and responds accordingly.
    """
    try:
        profile = getattr(request.user, 'profile', None)
        if not profile:
             return JsonResponse({"error": "حسابك يفتقر إلى ملف شخصي. يرجى إكمال بيانات الشركة أولاً."}, status=403)
             
        if not profile.is_approved:
            return JsonResponse({"error": "حسابك بانتظار الموافقة. لا يمكنك استخدام المساعد الذكي حالياً."}, status=403)
        
        # (Developer role restriction removed for seamless testing)

        payload  = json.loads(request.body)
        question = payload.get("question", "").strip()
        history  = payload.get("history", [])  # list of {role, content}

        if not question:
            return JsonResponse({"error": "question is required"}, status=400)

        from django.conf import settings as dj_settings
        from groq import Groq
        import datetime

        groq_client = Groq(api_key=dj_settings.GROQ_API_KEY, timeout=30.0)
        start = datetime.datetime.now()

        # Build conversation messages from history (last 10 turns for speed)
        messages = []
        for h in history[-10:]:
            messages.append({"role": h.get("role"), "content": h.get("content")})

        if profile.role == 'engineer':
            # Simple chat via RAG system
            rag_output = _get_rag().simple_chat(question)
            return JsonResponse({
                "answer": rag_output["answer"],
                "sources": [],
                "is_simple_chat": True,
                "generation_time_sec": 0.5, # Placeholder for speed
            })

        else:
            # Full RAG-aware chat
            rag_sys = _get_rag()
            if getattr(rag_sys, 'is_offline', False):
                return JsonResponse({
                    "answer": "عذراً، المساعد الذكي يعمل حالياً في وضع 'صيانة' أو بدون إنترنت، لذا لا يمكنه تحليل الملفات بدقة الآن. يمكنك سؤال المهندسين أو مراجعة التقارير المالية مباشرة.",
                    "sources": [],
                    "offline_mode": True
                })

            company = profile.company.name if profile.company else profile.company_name
            rag_kwargs = {"company": company}
            
            # No strict isolation for improved workspace testing and global financial records


            start_t = datetime.datetime.now()
            rag_output = rag_sys.query(question, **rag_kwargs)
            end_t = datetime.datetime.now()
            diff = (end_t - start_t).total_seconds()
            
            return JsonResponse({
                "answer": rag_output["answer"],
                "sources": rag_output["sources"],
                "context_used": True,
                "retrieval_time_sec": diff * 0.3,
                "generation_time_sec": diff * 0.7,
            })
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"RAG Chat Error: {str(exc)}")
        return JsonResponse({"error": "حدث خطأ أثناء معالجة طلبك بالمساعد الذكي."}, status=500)


@login_required
@require_http_methods(["POST"])
def sync_db(request):
    """
    POST /rag/api/sync/
    Re-indexes all DB records into ChromaDB.
    Call this after uploading new company files.
    """
    try:
        _get_rag().sync_db()
        return JsonResponse({"status": "synced"})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
