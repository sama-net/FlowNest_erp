// ─── FlowNest Calling v4.3 — Floating Inline Widget ──────────────────────────
let activeSessionId  = null;
let _incomingPollInterval = null;
let _heartbeatInterval    = null;
let _audioContext    = null;
let _autoSumRec = null, _autoSumTimer = null, _autoSumText = '';
let _genRec = null,     _genText = '';
let _inCallRec = null,  _inCallTranscript = [];  // Records speech DURING the call

// ── AudioContext unlock ───────────────────────────────────────────────────────
document.addEventListener('click', () => {
    if (!_audioContext) try { _audioContext = new (window.AudioContext || window.webkitAudioContext)(); } catch(e){}
    if (_audioContext?.state === 'suspended') _audioContext.resume();
}, { passive: true });

// ─── Ring ─────────────────────────────────────────────────────────────────────
function playRingTone() {
    try {
        if (!_audioContext) _audioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (_audioContext.state === 'suspended') _audioContext.resume();
        window._isRinging = true;
        const beep = (f, d, t) => {
            const o = _audioContext.createOscillator(), g = _audioContext.createGain();
            o.connect(g); g.connect(_audioContext.destination);
            o.frequency.value = f; o.type = 'sine';
            g.gain.setValueAtTime(0.4, t); g.gain.exponentialRampToValueAtTime(0.001, t + d);
            o.start(t); o.stop(t + d);
        };
        const ring = () => {
            if (!window._isRinging) return;
            const n = _audioContext.currentTime;
            beep(880, 0.4, n); beep(660, 0.4, n + 0.5);
            setTimeout(ring, 2200);
        };
        ring();
    } catch(e) {}
}
function stopRinging() { window._isRinging = false; }

// ─── Incoming call overlay ────────────────────────────────────────────────────
function showIncomingCallOverlay(sessionId, callerName, callType) {
    document.getElementById('incoming-call-overlay')?.remove();
    const el = document.createElement('div');
    el.id = 'incoming-call-overlay';
    el.style.cssText = 'position:fixed;inset:0;z-index:9500;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,0.85);backdrop-filter:blur(20px)';
    el.innerHTML = `
      <div style="background:#111827;border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:40px;text-align:center;max-width:320px;width:100%">
        <div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#10b981,#059669);display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;color:#fff;margin:0 auto 20px;animation:pulse 1s infinite">${callerName[0].toUpperCase()}</div>
        <p style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px">اتصال وارد</p>
        <h3 style="font-size:22px;font-weight:900;color:#fff;margin-bottom:4px">${callerName}</h3>
        <p style="font-size:13px;color:#6b7280;margin-bottom:28px">${callType==='video'?'📹 فيديو':'🎤 صوت'}</p>
        <div style="display:flex;gap:16px;justify-content:center">
          <button onclick="rejectIncomingCall()" style="width:60px;height:60px;border-radius:50%;background:#dc2626;border:none;color:#fff;font-size:20px;cursor:pointer">✗</button>
          <button onclick="acceptIncomingCall(${sessionId})" style="width:60px;height:60px;border-radius:50%;background:#16a34a;border:none;color:#fff;font-size:20px;cursor:pointer;animation:pulse 1s infinite">✓</button>
        </div>
      </div>`;
    document.body.appendChild(el);
    playRingTone();
}
function rejectIncomingCall() {
    stopRinging();
    document.getElementById('incoming-call-overlay')?.remove();
}
async function acceptIncomingCall(sessionId) {
    stopRinging();
    document.getElementById('incoming-call-overlay')?.remove();
    const csrf = window._csrfToken || '';
    const res = await fetch(`/chat/api/call/daily-room/${window._roomName}/`, {
        method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'},
        body: JSON.stringify({joining:true})
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    activeSessionId = sessionId;
    openJitsiWidget(data.jitsi_room, data.display_name);
}

// ─── Start Call ───────────────────────────────────────────────────────────────
async function startCall(type='audio', participants=[]) {
    const csrf = window._csrfToken || '';
    const res = await fetch(`/chat/api/call/daily-room/${window._roomName}/`, {
        method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'},
        body: JSON.stringify({type, participants})
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    activeSessionId = data.session_id;
    openJitsiWidget(data.jitsi_room, data.display_name);
    startCallHeartbeat(window._roomName);
}

// ─── Floating Jitsi Widget ────────────────────────────────────────────────────
let _widgetMinimized = false;

function openJitsiWidget(roomName, displayName) {
    document.getElementById('jitsi-widget')?.remove();

    const params = [
        'config.prejoinConfig.enabled=false',
        'config.requireDisplayName=false',
        'config.lobby.enabled=false',
        'config.startWithVideoMuted=true',
        `userInfo.displayName=${encodeURIComponent(displayName||'مستخدم')}`,
    ].join('&');
    const src = `https://meet.jit.si/${roomName}#${params}`;

    const w = document.createElement('div');
    w.id = 'jitsi-widget';
    _widgetMinimized = false;
    w.style.cssText = `
        position:fixed; bottom:20px; right:20px; z-index:9000;
        width:420px; height:300px;
        border-radius:18px; overflow:hidden;
        box-shadow:0 20px 60px rgba(0,0,0,0.7);
        border:1px solid rgba(255,255,255,0.12);
        display:flex; flex-direction:column;
        transition: width 0.3s, height 0.3s;
    `;

    // Header bar (drag handle + controls)
    const hdr = document.createElement('div');
    hdr.id = 'jitsi-widget-hdr';
    hdr.style.cssText = `
        flex-shrink:0; height:42px; background:#0d0f1a;
        display:flex; align-items:center; padding:0 12px; gap:8px;
        cursor:grab; user-select:none;
        border-bottom:1px solid rgba(255,255,255,0.06);
    `;
    hdr.innerHTML = `
        <span style="width:8px;height:8px;background:#10b981;border-radius:50%;animation:pulse 1.5s infinite;flex-shrink:0"></span>
        <span style="font-size:12px;font-weight:700;color:#fff;flex:1">🔒 مكالمة نشطة</span>
        <button id="jw-min" title="تصغير" onclick="toggleWidgetMinimize()" style="background:rgba(255,255,255,0.08);border:none;color:#ccc;width:28px;height:28px;border-radius:8px;cursor:pointer;font-size:14px">_</button>
        <button id="jw-max" title="تكبير" onclick="maximizeWidget()" style="background:rgba(255,255,255,0.08);border:none;color:#ccc;width:28px;height:28px;border-radius:8px;cursor:pointer;font-size:12px">⛶</button>
        <button onclick="endCallFromWidget()" title="إنهاء" style="background:#dc2626;border:none;color:#fff;width:28px;height:28px;border-radius:8px;cursor:pointer;font-size:14px">✕</button>
    `;

    // Container for Jitsi SDK (fills remaining space)
    const jitsiContainer = document.createElement('div');
    jitsiContainer.id = 'jitsi-sdk-container';
    jitsiContainer.style.cssText = 'flex:1;width:100%;overflow:hidden;background:#000';

    w.appendChild(hdr);
    w.appendChild(jitsiContainer);
    document.body.appendChild(w);

    // Make widget draggable via header
    makeDraggable(w, hdr);

    // Start capturing speech DURING the call
    _startInCallRecording();

    // Responsive: on mobile, show full-screen
    if (window.innerWidth < 640) {
        w.style.cssText += ';width:100%;height:55vh;bottom:0;right:0;border-radius:18px 18px 0 0;';
    }

    // ── Load Jitsi via External API SDK (bypasses iframe restrictions) ──
    function initJitsiSDK() {
        if (typeof JitsiMeetExternalAPI === 'undefined') {
            // SDK not loaded yet, load it dynamically then retry
            const s = document.createElement('script');
            s.src = 'https://meet.jit.si/external_api.js';
            s.onload = () => initJitsiSDK();
            s.onerror = () => console.error('Jitsi SDK failed to load');
            document.head.appendChild(s);
            return;
        }

        window._jitsiWidgetApi = new JitsiMeetExternalAPI('meet.jit.si', {
            roomName,
            width: '100%',
            height: '100%',
            parentNode: jitsiContainer,
            userInfo: { displayName: displayName || 'مستخدم', email: '' },
            configOverwrite: {
                startWithVideoMuted: true,
                startWithAudioMuted: false,
                prejoinConfig: { enabled: false },
                requireDisplayName: false,
                enableLobbyChat: false,
                lobby: { enabled: false },
                disableDeepLinking: true,
                enableWelcomePage: false,
            },
            interfaceConfigOverwrite: {
                SHOW_JITSI_WATERMARK: false,
                SHOW_BRAND_WATERMARK: false,
                SHOW_POWERED_BY: false,
                TOOLBAR_BUTTONS: ['microphone','camera','desktop','fullscreen','hangup','chat','settings','raisehand','tileview'],
            },
            lang: 'ar',
        });

        // If user clicks hangup INSIDE Jitsi → same as our ✕ button
        window._jitsiWidgetApi.addEventListener('videoConferenceLeft', () => {
            window.endCallFromWidget();
        });
    }
    initJitsiSDK();
}

function makeDraggable(el, handle) {
    let startX, startY, startLeft, startBottom;
    handle.onmousedown = e => {
        if (e.target.tagName === 'BUTTON') return;
        startX = e.clientX; startY = e.clientY;
        const rect = el.getBoundingClientRect();
        startLeft = rect.left; startBottom = window.innerHeight - rect.bottom;
        // Overlay to capture mouse over iframe during drag
        const cover = document.createElement('div');
        cover.id = 'drag-cover';
        cover.style.cssText = 'position:fixed;inset:0;z-index:8999;cursor:grabbing';
        document.body.appendChild(cover);
        handle.style.cursor = 'grabbing';

        const onMove = e => {
            const dx = e.clientX - startX, dy = e.clientY - startY;
            el.style.left  = (startLeft + dx) + 'px';
            el.style.right = 'auto';
            el.style.bottom = (startBottom - dy) + 'px';
        };
        const onUp = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.getElementById('drag-cover')?.remove();
            handle.style.cursor = 'grab';
        };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    };
}

window.toggleWidgetMinimize = function() {
    const w = document.getElementById('jitsi-widget');
    const jc = document.getElementById('jitsi-sdk-container');
    if (!w) return;
    _widgetMinimized = !_widgetMinimized;
    if (_widgetMinimized) {
        w.style.width  = '220px';
        w.style.height = '42px';
        if (jc) jc.style.display = 'none';
        document.getElementById('jw-min').textContent = '⬜';
    } else {
        w.style.width  = '420px';
        w.style.height = '300px';
        if (jc) jc.style.display = '';
        document.getElementById('jw-min').textContent = '_';
    }
};

window.maximizeWidget = function() {
    const w = document.getElementById('jitsi-widget');
    const jc = document.getElementById('jitsi-sdk-container');
    if (!w) return;
    _widgetMinimized = false;
    w.style.cssText = `
        position:fixed; inset:0; z-index:9000;
        width:100%; height:100%;
        border-radius:0; overflow:hidden;
        display:flex; flex-direction:column;
        transition: width 0.3s, height 0.3s;
    `;
    if (jc) jc.style.display = '';
};

window.endCallFromWidget = function() {
    // Prevent double-call (Jitsi hangup fires this, then we dispose)
    if (!document.getElementById('jitsi-widget')) return;

    activeSessionId = null;
    stopCallHeartbeat();

    // Dispose Jitsi SDK
    if (window._jitsiWidgetApi) {
        try { window._jitsiWidgetApi.dispose(); } catch(e) {}
        window._jitsiWidgetApi = null;
    }

    // Stop in-call recording and collect transcript
    _stopInCallRecording();
    const capturedTranscript = _inCallTranscript.join(' ').trim();
    _inCallTranscript = [];

    document.getElementById('jitsi-widget')?.remove();
    const csrf = window._csrfToken || '';
    fetch(`/chat/api/call/end/${window._roomName}/`, {
        method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'}
    }).catch(()=>{});

    if (capturedTranscript.length >= 15) {
        _autoSumText = capturedTranscript;
        _sendAutoSummary();
    } else {
        startAutoCallSummary();
    }
};

// ─── In-Call Speech Recording ──────────────────────────────────────────────────
function _startInCallRecording() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    _inCallTranscript = [];
    _inCallRec = new SR();
    _inCallRec.continuous = true;
    _inCallRec.interimResults = false;
    _inCallRec.lang = 'ar-SA';
    _inCallRec.onresult = e => {
        for (let i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) {
                const t = e.results[i][0].transcript.trim();
                if (t) _inCallTranscript.push(t);
            }
        }
    };
    _inCallRec.onerror = () => {};
    _inCallRec.onend = () => {
        // Keep restarting as long as call is active
        if (activeSessionId && _inCallRec) try { _inCallRec.start(); } catch(e) {}
    };
    try { _inCallRec.start(); } catch(e) {}
}

function _stopInCallRecording() {
    if (_inCallRec) {
        try { _inCallRec.stop(); } catch(e) {}
        _inCallRec = null;
    }
}

// ─── Auto Summary after Call ──────────────────────────────────────────────────
function startAutoCallSummary() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    document.getElementById('auto-sum-banner')?.remove();

    const banner = document.createElement('div');
    banner.id = 'auto-sum-banner';
    banner.style.cssText = `position:fixed;bottom:28px;left:50%;transform:translateX(-50%);
        z-index:9999;background:linear-gradient(135deg,#4f46e5,#7c3aed);
        color:#fff;border-radius:20px;padding:14px 22px;font-size:13px;
        font-weight:700;box-shadow:0 8px 32px rgba(79,70,229,0.5);
        display:flex;align-items:center;gap:10px;min-width:280px`;
    banner.innerHTML = `
        <i class="fas fa-microphone" style="font-size:18px"></i>
        <span>🎤 قل ملخص الاجتماع...</span>
        <span id="auto-sum-countdown" style="background:rgba(255,255,255,0.2);border-radius:8px;padding:2px 8px">60</span>
        <button onclick="cancelAutoSummary()" style="margin-right:auto;background:rgba(255,255,255,0.15);border:none;color:#fff;border-radius:8px;padding:2px 8px;cursor:pointer;font-size:11px">تخطي</button>
    `;
    document.body.appendChild(banner);

    _autoSumText = '';
    let seconds = 60;

    _autoSumTimer = setInterval(() => {
        seconds--;
        const cd = document.getElementById('auto-sum-countdown');
        if (cd) cd.textContent = seconds;
        if (seconds <= 0) { clearInterval(_autoSumTimer); _autoSumTimer = null; _sendAutoSummary(); }
    }, 1000);

    if (!SR) return;
    _autoSumRec = new SR();
    _autoSumRec.continuous = true; _autoSumRec.interimResults = true; _autoSumRec.lang = 'ar-SA';
    _autoSumRec.onresult = e => {
        let txt = '';
        for (let i = 0; i < e.results.length; i++) txt += e.results[i][0].transcript + ' ';
        _autoSumText = txt.trim();
        if (_autoSumText.length > 80 && seconds > 5) { seconds = 5; const cd = document.getElementById('auto-sum-countdown'); if (cd) cd.textContent = '5'; }
    };
    _autoSumRec.onerror = () => {};
    _autoSumRec.onend = () => { if (_autoSumTimer) try { _autoSumRec.start(); } catch(e){} };
    try { _autoSumRec.start(); } catch(e) {}
}

function cancelAutoSummary() {
    if (_autoSumRec) { try { _autoSumRec.stop(); } catch(e){} _autoSumRec = null; }
    if (_autoSumTimer) { clearInterval(_autoSumTimer); _autoSumTimer = null; }
    document.getElementById('auto-sum-banner')?.remove();
}

async function _sendAutoSummary() {
    if (_autoSumRec) { try { _autoSumRec.stop(); } catch(e){} _autoSumRec = null; }
    document.getElementById('auto-sum-banner')?.remove();
    if (!_autoSumText || _autoSumText.trim().length < 15) return;
    const toast = document.createElement('div');
    toast.style.cssText = `position:fixed;bottom:28px;left:50%;transform:translateX(-50%);z-index:9999;background:#4f46e5;color:#fff;padding:12px 22px;border-radius:16px;font-weight:700;font-size:13px;display:flex;align-items:center;gap:8px;box-shadow:0 8px 28px rgba(79,70,229,0.4)`;
    toast.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التلخيص...';
    document.body.appendChild(toast);
    try {
        const csrf = window._csrfToken || '';
        const res = await fetch('/chat/api/call/summarize/', {
            method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'},
            body: JSON.stringify({transcript: _autoSumText, room_name: window._roomName})
        });
        const data = await res.json();
        toast.remove();
        if (data.summary || data.tasks?.length) showCallSummaryResult(data.summary, data.tasks);
    } catch(e) { toast.remove(); }
}

// ─── General Mic (for any discussion) ────────────────────────────────────────
window.toggleGeneralSummaryMic = function() {
    const btn = document.getElementById('general-sum-btn');
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('استخدم Chrome'); return; }
    if (_genRec) {
        _genRec.stop(); _genRec = null;
        if (btn) btn.innerHTML = '<i class="fas fa-microphone text-purple-400 text-sm"></i>';
        if (_genText && _genText.length > 10) _sendGeneralSummary(_genText);
        _genText = '';
        return;
    }
    _genText = '';
    _genRec = new SR();
    _genRec.continuous = true; _genRec.interimResults = true; _genRec.lang = 'ar-SA';
    _genRec.onresult = e => { let t=''; for(let i=0;i<e.results.length;i++) t+=e.results[i][0].transcript+' '; _genText=t.trim(); };
    _genRec.onerror = ()=>{};
    _genRec.onend = ()=>{ if(_genRec) try{_genRec.start();}catch(e){} };
    _genRec.start();
    if (btn) btn.innerHTML = '<i class="fas fa-stop text-red-400 text-sm"></i>';
};

async function _sendGeneralSummary(text) {
    const toast = document.createElement('div');
    toast.style.cssText = `position:fixed;bottom:28px;left:50%;transform:translateX(-50%);z-index:9999;background:#4f46e5;color:#fff;padding:12px 22px;border-radius:16px;font-weight:700;font-size:13px;display:flex;align-items:center;gap:8px`;
    toast.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التلخيص...';
    document.body.appendChild(toast);
    try {
        const csrf = window._csrfToken || '';
        const res = await fetch('/chat/api/call/summarize/', {
            method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'},
            body: JSON.stringify({transcript: text, room_name: window._roomName})
        });
        const data = await res.json();
        toast.remove();
        if (data.summary || data.tasks?.length) showCallSummaryResult(data.summary, data.tasks);
    } catch(e) { toast.remove(); }
}

// ─── Summary Result Modal ─────────────────────────────────────────────────────
function showCallSummaryResult(summary, tasks) {
    document.getElementById('call-summary-result')?.remove();
    let tasksHtml = '';
    if (tasks?.length) {
        tasksHtml = `<div style="margin-top:16px;text-align:right">
            <p style="color:#facc15;font-weight:700;font-size:12px;margin-bottom:8px">📋 المهام المحفوظة تلقائياً</p>
            <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:6px">
                ${tasks.map(t=>`<li style="background:rgba(255,255,255,0.05);padding:10px 14px;border-radius:12px;font-size:12px;color:#d1d5db;display:flex;justify-content:flex-end;align-items:center;gap:8px"><span>${t}</span><span style="color:#22c55e">✓</span></li>`).join('')}
            </ul></div>`;
    }
    const m = document.createElement('div');
    m.id = 'call-summary-result';
    m.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,0.85);backdrop-filter:blur(20px)';
    m.innerHTML = `
      <div style="background:#0d0f1a;border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:24px;max-width:480px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,0.8)">
        <div style="width:48px;height:48px;background:rgba(139,92,246,0.2);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:20px;margin:0 auto 16px">✨</div>
        <h3 style="font-size:17px;font-weight:900;color:#fff;margin:0 0 12px;text-align:center">ملخص الاجتماع</h3>
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:16px;text-align:right;font-size:13px;color:#d1d5db;line-height:1.7;max-height:180px;overflow-y:auto">
            ${summary || 'لم يُلتقط محتوى كافٍ.'}
        </div>
        ${tasksHtml}
        <div style="display:flex;gap:10px;margin-top:20px">
          <button onclick="document.getElementById('call-summary-result').remove()" style="flex:1;padding:12px;border-radius:12px;background:rgba(255,255,255,0.06);border:none;color:#9ca3af;font-weight:700;cursor:pointer;font-size:13px">إغلاق</button>
          <button onclick="refreshSummariesPanel();document.getElementById('call-summary-result').remove()" style="flex:1;padding:12px;border-radius:12px;background:#4f46e5;border:none;color:#fff;font-weight:700;cursor:pointer;font-size:13px">عرض في الملخصات ←</button>
        </div>
      </div>`;
    document.body.appendChild(m);
}

// ─── Refresh Summaries Panel ──────────────────────────────────────────────────
function refreshSummariesPanel() {
    fetch(`/chat/api/summaries/${window._roomName}/`)
        .then(r=>r.json())
        .then(data=>{
            if (!data.summaries) return;
            const list = document.getElementById('summaries-list');
            if (!list) return;
            list.innerHTML = data.summaries.length
                ? data.summaries.map(s=>`
                    <div style="background:rgba(255,255,255,0.04);border-radius:14px;padding:12px;border:1px solid rgba(255,255,255,0.05)">
                        <p style="font-size:10px;color:#4b5563;margin:0 0 4px">${s.date}</p>
                        <p style="font-size:12px;color:#d1d5db;line-height:1.6;margin:0">${s.summary}</p>
                    </div>`).join('')
                : '<p style="font-size:12px;color:#4b5563;text-align:center;padding:40px 0">لا توجد ملخصات بعد</p>';
        }).catch(()=>{});
}

// ─── Heartbeat ────────────────────────────────────────────────────────────────
function startCallHeartbeat(roomName) {
    stopCallHeartbeat();
    _heartbeatInterval = setInterval(async () => {
        if (!activeSessionId) { stopCallHeartbeat(); return; }
        const csrf = window._csrfToken || '';
        fetch(`/chat/api/call/daily-room/${roomName}/`, {
            method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'},
            body: JSON.stringify({heartbeat:true})
        }).catch(()=>{});
    }, 30000);
}
function stopCallHeartbeat() {
    if (_heartbeatInterval) { clearInterval(_heartbeatInterval); _heartbeatInterval = null; }
}

// ─── leaveCall (cleanup only) ─────────────────────────────────────────────────
async function leaveCall() {
    stopCallHeartbeat();
    document.getElementById('jitsi-widget')?.remove();
    const csrf = window._csrfToken || '';
    if (window._roomName) {
        await fetch(`/chat/api/call/end/${window._roomName}/`, {
            method:'POST', headers:{'X-CSRFToken':csrf,'Content-Type':'application/json'}
        }).catch(()=>{});
    }
    activeSessionId = null;
}

// ─── Incoming Call Polling ────────────────────────────────────────────────────
function startIncomingCallPolling(roomName) {
    if (_incomingPollInterval) clearInterval(_incomingPollInterval);
    _incomingPollInterval = setInterval(async () => {
        if (activeSessionId) return;
        try {
            const res = await fetch(`/chat/api/call/check/${roomName}/`);
            const d = await res.json();
            if (d.active && !document.getElementById('incoming-call-overlay'))
                showIncomingCallOverlay(d.session_id, d.caller, d.type);
        } catch(e) {}
    }, 2500);
}