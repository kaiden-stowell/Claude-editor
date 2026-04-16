const API = '';
let state = {
    exampleFile: null,
    examplePath: null,
    rawFile: null,
    rawPath: null,
    outputFormat: 'reel',
    brand: 'default',
    jobId: null,
    eventSource: null,
};

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadBrands();
    loadJobs();
    setupDragDrop();
    setupColorSync();
    buildRuler();
    fetchVersion();
    checkForUpdates(false);
});

/* ─── Health Check ─────────────────────────────────────────────────────── */

async function checkHealth() {
    const dot = document.getElementById('connection-dot');
    const text = document.getElementById('connection-text');
    try {
        const res = await fetch(`${API}/api/health`);
        const data = await res.json();
        if (data.healthy) {
            dot.className = 'status-dot ok';
            text.textContent = 'Ready';
        } else {
            dot.className = 'status-dot warn';
            const missing = Object.entries(data.checks).filter(([_,ok]) => !ok).map(([k]) => k);
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
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API}/api/upload/${type}`, { method: 'POST', body: formData });
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
    } catch (err) {
        console.error('Import failed:', err);
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
    document.getElementById('btn-process').disabled = !(state.examplePath && state.rawPath);
}

/* ─── View Switching ───────────────────────────────────────────────────── */

function switchView(view) {
    document.querySelectorAll('.view-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
    if (view === 'color') switchInspectorTab('effects');
    else if (view === 'export') switchInspectorTab('settings');
    else switchInspectorTab('settings');
}

/* ─── Browser Tabs ─────────────────────────────────────────────────────── */

function switchBrowserTab(tab) {
    const panel = document.getElementById('browser-panel');
    panel.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    ['media', 'brands', 'jobs'].forEach(t => {
        document.getElementById(`tab-${t}`).style.display = t === tab ? 'block' : 'none';
    });
}

/* ─── Inspector Tabs ───────────────────────────────────────────────────── */

function switchInspectorTab(tab) {
    const panel = document.getElementById('inspector-panel');
    panel.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    ['settings', 'effects', 'api'].forEach(t => {
        document.getElementById(`inspector-${t}`).style.display = t === tab ? 'block' : 'none';
    });
}

function toggleInspector() {
    document.getElementById('inspector-panel').classList.toggle('hidden');
}

/* ─── Section Toggle ───────────────────────────────────────────────────── */

function toggleSection(header) {
    header.classList.toggle('collapsed');
    const body = header.nextElementSibling;
    if (body) body.classList.toggle('collapsed');
}

/* ─── Format & Brand ───────────────────────────────────────────────────── */

function selectFormat(btn) {
    document.querySelectorAll('.format-card').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.outputFormat = btn.dataset.format;
}

function selectBrand(name) {
    state.brand = name;
}

/* ─── Transport Controls ──────────────────────────────────────────────── */

function transportAction(action) {
    const video = document.getElementById('preview-video');
    if (!video.src) return;
    switch (action) {
        case 'play':
            if (video.paused) { video.play(); document.getElementById('btn-play').textContent = '\u23F8'; }
            else { video.pause(); document.getElementById('btn-play').textContent = '\u25B6'; }
            break;
        case 'start': video.currentTime = 0; break;
        case 'end': video.currentTime = video.duration; break;
        case 'back': video.currentTime = Math.max(0, video.currentTime - 1/30); break;
        case 'forward': video.currentTime = Math.min(video.duration, video.currentTime + 1/30); break;
    }
}

/* ─── Timeline Ruler ──────────────────────────────────────────────────── */

function buildRuler() {
    const ruler = document.getElementById('timeline-ruler');
    let html = '';
    for (let i = 0; i <= 60; i += 5) {
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
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        state.jobId = data.job_id;
        startProgressStream(data.job_id);
    } catch (err) {
        alert(`Error: ${err.message}`);
        btn.disabled = false;
    }
}

function startProgressStream(jobId) {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = new EventSource(`${API}/api/stream/${jobId}`);
    state.eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);
        if (data.status === 'complete') { state.eventSource.close(); onComplete(data); }
        else if (data.status === 'error') { state.eventSource.close(); onError(data); }
    };
    state.eventSource.onerror = () => { state.eventSource.close(); pollStatus(jobId); };
}

async function pollStatus(jobId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API}/api/status/${jobId}`);
            const data = await res.json();
            updateProgress(data);
            if (data.status === 'complete') { clearInterval(interval); onComplete(data); }
            else if (data.status === 'error') { clearInterval(interval); onError(data); }
        } catch (e) {}
    }, 1000);
}

function updateProgress(data) {
    document.getElementById('progress-stage').textContent = data.current_message || 'Processing...';
    document.getElementById('progress-percent').textContent = `${data.overall_percent || 0}%`;
    document.getElementById('progress-fill').style.width = `${data.overall_percent || 0}%`;

    const stageMap = { analyzing: 'analyze', transcribing: 'transcribe', planning: 'plan', editing: 'render' };
    const stages = ['analyze', 'transcribe', 'plan', 'render'];
    const currentStage = stageMap[data.status] || '';
    const currentIdx = stages.indexOf(currentStage);
    stages.forEach((s, i) => {
        const el = document.getElementById(`pstep-${s}`);
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
    document.getElementById('viewer-title').textContent = output.title || 'Output';

    buildEditTimeline();
    loadJobs();

    document.getElementById('btn-process').disabled = false;
}

function onError(data) {
    document.getElementById('timeline-progress').style.display = 'none';
    alert(`Editing failed: ${data.error || 'Unknown error'}`);
    document.getElementById('btn-process').disabled = false;
}

/* ─── Build Edit Timeline ─────────────────────────────────────────────── */

async function buildEditTimeline() {
    try {
        const res = await fetch(`${API}/api/edit-plan/${state.jobId}`);
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

        segments.forEach((seg, i) => {
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

        buildRuler();
    } catch (e) {}
}

/* ─── Download / Export ────────────────────────────────────────────────── */

function downloadVideo() {
    if (state.jobId) window.location.href = `${API}/api/download/${state.jobId}`;
}

async function exportForPlatform() {
    if (!state.jobId) return;
    const platform = document.getElementById('premium-platform').value;
    if (platform === 'auto') { alert('Select a platform first.'); return; }
    try {
        const res = await fetch(`${API}/api/premium/export/${state.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform }),
        });
        const data = await res.json();
        if (data.error) alert(`Export failed: ${data.error}`);
        else alert(`Exported for ${data.preset_name}! ${data.size_mb} MB`);
    } catch (e) { alert(`Export error: ${e.message}`); }
}

async function generateThumbnail() {
    if (!state.jobId) return;
    try {
        const res = await fetch(`${API}/api/premium/thumbnail/${state.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();
        if (data.error) alert(`Thumbnail failed: ${data.error}`);
        else window.open(`${API}/api/premium/thumbnail/${state.jobId}/download`, '_blank');
    } catch (e) { alert(`Thumbnail error: ${e.message}`); }
}

/* ─── Edit Plan Modal ──────────────────────────────────────────────────── */

async function showEditPlan() {
    if (!state.jobId) return;
    try {
        const res = await fetch(`${API}/api/edit-plan/${state.jobId}`);
        const data = await res.json();
        document.getElementById('edit-plan-content').textContent = JSON.stringify(data, null, 2);
        document.getElementById('edit-plan-modal').style.display = 'flex';
    } catch (e) { alert('Could not load edit plan'); }
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
        ph.addEventListener('input', () => { p.value = ph.value; });
    }
    if (a && ah) {
        a.addEventListener('input', () => { ah.value = a.value; });
        ah.addEventListener('input', () => { a.value = ah.value; });
    }
}

async function saveBrand() {
    const name = document.getElementById('brand-name').value.trim();
    if (!name) { alert('Enter a brand name'); return; }
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
        await fetch(`${API}/api/brands/${name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        const select = document.getElementById('brand-select');
        let found = false;
        for (const opt of select.options) { if (opt.value === name) { found = true; break; } }
        if (!found) { const opt = document.createElement('option'); opt.value = name; opt.textContent = name; select.appendChild(opt); }
        select.value = name;
        state.brand = name;
        loadBrands();
    } catch (e) { alert(`Failed: ${e.message}`); }
}

async function loadBrands() {
    try {
        const res = await fetch(`${API}/api/brands`);
        const data = await res.json();
        const list = document.getElementById('brands-list');
        if (data.brands && data.brands.length) {
            list.innerHTML = data.brands.map(b =>
                `<div class="brand-item" onclick="selectBrand('${b}')">${b}</div>`
            ).join('');
        } else {
            list.innerHTML = '<div class="empty-state"><span>No custom brands</span></div>';
        }
    } catch (e) {}
}

/* ─── Jobs ─────────────────────────────────────────────────────────────── */

async function loadJobs() {
    try {
        const res = await fetch(`${API}/api/jobs`);
        const data = await res.json();
        const list = document.getElementById('jobs-list');
        if (data.jobs && data.jobs.length) {
            list.innerHTML = data.jobs.slice(0, 20).map(j =>
                `<div class="job-item" onclick="loadJob('${j.job_id}')">
                    <div>${j.job_id.slice(0,8)}...</div>
                    <div class="job-status">${j.status}</div>
                </div>`
            ).join('');
        } else {
            list.innerHTML = '<div class="empty-state"><span>No jobs yet</span></div>';
        }
    } catch (e) {}
}

async function loadJob(jobId) {
    try {
        const res = await fetch(`${API}/api/status/${jobId}`);
        const data = await res.json();
        if (data.status === 'complete') {
            state.jobId = jobId;
            const video = document.getElementById('preview-video');
            video.src = `${API}/api/download/${jobId}`;
            video.style.display = 'block';
            document.getElementById('viewer-placeholder').style.display = 'none';
            document.getElementById('results-bar').style.display = 'flex';
            document.getElementById('result-title').textContent = data.output?.title || 'Edit';
        }
    } catch (e) {}
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

    document.getElementById('preview-video').style.display = 'none';
    document.getElementById('preview-video').src = '';
    document.getElementById('viewer-placeholder').style.display = 'flex';
    document.getElementById('viewer-title').textContent = 'Viewer';
    document.getElementById('results-bar').style.display = 'none';
    document.getElementById('timeline-progress').style.display = 'none';
    document.getElementById('instructions').value = '';

    updateProcessButton();
}

/* ─── Version & Updates ────────────────────────────────────────────────── */

async function fetchVersion() {
    try {
        const res = await fetch(`${API}/api/info`);
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

/* ─── Timecode Update ──────────────────────────────────────────────────── */

setInterval(() => {
    const video = document.getElementById('preview-video');
    if (video && video.src && !video.paused) {
        const t = video.currentTime;
        const h = Math.floor(t / 3600);
        const m = Math.floor((t % 3600) / 60);
        const s = Math.floor(t % 60);
        const f = Math.floor((t % 1) * 30);
        document.getElementById('viewer-timecode').textContent =
            `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}:${String(f).padStart(2,'0')}`;
    }
}, 33);
