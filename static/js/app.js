const API = '';
const STORAGE_KEY = 'claude-editor-state';

let state = {
    exampleFile: null,
    examplePath: null,
    rawFile: null,
    rawPath: null,
    outputFormat: 'reel',
    brand: 'default',
    jobId: null,
    eventSource: null,
    inspectorVisible: true,
    activeView: 'edit',
    activeBrowserTab: 'media',
    activeInspectorTab: 'settings',
};

/* ─── LocalStorage Persistence ─────────────────────────────────────────── */

function saveState() {
    const persist = {
        outputFormat: state.outputFormat,
        brand: state.brand,
        inspectorVisible: state.inspectorVisible,
        activeView: state.activeView,
        activeBrowserTab: state.activeBrowserTab,
        activeInspectorTab: state.activeInspectorTab,
        instructions: document.getElementById('instructions')?.value || '',
        premiumLut: document.getElementById('premium-lut')?.value || 'auto',
        premiumCaptions: document.getElementById('premium-captions')?.value || 'auto',
        premiumGrain: document.getElementById('premium-grain')?.value || 'auto',
        premiumPlatform: document.getElementById('premium-platform')?.value || 'auto',
        premiumNormalize: document.getElementById('premium-normalize')?.checked ?? true,
        premiumDenoise: document.getElementById('premium-denoise')?.checked ?? true,
        premiumVoice: document.getElementById('premium-voice')?.checked ?? false,
        premiumVignette: document.getElementById('premium-vignette')?.checked ?? false,
        collapsedSections: getCollapsedSections(),
    };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(persist)); } catch (e) {}
}

function loadState() {
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
        if (!saved) return;

        state.outputFormat = saved.outputFormat || 'reel';
        state.brand = saved.brand || 'default';
        state.inspectorVisible = saved.inspectorVisible !== false;
        state.activeView = saved.activeView || 'edit';
        state.activeBrowserTab = saved.activeBrowserTab || 'media';
        state.activeInspectorTab = saved.activeInspectorTab || 'settings';

        // Restore format card
        document.querySelectorAll('.format-card').forEach(b => {
            b.classList.toggle('active', b.dataset.format === state.outputFormat);
        });

        // Restore brand dropdown
        const brandSelect = document.getElementById('brand-select');
        if (brandSelect) brandSelect.value = state.brand;

        // Restore instructions
        if (saved.instructions) {
            const el = document.getElementById('instructions');
            if (el) el.value = saved.instructions;
        }

        // Restore premium settings
        setSelectValue('premium-lut', saved.premiumLut);
        setSelectValue('premium-captions', saved.premiumCaptions);
        setSelectValue('premium-grain', saved.premiumGrain);
        setSelectValue('premium-platform', saved.premiumPlatform);
        setCheckbox('premium-normalize', saved.premiumNormalize);
        setCheckbox('premium-denoise', saved.premiumDenoise);
        setCheckbox('premium-voice', saved.premiumVoice);
        setCheckbox('premium-vignette', saved.premiumVignette);

        // Restore inspector visibility
        const inspector = document.getElementById('inspector-panel');
        if (inspector) inspector.classList.toggle('hidden', !state.inspectorVisible);

        // Restore view tabs
        switchView(state.activeView, true);
        switchBrowserTab(state.activeBrowserTab, true);
        switchInspectorTab(state.activeInspectorTab, true);

        // Restore collapsed sections
        if (saved.collapsedSections) restoreCollapsedSections(saved.collapsedSections);

    } catch (e) {}
}

function setSelectValue(id, val) {
    const el = document.getElementById(id);
    if (el && val !== undefined) el.value = val;
}

function setCheckbox(id, val) {
    const el = document.getElementById(id);
    if (el && val !== undefined) el.checked = val;
}

function getCollapsedSections() {
    const collapsed = [];
    document.querySelectorAll('.section-header.collapsed').forEach(h => {
        const label = h.querySelector('span')?.textContent;
        if (label) collapsed.push(label);
    });
    return collapsed;
}

function restoreCollapsedSections(collapsed) {
    document.querySelectorAll('.section-header').forEach(h => {
        const label = h.querySelector('span')?.textContent;
        if (label && collapsed.includes(label)) {
            h.classList.add('collapsed');
            const body = h.nextElementSibling;
            if (body) body.classList.add('collapsed');
        }
    });
}

/* ─── Init ─────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    loadState();
    checkHealth();
    loadBrands();
    loadJobs();
    setupDragDrop();
    setupColorSync();
    setupAutoSave();
    buildRuler();
    fetchVersion();
    checkForUpdates(false);
    setupVideoErrorHandler();
});

function setupAutoSave() {
    // Save state whenever form inputs change
    document.querySelectorAll('select, textarea, input[type="checkbox"]').forEach(el => {
        el.addEventListener('change', () => saveState());
    });
    document.querySelectorAll('textarea').forEach(el => {
        el.addEventListener('input', debounce(() => saveState(), 500));
    });
}

function debounce(fn, ms) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function setupVideoErrorHandler() {
    const video = document.getElementById('preview-video');
    if (video) {
        video.addEventListener('error', () => {
            video.style.display = 'none';
            document.getElementById('viewer-placeholder').style.display = 'flex';
        });
        video.addEventListener('ended', () => {
            document.getElementById('btn-play').textContent = '\u25B6';
        });
        video.addEventListener('pause', () => {
            document.getElementById('btn-play').textContent = '\u25B6';
        });
        video.addEventListener('play', () => {
            document.getElementById('btn-play').textContent = '\u23F8';
        });
    }
}

/* ─── Health Check ─────────────────────────────────────────────────────── */

async function checkHealth() {
    const dot = document.getElementById('connection-dot');
    const text = document.getElementById('connection-text');
    try {
        const res = await fetch(`${API}/api/health`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.healthy) {
            dot.className = 'status-dot ok';
            text.textContent = 'Ready';
        } else {
            dot.className = 'status-dot warn';
            const missing = Object.entries(data.checks).filter(([_, ok]) => !ok).map(([k]) => k);
            text.textContent = `Missing: ${missing.join(', ')}`;
        }
    } catch (e) {
        dot.className = 'status-dot error';
        text.textContent = 'Offline';
    }
}

/* ─── Global Drag & Drop ──────────────────────────────────────────────── */

function setupDragDrop() {
    let dragCounter = 0;
    const overlay = document.getElementById('drop-overlay');

    document.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (dragCounter === 1) overlay.style.display = 'flex';
    });
    document.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) { dragCounter = 0; overlay.style.display = 'none'; }
    });
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        overlay.style.display = 'none';
        if (e.dataTransfer.files.length > 0) {
            Array.from(e.dataTransfer.files).forEach(file => {
                if (file.type.startsWith('video/')) importFile(file);
            });
        }
    });
}

/* ─── Import ───────────────────────────────────────────────────────────── */

function handleImport(input) {
    Array.from(input.files).forEach(file => importFile(file));
    input.value = '';
}

async function importFile(file) {
    const type = !state.examplePath ? 'example' : 'raw';

    if (type === 'raw' && state.exampleFile && file.name === state.exampleFile.name && file.size === state.exampleFile.size) {
        showToast('Please select a different file for raw footage', 'warn');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    showToast(`Importing ${file.name}...`, 'info');

    try {
        const res = await fetch(`${API}/api/upload/${type}`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error(`Upload failed: HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        if (type === 'example') {
            state.exampleFile = file;
            state.examplePath = data.path;
        } else {
            state.rawFile = file;
            state.rawPath = data.path;
        }

        addMediaItem(file, type, data.size_mb);
        addClipToTimeline(file.name, type, data.duration || 0);
        updateProcessButton();
        updateTimelineInfo();
        showToast(`${type === 'example' ? 'Example' : 'Raw footage'} imported`, 'ok');
    } catch (err) {
        showToast(`Import failed: ${err.message}`, 'error');
    }
}

function addMediaItem(file, type, sizeMb) {
    const grid = document.getElementById('media-grid');
    const empty = document.getElementById('media-empty');
    if (empty) empty.remove();

    const item = document.createElement('div');
    item.className = 'media-item';
    item.onclick = () => selectMediaItem(item, file, type);
    item.innerHTML = `
        <div class="media-clip-${type}">&#9654;</div>
        <span class="media-badge ${type}">${type}</span>
        <span class="media-label">${file.name}</span>
    `;
    grid.appendChild(item);

    // Auto-select first imported item
    if (!document.querySelector('.media-item.selected')) {
        item.classList.add('selected');
        document.getElementById('viewer-title').textContent = file.name;
    }
}

function selectMediaItem(item, file, type) {
    document.querySelectorAll('.media-item').forEach(i => i.classList.remove('selected'));
    item.classList.add('selected');
    document.getElementById('viewer-title').textContent = file.name;
}

function addClipToTimeline(name, type, duration) {
    const hint = document.getElementById('video-track-hint');
    if (hint) hint.remove();

    const lane = document.getElementById('track-video-lane');
    const clip = document.createElement('div');
    clip.className = 'clip video';
    clip.style.width = Math.max(80, (duration || 10) * 8) + 'px';
    clip.innerHTML = `<span class="clip-label">${name}</span>`;
    clip.title = `${type}: ${name}`;
    lane.appendChild(clip);

    const audioLane = document.getElementById('track-audio-lane');
    const audioClip = document.createElement('div');
    audioClip.className = 'clip audio';
    audioClip.style.width = Math.max(80, (duration || 10) * 8) + 'px';
    audioClip.innerHTML = `<span class="clip-label">${name} audio</span>`;
    audioLane.appendChild(audioClip);
}

function updateProcessButton() {
    const btn = document.getElementById('btn-process');
    const ready = !!(state.examplePath && state.rawPath);
    btn.disabled = !ready;
    if (ready) {
        btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><polygon points="1,0 1,12 11,6"/></svg> Start AI Edit';
    }
}

function updateTimelineInfo() {
    const info = document.getElementById('timeline-info');
    const clips = document.getElementById('track-video-lane')?.querySelectorAll('.clip').length || 0;
    if (clips > 0) {
        info.textContent = `${clips} clip${clips !== 1 ? 's' : ''} imported`;
    }
}

/* ─── Toast Notifications ──────────────────────────────────────────────── */

function showToast(message, type) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type || 'info'}`;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('visible'));

    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/* ─── View Switching ───────────────────────────────────────────────────── */

function switchView(view, skipSave) {
    state.activeView = view;
    document.querySelectorAll('.view-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
    if (view === 'color') switchInspectorTab('effects', true);
    else if (view === 'export') switchInspectorTab('settings', true);
    if (!skipSave) saveState();
}

/* ─── Browser Tabs ─────────────────────────────────────────────────────── */

function switchBrowserTab(tab, skipSave) {
    state.activeBrowserTab = tab;
    const panel = document.getElementById('browser-panel');
    panel.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    ['media', 'brands', 'jobs'].forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        if (el) el.style.display = t === tab ? 'block' : 'none';
    });
    if (!skipSave) saveState();
}

/* ─── Inspector Tabs ───────────────────────────────────────────────────── */

function switchInspectorTab(tab, skipSave) {
    state.activeInspectorTab = tab;
    const panel = document.getElementById('inspector-panel');
    panel.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    ['settings', 'effects', 'api'].forEach(t => {
        const el = document.getElementById(`inspector-${t}`);
        if (el) el.style.display = t === tab ? 'block' : 'none';
    });
    if (!skipSave) saveState();
}

function toggleInspector() {
    state.inspectorVisible = !state.inspectorVisible;
    document.getElementById('inspector-panel').classList.toggle('hidden', !state.inspectorVisible);
    saveState();
}

/* ─── Section Toggle ───────────────────────────────────────────────────── */

function toggleSection(header) {
    header.classList.toggle('collapsed');
    const body = header.nextElementSibling;
    if (body) body.classList.toggle('collapsed');
    saveState();
}

/* ─── Format & Brand ───────────────────────────────────────────────────── */

function selectFormat(btn) {
    document.querySelectorAll('.format-card').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.outputFormat = btn.dataset.format;
    saveState();
}

function selectBrand(name) {
    state.brand = name;
    const select = document.getElementById('brand-select');
    if (select) select.value = name;
    saveState();
}

/* ─── Transport Controls ──────────────────────────────────────────────── */

function transportAction(action) {
    const video = document.getElementById('preview-video');
    if (!video || !video.src || video.src === window.location.href) return;
    switch (action) {
        case 'play':
            if (video.paused) video.play();
            else video.pause();
            break;
        case 'start': video.currentTime = 0; break;
        case 'end': if (video.duration) video.currentTime = video.duration; break;
        case 'back': video.currentTime = Math.max(0, video.currentTime - 1 / 30); break;
        case 'forward': if (video.duration) video.currentTime = Math.min(video.duration, video.currentTime + 1 / 30); break;
    }
}

/* ─── Timeline Ruler ──────────────────────────────────────────────────── */

function buildRuler(totalSeconds) {
    const ruler = document.getElementById('timeline-ruler');
    const total = totalSeconds || 60;
    let html = '';
    const step = total > 120 ? 10 : 5;
    for (let i = 0; i <= total; i += step) {
        const x = i * 8;
        html += `<span style="position:absolute;left:${x}px;top:4px;font-size:9px;color:#666;font-family:monospace">${formatTC(i)}</span>`;
    }
    ruler.innerHTML = html;
}

function formatTC(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
}

/* ─── Processing ───────────────────────────────────────────────────────── */

async function startProcessing() {
    if (!state.examplePath || !state.rawPath) return;

    const btn = document.getElementById('btn-process');
    btn.disabled = true;
    btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" class="spin"><circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-dasharray="20 12"/></svg> Processing...';

    document.getElementById('timeline-progress').style.display = 'flex';
    document.getElementById('results-bar').style.display = 'none';
    document.getElementById('viewer-placeholder').style.display = 'none';

    const instructions = document.getElementById('instructions').value;
    let premiumInstructions = instructions;
    const lut = document.getElementById('premium-lut').value;
    const captions = document.getElementById('premium-captions').value;
    const grain = document.getElementById('premium-grain').value;
    if (lut !== 'auto') premiumInstructions += `\nUse LUT: ${lut}`;
    if (captions !== 'auto') premiumInstructions += `\nCaption style: ${captions}`;
    if (grain !== 'auto') premiumInstructions += `\nFilm grain: ${grain}`;
    if (document.getElementById('premium-normalize').checked) premiumInstructions += '\nNormalize audio.';
    if (document.getElementById('premium-denoise').checked) premiumInstructions += '\nApply noise reduction.';
    if (document.getElementById('premium-voice').checked) premiumInstructions += '\nEnhance voice clarity.';
    if (document.getElementById('premium-vignette').checked) premiumInstructions += '\nAdd vignette effect.';

    try {
        const res = await fetch(`${API}/api/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                example_path: state.examplePath,
                raw_path: state.rawPath,
                instructions: premiumInstructions,
                output_format: state.outputFormat,
                brand: state.brand,
            }),
        });
        if (!res.ok) throw new Error(`Server error: HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        state.jobId = data.job_id;
        startProgressStream(data.job_id);
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
        resetProcessButton();
    }
}

function resetProcessButton() {
    const btn = document.getElementById('btn-process');
    btn.disabled = !(state.examplePath && state.rawPath);
    btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><polygon points="1,0 1,12 11,6"/></svg> Start AI Edit';
}

function startProgressStream(jobId) {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = new EventSource(`${API}/api/stream/${jobId}`);
    state.eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateProgress(data);
            if (data.status === 'complete') { state.eventSource.close(); onComplete(data); }
            else if (data.status === 'error') { state.eventSource.close(); onError(data); }
        } catch (e) {}
    };
    state.eventSource.onerror = () => { state.eventSource.close(); pollStatus(jobId); };
}

async function pollStatus(jobId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API}/api/status/${jobId}`);
            if (!res.ok) return;
            const data = await res.json();
            updateProgress(data);
            if (data.status === 'complete') { clearInterval(interval); onComplete(data); }
            else if (data.status === 'error') { clearInterval(interval); onError(data); }
        } catch (e) {}
    }, 1000);
}

function updateProgress(data) {
    const stageEl = document.getElementById('progress-stage');
    const pctEl = document.getElementById('progress-percent');
    const fillEl = document.getElementById('progress-fill');
    if (stageEl) stageEl.textContent = data.current_message || 'Processing...';
    if (pctEl) pctEl.textContent = `${data.overall_percent || 0}%`;
    if (fillEl) fillEl.style.width = `${data.overall_percent || 0}%`;

    const stageMap = { analyzing: 'analyze', transcribing: 'transcribe', planning: 'plan', editing: 'render' };
    const stages = ['analyze', 'transcribe', 'plan', 'render'];
    const currentStage = stageMap[data.status] || '';
    const currentIdx = stages.indexOf(currentStage);
    stages.forEach((s, i) => {
        const el = document.getElementById(`pstep-${s}`);
        if (!el) return;
        el.className = 'pipeline-step';
        if (i < currentIdx) el.classList.add('done');
        else if (i === currentIdx) el.classList.add('active');
    });
}

function onComplete(data) {
    document.getElementById('timeline-progress').style.display = 'none';
    document.getElementById('results-bar').style.display = 'flex';

    const output = data.output || {};
    document.getElementById('result-title').textContent = output.title || 'Edit Complete';
    document.getElementById('result-meta').textContent =
        `${output.duration || 0}s | ${output.size_mb || 0} MB | ${output.resolution || 'N/A'} | ${output.segments_used || 0} segments`;

    const premiumDiv = document.getElementById('result-premium');
    premiumDiv.innerHTML = (output.premium_features || []).map(f => `<span class="premium-tag">${f}</span>`).join('');

    const video = document.getElementById('preview-video');
    video.src = `${API}/api/download/${state.jobId}`;
    video.style.display = 'block';
    document.getElementById('viewer-placeholder').style.display = 'none';
    document.getElementById('viewer-title').textContent = output.title || 'Output';

    buildEditTimeline();
    loadJobs();
    resetProcessButton();
    showToast('Edit complete!', 'ok');
}

function onError(data) {
    document.getElementById('timeline-progress').style.display = 'none';
    showToast(`Editing failed: ${data.error || 'Unknown error'}`, 'error');
    resetProcessButton();
}

/* ─── Build Edit Timeline ─────────────────────────────────────────────── */

async function buildEditTimeline() {
    try {
        const res = await fetch(`${API}/api/edit-plan/${state.jobId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.edit_plan || !data.edit_plan.segments) return;

        const videoLane = document.getElementById('track-video-lane');
        const audioLane = document.getElementById('track-audio-lane');
        const captionsLane = document.getElementById('track-captions-lane');

        videoLane.innerHTML = '';
        audioLane.innerHTML = '';
        captionsLane.innerHTML = '';

        const segments = data.edit_plan.segments;
        const totalDur = segments.reduce((sum, s) => sum + (s.end - s.start), 0);
        const info = document.getElementById('timeline-info');
        info.textContent = `${segments.length} segments | ${totalDur.toFixed(1)}s`;

        segments.forEach((seg) => {
            const dur = seg.end - seg.start;
            const w = Math.max(30, dur * 8);

            const vc = document.createElement('div');
            vc.className = 'clip video';
            vc.style.width = w + 'px';
            vc.innerHTML = `<span class="clip-label">${dur.toFixed(1)}s</span>`;
            vc.title = `${seg.start.toFixed(1)}s - ${seg.end.toFixed(1)}s\n${seg.reason || ''}`;
            videoLane.appendChild(vc);

            const ac = document.createElement('div');
            ac.className = 'clip audio';
            ac.style.width = w + 'px';
            audioLane.appendChild(ac);
        });

        if (data.edit_plan.captions) {
            data.edit_plan.captions.forEach(cap => {
                const dur = (cap.end || cap.start + 2) - cap.start;
                const cc = document.createElement('div');
                cc.className = 'clip caption';
                cc.style.width = Math.max(40, dur * 8) + 'px';
                cc.innerHTML = `<span class="clip-label">${cap.text || ''}</span>`;
                captionsLane.appendChild(cc);
            });
        }

        buildRuler(Math.ceil(totalDur) + 5);
    } catch (e) {
        showToast('Could not load edit timeline', 'warn');
    }
}

/* ─── Download / Export ────────────────────────────────────────────────── */

function downloadVideo() {
    if (!state.jobId) { showToast('No video to download', 'warn'); return; }
    window.location.href = `${API}/api/download/${state.jobId}`;
}

async function exportForPlatform() {
    if (!state.jobId) { showToast('Process a video first', 'warn'); return; }
    const platform = document.getElementById('premium-platform').value;
    if (platform === 'auto') { showToast('Select a platform in the inspector first', 'warn'); return; }
    try {
        const res = await fetch(`${API}/api/premium/export/${state.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) showToast(`Export failed: ${data.error}`, 'error');
        else showToast(`Exported for ${data.preset_name}! ${data.size_mb} MB`, 'ok');
    } catch (e) { showToast(`Export error: ${e.message}`, 'error'); }
}

async function generateThumbnail() {
    if (!state.jobId) { showToast('Process a video first', 'warn'); return; }
    try {
        const res = await fetch(`${API}/api/premium/thumbnail/${state.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) showToast(`Thumbnail failed: ${data.error}`, 'error');
        else window.open(`${API}/api/premium/thumbnail/${state.jobId}/download`, '_blank');
    } catch (e) { showToast(`Thumbnail error: ${e.message}`, 'error'); }
}

/* ─── Edit Plan Modal ──────────────────────────────────────────────────── */

async function showEditPlan() {
    if (!state.jobId) { showToast('Process a video first', 'warn'); return; }
    try {
        const res = await fetch(`${API}/api/edit-plan/${state.jobId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        document.getElementById('edit-plan-content').textContent = JSON.stringify(data, null, 2);
        document.getElementById('edit-plan-modal').style.display = 'flex';
    } catch (e) { showToast('Could not load edit plan', 'error'); }
}

function closeModal() {
    document.getElementById('edit-plan-modal').style.display = 'none';
}

/* ─── Brand Management ─────────────────────────────────────────────────── */

function setupColorSync() {
    const p = document.getElementById('brand-primary');
    const ph = document.getElementById('brand-primary-hex');
    const a = document.getElementById('brand-accent');
    const ah = document.getElementById('brand-accent-hex');
    if (p && ph) {
        p.addEventListener('input', () => { ph.value = p.value; });
        ph.addEventListener('input', () => { if (/^#[0-9a-fA-F]{6}$/.test(ph.value)) p.value = ph.value; });
    }
    if (a && ah) {
        a.addEventListener('input', () => { ah.value = a.value; });
        ah.addEventListener('input', () => { if (/^#[0-9a-fA-F]{6}$/.test(ah.value)) a.value = ah.value; });
    }
}

async function saveBrand() {
    const name = document.getElementById('brand-name').value.trim();
    if (!name) { showToast('Enter a brand name', 'warn'); return; }
    const config = {
        primary_color: document.getElementById('brand-primary').value,
        accent_color: document.getElementById('brand-accent').value,
        emphasis_color: document.getElementById('brand-accent').value,
        caption_position: document.getElementById('brand-position').value,
        caption_size: document.getElementById('brand-size').value,
        caption_bg: document.getElementById('brand-bg').value,
        emphasis_style: document.getElementById('brand-emphasis').value,
    };
    try {
        const res = await fetch(`${API}/api/brands/${encodeURIComponent(name)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const select = document.getElementById('brand-select');
        let found = false;
        for (const opt of select.options) { if (opt.value === name) { found = true; break; } }
        if (!found) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
        select.value = name;
        state.brand = name;
        saveState();
        loadBrands();
        showToast(`Brand "${name}" saved`, 'ok');
    } catch (e) {
        showToast(`Failed to save brand: ${e.message}`, 'error');
    }
}

async function loadBrands() {
    try {
        const res = await fetch(`${API}/api/brands`);
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('brands-list');
        const select = document.getElementById('brand-select');

        if (data.brands && data.brands.length) {
            list.innerHTML = data.brands.map(b => {
                const active = b === state.brand ? ' brand-active' : '';
                return `<div class="brand-item${active}" onclick="selectBrandFromList('${b}')">${b}</div>`;
            }).join('');

            // Sync custom brands into the dropdown
            data.brands.forEach(b => {
                let found = false;
                for (const opt of select.options) { if (opt.value === b) { found = true; break; } }
                if (!found) {
                    const opt = document.createElement('option');
                    opt.value = b;
                    opt.textContent = b;
                    select.appendChild(opt);
                }
            });
            if (state.brand) select.value = state.brand;
        } else {
            list.innerHTML = '<div class="empty-state"><span>No custom brands</span></div>';
        }
    } catch (e) {}
}

function selectBrandFromList(name) {
    selectBrand(name);
    // Highlight active brand in list
    document.querySelectorAll('.brand-item').forEach(el => {
        el.classList.toggle('brand-active', el.textContent === name);
    });
}

/* ─── Jobs ─────────────────────────────────────────────────────────────── */

async function loadJobs() {
    try {
        const res = await fetch(`${API}/api/jobs`);
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('jobs-list');
        if (data.jobs && data.jobs.length) {
            list.innerHTML = data.jobs.slice(0, 20).map(j => {
                const statusClass = j.status === 'complete' ? 'job-done' : j.status === 'error' ? 'job-error' : 'job-active';
                return `<div class="job-item ${statusClass}" onclick="loadJob('${j.job_id}')">
                    <div>${j.job_id.slice(0, 8)}...</div>
                    <div class="job-status">${j.status}</div>
                </div>`;
            }).join('');
        } else {
            list.innerHTML = '<div class="empty-state"><span>No jobs yet</span></div>';
        }
    } catch (e) {}
}

async function loadJob(jobId) {
    try {
        const res = await fetch(`${API}/api/status/${jobId}`);
        if (!res.ok) return;
        const data = await res.json();
        state.jobId = jobId;

        if (data.status === 'complete') {
            const video = document.getElementById('preview-video');
            video.src = `${API}/api/download/${jobId}`;
            video.style.display = 'block';
            document.getElementById('viewer-placeholder').style.display = 'none';
            document.getElementById('results-bar').style.display = 'flex';
            document.getElementById('result-title').textContent = data.output?.title || 'Edit';
            document.getElementById('result-meta').textContent =
                `${data.output?.duration || 0}s | ${data.output?.size_mb || 0} MB`;
            buildEditTimeline();
            showToast('Job loaded', 'ok');
        } else if (data.status === 'error') {
            showToast(`Job failed: ${data.error || 'Unknown error'}`, 'error');
        } else {
            showToast(`Job is ${data.status}`, 'info');
        }
    } catch (e) {
        showToast('Could not load job', 'error');
    }
}

/* ─── Reset ────────────────────────────────────────────────────────────── */

function resetWorkflow() {
    state.exampleFile = null;
    state.examplePath = null;
    state.rawFile = null;
    state.rawPath = null;
    state.jobId = null;

    document.getElementById('media-grid').innerHTML = `
        <div class="empty-state" id="media-empty">
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none"><rect x="4" y="7" width="28" height="22" rx="3" stroke="currentColor" stroke-width="1.5"/><polygon points="14,13 14,23 24,18" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/></svg>
            <span>Import media to get started</span>
            <small>Drag files here or click Import</small>
        </div>`;

    document.getElementById('track-video-lane').innerHTML = '<div class="track-empty" id="video-track-hint">Drop example &amp; raw footage to begin</div>';
    document.getElementById('track-audio-lane').innerHTML = '';
    document.getElementById('track-captions-lane').innerHTML = '';

    const video = document.getElementById('preview-video');
    video.style.display = 'none';
    video.removeAttribute('src');
    video.load();
    document.getElementById('viewer-placeholder').style.display = 'flex';
    document.getElementById('viewer-title').textContent = 'Viewer';
    document.getElementById('viewer-timecode').textContent = '00:00:00:00';
    document.getElementById('btn-play').textContent = '\u25B6';
    document.getElementById('results-bar').style.display = 'none';
    document.getElementById('timeline-progress').style.display = 'none';
    document.getElementById('timeline-info').textContent = '';

    resetProcessButton();
    buildRuler();
    showToast('Project reset', 'info');
}

/* ─── Version & Updates ────────────────────────────────────────────────── */

async function fetchVersion() {
    try {
        const res = await fetch(`${API}/api/info`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.version) {
            document.getElementById('version-label').textContent = `v${data.version}`;
            document.getElementById('version-label').title = data.full || '';
        }
    } catch (e) {}
}

async function checkForUpdates(showModal) {
    const force = showModal ? '1' : '0';
    try {
        const res = await fetch(`${API}/api/update/check?force=${force}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        document.getElementById('update-local').textContent = data.local || '--';
        document.getElementById('update-remote').textContent = data.remote || '--';

        const badge = document.getElementById('update-badge');
        const status = document.getElementById('update-status');
        const applyBtn = document.getElementById('btn-apply-update');

        if (data.updateAvailable) {
            badge.style.display = 'inline';
            status.textContent = `Update available: v${data.remote}`;
            status.className = 'update-status has-update';
            applyBtn.style.display = 'inline-flex';
        } else if (data.remote) {
            badge.style.display = 'none';
            status.textContent = 'You are up to date';
            status.className = 'update-status up-to-date';
            applyBtn.style.display = 'none';
        } else if (data.error) {
            status.textContent = `Could not check: ${data.error}`;
            status.className = 'update-status error';
            applyBtn.style.display = 'none';
        }

        if (showModal) {
            document.getElementById('update-modal').style.display = 'flex';
        }
    } catch (e) {
        if (showModal) {
            document.getElementById('update-status').textContent = 'Failed to check for updates';
            document.getElementById('update-status').className = 'update-status error';
            document.getElementById('update-modal').style.display = 'flex';
        }
    }
}

async function applyUpdate() {
    const status = document.getElementById('update-status');
    const applyBtn = document.getElementById('btn-apply-update');

    status.textContent = 'Updating... do not close the browser';
    status.className = 'update-status updating';
    applyBtn.disabled = true;
    applyBtn.textContent = 'Updating...';

    try {
        const res = await fetch(`${API}/api/update/apply`, { method: 'POST' });
        const data = await res.json();

        if (data.ok) {
            status.textContent = `Updated to v${data.version}! Restarting server...`;
            status.className = 'update-status up-to-date';
            document.getElementById('update-badge').style.display = 'none';
            setTimeout(() => {
                status.textContent = 'Reloading page...';
                setTimeout(() => window.location.reload(), 3000);
            }, 2000);
        } else {
            status.textContent = `Update failed: ${data.error}`;
            status.className = 'update-status error';
            applyBtn.disabled = false;
            applyBtn.textContent = 'Update Now';
        }
    } catch (e) {
        status.textContent = 'Server restarting... reloading in a few seconds';
        status.className = 'update-status updating';
        setTimeout(() => window.location.reload(), 5000);
    }
}

function closeUpdateModal() {
    document.getElementById('update-modal').style.display = 'none';
}

/* ─── Bug Tracker ──────────────────────────────────────────────────────── */

let autoErrors = [];

function setupErrorCapture() {
    window.addEventListener('error', (e) => {
        captureError('js-error', e.message, e.filename ? `${e.filename}:${e.lineno}:${e.colno}\n${e.error?.stack || ''}` : '');
    });
    window.addEventListener('unhandledrejection', (e) => {
        captureError('promise-rejection', String(e.reason), e.reason?.stack || '');
    });

    const origFetch = window.fetch;
    window.fetch = async function (...args) {
        try {
            const res = await origFetch.apply(this, args);
            if (!res.ok && String(args[0]).startsWith(API + '/api/')) {
                captureError('api-error', `${res.status} ${res.statusText}: ${args[0]}`, '');
            }
            return res;
        } catch (e) {
            if (String(args[0]).startsWith(API + '/api/')) {
                captureError('network-error', `Failed: ${args[0]}`, e.stack || '');
            }
            throw e;
        }
    };
}

function captureError(type, message, stack) {
    if (autoErrors.length >= 50) autoErrors.shift();
    autoErrors.push({
        type: `auto-${type}`,
        title: message.slice(0, 120),
        stack: stack?.slice(0, 1000) || '',
        timestamp: new Date().toISOString(),
    });
    updateBugCount();
}

function openBugReporter() {
    document.getElementById('bug-modal').style.display = 'flex';
    loadBugList();
    renderAutoErrors();
}

function closeBugModal() {
    document.getElementById('bug-modal').style.display = 'none';
}

async function submitBugReport() {
    const title = document.getElementById('bug-title').value.trim();
    const desc = document.getElementById('bug-description').value.trim();
    const type = document.getElementById('bug-type').value;

    if (!title) { showToast('Enter a title for the bug', 'warn'); return; }

    try {
        const res = await fetch(`${API}/api/bugs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title, description: desc, type,
                context: { url: window.location.href, userAgent: navigator.userAgent },
            }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.ok) {
            document.getElementById('bug-title').value = '';
            document.getElementById('bug-description').value = '';
            showToast('Bug report saved', 'ok');
            loadBugList();
        }
    } catch (e) { showToast(`Failed to save: ${e.message}`, 'error'); }
}

async function submitAutoError(idx) {
    const err = autoErrors[idx];
    if (!err) return;
    try {
        await fetch(`${API}/api/bugs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: err.title, type: err.type, stack: err.stack,
                context: { capturedAt: err.timestamp, userAgent: navigator.userAgent },
            }),
        });
        autoErrors.splice(idx, 1);
        renderAutoErrors();
        loadBugList();
        showToast('Error saved to tracker', 'ok');
    } catch (e) { showToast('Failed to save error', 'error'); }
}

async function loadBugList() {
    try {
        const res = await fetch(`${API}/api/bugs`);
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('bug-list');

        if (data.bugs && data.bugs.length) {
            list.innerHTML = data.bugs.map(b => {
                const typeClass = `type-${b.type || 'bug'}`;
                const statusClass = b.status || 'pending';
                const submitted = b.status === 'submitted';
                return `<div class="bug-entry ${typeClass} ${submitted ? 'submitted' : ''}">
                    <div class="bug-entry-info">
                        <div class="bug-entry-title">${escapeHtml(b.title)}</div>
                        <div class="bug-entry-meta">${b.type} | ${b.created_at || ''}</div>
                    </div>
                    <span class="bug-entry-status ${statusClass}">${b.status}</span>
                    ${b.github_url ? `<a href="${b.github_url}" target="_blank" class="bug-entry-delete" title="View on GitHub">&nearr;</a>` : ''}
                    <button class="bug-entry-delete" onclick="deleteBug('${b.id}')" title="Delete">&times;</button>
                </div>`;
            }).join('');
        } else {
            list.innerHTML = '<div class="empty-state"><span>No tracked issues</span></div>';
        }

        updateBugCount();
    } catch (e) {}
}

function renderAutoErrors() {
    const list = document.getElementById('bug-auto-list');
    const count = document.getElementById('bug-auto-count');
    count.textContent = autoErrors.length;

    if (autoErrors.length) {
        list.innerHTML = autoErrors.map((e, i) => `
            <div class="bug-entry type-${e.type}">
                <div class="bug-entry-info">
                    <div class="bug-entry-title">${escapeHtml(e.title)}</div>
                    <div class="bug-entry-meta">${e.type} | ${new Date(e.timestamp).toLocaleTimeString()}</div>
                </div>
                <button class="fcp-btn small" onclick="submitAutoError(${i})">Track</button>
            </div>
        `).join('');
    } else {
        list.innerHTML = '<div class="empty-state"><span>No errors captured</span></div>';
    }
}

async function deleteBug(id) {
    try {
        await fetch(`${API}/api/bugs/${id}`, { method: 'DELETE' });
        loadBugList();
    } catch (e) {}
}

async function submitAllBugs() {
    showToast('Submitting bugs to GitHub...', 'info');
    try {
        const res = await fetch(`${API}/api/bugs/submit`, { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(`Submitted ${data.submitted} of ${data.total} bugs to GitHub`, 'ok');
            loadBugList();
        }
    } catch (e) { showToast(`Submit failed: ${e.message}`, 'error'); }
}

function updateBugCount() {
    const badge = document.getElementById('bug-count');
    fetch(`${API}/api/bugs`).then(r => r.json()).then(data => {
        const pending = (data.bugs || []).filter(b => b.status === 'pending').length;
        const total = pending + autoErrors.length;
        if (total > 0) {
            badge.textContent = total;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }).catch(() => {});
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

setupErrorCapture();

/* ─── Timecode Update ──────────────────────────────────────────────────── */

setInterval(() => {
    const video = document.getElementById('preview-video');
    if (video && video.src && video.src !== window.location.href) {
        const t = video.currentTime || 0;
        const h = Math.floor(t / 3600);
        const m = Math.floor((t % 3600) / 60);
        const s = Math.floor(t % 60);
        const f = Math.floor((t % 1) * 30);
        document.getElementById('viewer-timecode').textContent =
            `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}:${String(f).padStart(2, '0')}`;
    }
}, 33);
