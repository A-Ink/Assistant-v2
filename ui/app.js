/* =====================================================
   ALLIANCE TERMINAL — Frontend Logic v2
   Boot sequence, sparklines, smart schedule, codex
   ===================================================== */

// ---- STATE ----
let leftPanelVisible = true;
let rightPanelVisible = true;
let isGenerating = false;
let diagnosticsTimer = null;
let clockTimer = null;
let ramHistory = [];
const RAM_HISTORY_MAX = 30;

// ---- DOM REFS ----
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnToggleLeft = document.getElementById('btn-toggle-left');
const btnToggleRight = document.getElementById('btn-toggle-right');
const btnMinimize = document.getElementById('btn-minimize');
const btnClose = document.getElementById('btn-close');
const panelLeft = document.getElementById('panel-left');
const panelRight = document.getElementById('panel-right');
const clockEl = document.getElementById('clock');
const clockDateEl = document.getElementById('clock-date');
const ramSystem = document.getElementById('ram-system');
const ramApp = document.getElementById('ram-app');
const modelBadge = document.getElementById('model-badge');
const deviceBadge = document.getElementById('device-badge');
const dossierContent = document.getElementById('dossier-content');
const moodContent = document.getElementById('mood-content');
const scheduleContent = document.getElementById('schedule-content');
const bootScreen = document.getElementById('boot-screen');
const bootLog = document.getElementById('boot-log');
const sparklineCanvas = document.getElementById('sparkline-canvas');

// ---- STREAMING & TIMER STATE ----
let thinkingInterval = null;
let thinkingTime = 0;
let currentStreamBubble = null;

function startThinkingTimer() {
    // 1. Create a blank message bubble for the AI
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message normandy-msg';
    
    const spanSpeaker = document.createElement('span');
    spanSpeaker.className = 'speaker normandy-speaker';
    spanSpeaker.innerHTML = 'NORMANDY:';
    
    const spanMessage = document.createElement('span');
    spanMessage.className = 'message-text';
    spanMessage.style.color = '#00e5ff';
    spanMessage.style.fontFamily = 'monospace';
    spanMessage.innerText = '[TACTICAL ANALYSIS IN PROGRESS... 0.0s]';

    msgDiv.appendChild(spanSpeaker);
    msgDiv.appendChild(spanMessage);
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    currentStreamBubble = spanMessage;
    thinkingTime = 0;
    
    // 2. Start the high-precision timer
    thinkingInterval = setInterval(() => {
        thinkingTime += 0.1;
        if (currentStreamBubble && thinkingInterval) {
            currentStreamBubble.innerText = `[TACTICAL ANALYSIS IN PROGRESS... ${thinkingTime.toFixed(1)}s]`;
        }
    }, 100);
}

// 3. Exposed API for Python to inject words
window.streamToken = function(token) {
    if (thinkingInterval) {
        // The millisecond the AI wakes up, kill the timer!
        clearInterval(thinkingInterval);
        thinkingInterval = null;
        currentStreamBubble.innerHTML = ''; 
        currentStreamBubble.style.color = ''; 
        currentStreamBubble.style.fontFamily = ''; 
    }
    
    // Append the new word and auto-scroll
    if (currentStreamBubble) {
        currentStreamBubble.innerHTML += token;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
};

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initAutoExpand();
    initPanelToggles();
    initWindowControls();
    initChat();
    // Diagnostics start after boot completes
});

// Wait for pywebview bridge to be ready
window.addEventListener('pywebviewready', () => {
    // Trigger boot sequence from Python
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.trigger_boot();
    }
});

// =====================================================
// BOOT SEQUENCE
// =====================================================

window.appendBootLine = function(text, type) {
    type = type || 'info';
    const line = document.createElement('div');
    line.className = `boot-line boot-${type}`;
    line.textContent = text;
    bootLog.appendChild(line);
    bootLog.scrollTop = bootLog.scrollHeight;
};

window.bootComplete = function() {
    // Fade out boot screen
    bootScreen.classList.add('fade-out');

    // Show main app
    const app = document.getElementById('app');
    app.classList.remove('app-hidden');

    // Remove boot screen after animation
    setTimeout(() => {
        bootScreen.style.display = 'none';
    }, 900);

    // Start diagnostics and load data
    initDiagnostics();
    loadPanelData();
    loadDeviceInfo();
};

// =====================================================
// CLOCK (LEFT PANEL)
// =====================================================

function initClock() {
    function update() {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('en-GB', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        clockDateEl.textContent = now.toLocaleDateString('en-GB', {
            weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'
        }).toUpperCase();
    }
    update();
    clockTimer = setInterval(update, 1000);
}

// =====================================================
// FOCUS-AWARE DIAGNOSTICS + SPARKLINE
// =====================================================

function initDiagnostics() {
    async function fetchStats() {
        if (!document.hasFocus()) return;
        if (!window.pywebview || !window.pywebview.api) return;

        try {
            const stats = await window.pywebview.api.get_system_stats();
            if (stats) {
                ramSystem.textContent = `${stats.system_percent}%`;
                ramApp.textContent = `${stats.app_mb}MB (${stats.app_percent}%)`;

                // Update sparkline history
                ramHistory.push(stats.system_percent);
                if (ramHistory.length > RAM_HISTORY_MAX) {
                    ramHistory.shift();
                }
                drawSparkline();
            }
        } catch (e) {
            // Bridge may not be ready
        }
    }

    fetchStats();
    diagnosticsTimer = setInterval(fetchStats, 5000);
}

function drawSparkline() {
    if (!sparklineCanvas) return;
    const ctx = sparklineCanvas.getContext('2d');
    const w = sparklineCanvas.width;
    const h = sparklineCanvas.height;

    ctx.clearRect(0, 0, w, h);

    if (ramHistory.length < 2) return;

    // Background grid lines
    ctx.strokeStyle = 'rgba(0, 180, 255, 0.06)';
    ctx.lineWidth = 0.5;
    for (let y = 0; y < h; y += 10) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
    }

    // Draw line
    const step = w / (RAM_HISTORY_MAX - 1);
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.6)';
    ctx.lineWidth = 1.5;

    for (let i = 0; i < ramHistory.length; i++) {
        const x = i * step;
        const y = h - (ramHistory[i] / 100) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill under line
    const lastX = (ramHistory.length - 1) * step;
    const lastY = h - (ramHistory[ramHistory.length - 1] / 100) * h;
    ctx.lineTo(lastX, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(0, 255, 255, 0.04)';
    ctx.fill();
}

// =====================================================
// DEVICE INFO
// =====================================================

async function loadDeviceInfo() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
        const info = await window.pywebview.api.get_device_info();
        if (info) {
            modelBadge.textContent = info.model || '—';
            deviceBadge.textContent = info.device || '—';
            if (info.device === 'NPU') {
                deviceBadge.className = 'diag-value device-npu';
            } else {
                deviceBadge.className = 'diag-value diag-gold';
            }
        }
    } catch (e) { /* bridge not ready */ }
}

// =====================================================
// PANEL TOGGLES
// =====================================================

function initPanelToggles() {
    btnToggleLeft.addEventListener('click', () => {
        leftPanelVisible = !leftPanelVisible;
        panelLeft.classList.toggle('collapsed', !leftPanelVisible);
        btnToggleLeft.textContent = leftPanelVisible ? '◀' : '▶';
    });

    btnToggleRight.addEventListener('click', () => {
        rightPanelVisible = !rightPanelVisible;
        panelRight.classList.toggle('collapsed', !rightPanelVisible);
        btnToggleRight.textContent = rightPanelVisible ? '▶' : '◀';
    });
}

// =====================================================
// WINDOW CONTROLS
// =====================================================

function initWindowControls() {
    btnMinimize.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.minimize_window();
        }
    });

    btnClose.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.close_window();
        }
    });
}

// =====================================================
// AUTO-EXPANDING TEXTAREA
// =====================================================

function initAutoExpand() {
    chatInput.addEventListener('input', autoResizeInput);
}

function autoResizeInput() {
    chatInput.style.height = '45px';
    const scrollH = chatInput.scrollHeight;
    chatInput.style.height = Math.min(scrollH, 150) + 'px';
}

// =====================================================
// CHAT
// =====================================================

function initChat() {
    btnSend.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || isGenerating) return;

    appendMessage('CMDR N7:', text, 'commander');
    chatInput.value = '';
    autoResizeInput();

    isGenerating = true;
    document.getElementById('app').classList.add('loading');
    
    // Start the Tactical Timer instead of the typing indicator!
    startThinkingTimer();

    try {
        if (window.pywebview && window.pywebview.api) {
            const result = await window.pywebview.api.send_message(text);
            
            if (result && result.response) {
                // When generation finishes, lock in the clean HTML (hides the tags)
                if (currentStreamBubble) {
                    currentStreamBubble.innerHTML = result.response;
                    currentStreamBubble.removeAttribute('id');
                    currentStreamBubble = null;
                }

                if (result.facts_saved) await refreshDossier();
                if (result.schedule_updated) await refreshSchedule();
            } else if (result && result.error) {
                appendMessage('SYSTEM:', result.error, 'error');
            }
        } else {
            appendMessage('SYSTEM:', 'Pywebview bridge not available.', 'error');
        }
    } catch (e) {
        appendMessage('SYSTEM:', `Communication error: ${e.message}`, 'error');
    } finally {
        isGenerating = false;
        document.getElementById('app').classList.remove('loading');
    }
}

function appendMessage(speaker, content, type) {
    const msgDiv = document.createElement('div');
    const typeClass = type === 'commander' ? 'commander-msg' :
                      type === 'normandy' ? 'normandy-msg' :
                      type === 'error' ? 'error-msg' :
                      type === 'reminder' ? 'reminder-msg' : 'system-msg';
    const speakerClass = type === 'commander' ? 'commander-speaker' :
                         type === 'reminder' ? 'normandy-speaker' :
                         type === 'normandy' ? 'normandy-speaker' :
                         'normandy-speaker';

    msgDiv.className = `message ${typeClass}`;
    msgDiv.innerHTML = `
        <span class="speaker ${speakerClass}">${speaker}</span>
        <span class="message-text">${content}</span>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'message normandy-msg typing-indicator';
    div.innerHTML = `
        <span class="speaker normandy-speaker">NORMANDY:</span>
        <div class="typing-dots"><span></span><span></span><span></span></div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function removeTypingIndicator(el) {
    if (el && el.parentNode) {
        el.parentNode.removeChild(el);
    }
}

// =====================================================
// PANEL DATA LOADING
// =====================================================

async function loadPanelData() {
    if (!window.pywebview || !window.pywebview.api) return;

    try {
        const [dossier, mood, schedule] = await Promise.all([
            window.pywebview.api.get_dossier(),
            window.pywebview.api.get_mood(),
            window.pywebview.api.get_schedule(),
        ]);

        if (dossier) dossierContent.innerHTML = dossier;
        if (mood) moodContent.innerHTML = mood;
        if (schedule) scheduleContent.innerHTML = schedule;
    } catch (e) {
        // Bridge not ready
    }
}

async function refreshDossier() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
        const dossier = await window.pywebview.api.get_dossier();
        if (dossier) dossierContent.innerHTML = dossier;
    } catch (e) { /* ignore */ }
}

async function refreshSchedule() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
        const schedule = await window.pywebview.api.get_schedule();
        if (schedule) scheduleContent.innerHTML = schedule;
    } catch (e) { /* ignore */ }
}

// =====================================================
// EXTERNAL CALLS (from Python via evaluate_js)
// =====================================================

window.refreshDossier = refreshDossier;
window.refreshSchedule = refreshSchedule;

window.appendSystemMessage = function(text) {
    appendMessage('SYSTEM:', text, 'system');
};

window.appendReminderMessage = function(text) {
    appendMessage('NORMANDY:', text, 'reminder');
};