/* ─── Claude Editor — Frontend Logic ──────────────────────────────────── */

const API = '';  // Same origin
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

/* ─── Init ─────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();

    // Make dropzones clickable
    document.querySelectorAll('.dropzone').forEach(dz => {
        dz.addEventListener('click', () => {
            const input = dz.querySelector('input[type="file"]');
            if (input) input.click();
        });
    });

    // Sync color pickers with hex inputs
    const primary = document.getElementById('brand-primary');
    const primaryHex = document.getElementById('brand-primary-hex');
    const accent = document.getElementById('brand-accent');
    const accentHex = document.getElementById('brand-accent-hex');

    if (primary && primaryHex) {
        primary.addEventListener('input', () => { primaryHex.value = primary.value; });
        primaryHex.addEventListener('input', () => { primary.value = primaryHex.value; });
    }
    if (accent && accentHex) {
        accent.addEventListener('input', () => { accentHex.value = accent.value; });
        accentHex.addEventListener('input', () => { accent.value = accentHex.value; });
    }
});

/* ─── Health Check ─────────────────────────────────────────────────────── */

async function checkHealth() {
    const dot = document.getElementById('connection-dot');
    const text = document.getElementById('connection-text');

    try {
        const res = await fetch(`${API}/api/health`);
        const data = await res.json();

        if (data.healthy) {
            dot.className = 'dot dot-ok';
            text.textContent = 'All systems ready';
        } else {
            dot.className = 'dot dot-warn';
            const missing = Object.entries(data.checks)
                .filter(([_, ok]) => !ok)
                .map(([k, _]) => k);
            text.textContent = `Missing: ${missing.join(', ')}`;
        }
    } catch (e) {
        dot.className = 'dot dot-error';
        text.textContent = 'Server unreachable';
    }
}

/* ─── File Upload ──────────────────────────────────────────────────────── */

function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove('dragover');
}

function handleDrop(e, type) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0], type);
    }
}

function handleFileSelect(input, type) {
    if (input.files.length > 0) {
        uploadFile(input.files[0], type);
    }
}

async function uploadFile(file, type) {
    const dropzone = document.getElementById(`dropzone-${type}`);
    const info = document.getElementById(`${type}-info`);
    const stepStatus = document.getElementById(`step${type === 'example' ? '1' : '2'}-status`);
    const step = document.getElementById(`step-${type === 'example' ? '1' : '2'}`);

    dropzone.classList.add('uploading');
    dropzone.querySelector('.dropzone-text').textContent = 'Uploading...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API}/api/upload/${type}`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // Store result
        if (type === 'example') {
            state.exampleFile = file;
            state.examplePath = data.path;
        } else {
            state.rawFile = file;
            state.rawPath = data.path;
        }

        // Update UI
        dropzone.querySelector('.dropzone-text').textContent = file.name;
        dropzone.querySelector('.dropzone-sub').textContent = `${data.size_mb} MB`;
        dropzone.querySelector('.dropzone-icon').textContent = '\u2713';

        info.style.display = 'flex';
        info.innerHTML = `<span class="file-name">${file.name}</span><span class="file-size">${data.size_mb} MB</span>`;

        stepStatus.textContent = '\u2713';
        step.classList.add('done');

        updateProcessButton();

    } catch (err) {
        dropzone.querySelector('.dropzone-text').textContent = `Error: ${err.message}`;
        dropzone.querySelector('.dropzone-icon').textContent = '!';
        setTimeout(() => {
            dropzone.querySelector('.dropzone-text').textContent = `Drop ${type} video here`;
            dropzone.querySelector('.dropzone-icon').textContent = type === 'example' ? '\u25B6' : '\uD83C\uDFA5';
            dropzone.querySelector('.dropzone-sub').textContent = 'or click to browse';
        }, 3000);
    }

    dropzone.classList.remove('uploading');
}

function updateProcessButton() {
    const btn = document.getElementById('btn-process');
    btn.disabled = !(state.examplePath && state.rawPath);
}

/* ─── Format & Brand ───────────────────────────────────────────────────── */

function selectFormat(btn) {
    document.querySelectorAll('.format-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.outputFormat = btn.dataset.format;
}

function selectBrand(name) {
    state.brand = name;
}

/* ─── Steps Toggle ─────────────────────────────────────────────────────── */

function toggleStep(num) {
    const body = document.getElementById(`step${num}-body`);
    body.classList.toggle('collapsed');
}

/* ─── Panels ───────────────────────────────────────────────────────────── */

function showPanel(type) {
    const panelRight = document.getElementById('panel-right');
    const brandPanel = document.getElementById('brand-panel');
    const agentPanel = document.getElementById('agent-panel');

    panelRight.style.display = 'block';
    brandPanel.style.display = type === 'brand' ? 'block' : 'none';
    agentPanel.style.display = type === 'agent' ? 'block' : 'none';
}

function hidePanel() {
    document.getElementById('panel-right').style.display = 'none';
}

/* ─── Processing ───────────────────────────────────────────────────────── */

async function startProcessing() {
    if (!state.examplePath || !state.rawPath) return;

    const btn = document.getElementById('btn-process');
    btn.disabled = true;
    btn.textContent = 'Processing...';

    // Show progress, hide results
    document.getElementById('progress-container').style.display = 'block';
    document.getElementById('results-container').style.display = 'none';
    document.getElementById('timeline-container').style.display = 'none';
    document.getElementById('monitor-placeholder').style.display = 'none';

    const instructions = document.getElementById('instructions').value;

    // Gather premium settings
    const premiumLut = document.getElementById('premium-lut').value;
    const premiumCaptions = document.getElementById('premium-captions').value;
    const premiumGrain = document.getElementById('premium-grain').value;
    const premiumNormalize = document.getElementById('premium-normalize').checked;
    const premiumDenoise = document.getElementById('premium-denoise').checked;
    const premiumVoice = document.getElementById('premium-voice').checked;
    const premiumVignette = document.getElementById('premium-vignette').checked;

    // Build premium instructions for AI
    let premiumInstructions = instructions;
    if (premiumLut !== 'auto') premiumInstructions += `\nUse LUT: ${premiumLut}`;
    if (premiumCaptions !== 'auto') premiumInstructions += `\nCaption style: ${premiumCaptions}`;
    if (premiumGrain !== 'auto') premiumInstructions += `\nFilm grain: ${premiumGrain}`;
    if (premiumNormalize) premiumInstructions += '\nNormalize audio.';
    if (premiumDenoise) premiumInstructions += '\nApply noise reduction.';
    if (premiumVoice) premiumInstructions += '\nEnhance voice clarity.';
    if (premiumVignette) premiumInstructions += '\nAdd vignette effect.';

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

        if (data.error) {
            throw new Error(data.error);
        }

        state.jobId = data.job_id;
        startProgressStream(data.job_id);

    } catch (err) {
        alert(`Error: ${err.message}`);
        btn.disabled = false;
        btn.textContent = 'Start AI Edit';
    }
}

function startProgressStream(jobId) {
    if (state.eventSource) {
        state.eventSource.close();
    }

    state.eventSource = new EventSource(`${API}/api/stream/${jobId}`);

    state.eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);

        if (data.status === 'complete') {
            state.eventSource.close();
            onComplete(data);
        } else if (data.status === 'error') {
            state.eventSource.close();
            onError(data);
        }
    };

    state.eventSource.onerror = () => {
        // Fallback to polling
        state.eventSource.close();
        pollStatus(jobId);
    };
}

async function pollStatus(jobId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API}/api/status/${jobId}`);
            const data = await res.json();
            updateProgress(data);

            if (data.status === 'complete') {
                clearInterval(interval);
                onComplete(data);
            } else if (data.status === 'error') {
                clearInterval(interval);
                onError(data);
            }
        } catch (e) {
            // Keep polling
        }
    }, 1000);
}

function updateProgress(data) {
    document.getElementById('progress-stage').textContent = data.current_message || 'Processing...';
    document.getElementById('progress-percent').textContent = `${data.overall_percent || 0}%`;
    document.getElementById('progress-fill').style.width = `${data.overall_percent || 0}%`;

    // Update step indicators
    const stageMap = {
        'analyzing': 'analyze',
        'transcribing': 'transcribe',
        'planning': 'plan',
        'editing': 'render',
    };

    const stages = ['analyze', 'transcribe', 'plan', 'render'];
    const currentStage = stageMap[data.status] || '';
    const currentIdx = stages.indexOf(currentStage);

    stages.forEach((s, i) => {
        const el = document.getElementById(`pstep-${s}`);
        el.className = 'p-step';
        if (i < currentIdx) el.classList.add('done');
        else if (i === currentIdx) el.classList.add('active');
    });
}

function onComplete(data) {
    document.getElementById('progress-container').style.display = 'none';

    // Show results
    const container = document.getElementById('results-container');
    container.style.display = 'block';

    const output = data.output || {};
    document.getElementById('result-title').textContent = output.title || 'Your Edited Video';
    document.getElementById('result-meta').innerHTML =
        `Duration: ${output.duration || 0}s &bull; ` +
        `Size: ${output.size_mb || 0} MB &bull; ` +
        `Resolution: ${output.resolution || 'N/A'} &bull; ` +
        `Segments: ${output.segments_used || 0} &bull; ` +
        `Captions: ${output.captions_added || 0}`;

    // Show premium features applied
    const premiumDiv = document.getElementById('result-premium');
    const features = output.premium_features || [];
    premiumDiv.innerHTML = features.map(f =>
        `<span class="premium-tag">${f}</span>`
    ).join('');

    // Show video preview
    const video = document.getElementById('preview-video');
    video.src = `${API}/api/download/${state.jobId}`;
    video.style.display = 'block';

    // Build timeline
    buildTimeline();

    // Reset button
    const btn = document.getElementById('btn-process');
    btn.disabled = false;
    btn.textContent = 'Start AI Edit';

    // Mark step 3 done
    document.getElementById('step3-status').textContent = '\u2713';
    document.getElementById('step-3').classList.add('done');
}

function onError(data) {
    document.getElementById('progress-container').style.display = 'none';
    alert(`Editing failed: ${data.error || 'Unknown error'}`);

    const btn = document.getElementById('btn-process');
    btn.disabled = false;
    btn.textContent = 'Start AI Edit';
}

/* ─── Timeline ─────────────────────────────────────────────────────────── */

async function buildTimeline() {
    try {
        const res = await fetch(`${API}/api/edit-plan/${state.jobId}`);
        const data = await res.json();

        if (!data.edit_plan || !data.edit_plan.segments) return;

        const container = document.getElementById('timeline-container');
        const timeline = document.getElementById('timeline');
        const info = document.getElementById('timeline-info');

        container.style.display = 'block';

        const segments = data.edit_plan.segments;
        const totalDur = segments.reduce((sum, s) => sum + (s.end - s.start), 0);

        info.textContent = `${segments.length} segments | ${totalDur.toFixed(1)}s total`;

        timeline.innerHTML = '';
        segments.forEach((seg, i) => {
            const dur = seg.end - seg.start;
            const pct = (dur / totalDur) * 100;
            const el = document.createElement('div');
            el.className = 'timeline-segment';
            el.style.width = `${Math.max(pct, 1)}%`;
            el.title = `${seg.start.toFixed(1)}s - ${seg.end.toFixed(1)}s\n${seg.reason || ''}`;
            el.textContent = dur >= 2 ? `${dur.toFixed(1)}s` : '';
            timeline.appendChild(el);
        });

    } catch (e) {
        // Timeline is optional
    }
}

/* ─── Download ─────────────────────────────────────────────────────────── */

function downloadVideo() {
    if (!state.jobId) return;
    window.location.href = `${API}/api/download/${state.jobId}`;
}

/* ─── Edit Plan Modal ──────────────────────────────────────────────────── */

async function showEditPlan() {
    if (!state.jobId) return;

    try {
        const res = await fetch(`${API}/api/edit-plan/${state.jobId}`);
        const data = await res.json();

        document.getElementById('edit-plan-content').textContent =
            JSON.stringify(data, null, 2);
        document.getElementById('edit-plan-modal').style.display = 'flex';
    } catch (e) {
        alert('Could not load edit plan');
    }
}

function closeModal() {
    document.getElementById('edit-plan-modal').style.display = 'none';
}

/* ─── Brand Management ─────────────────────────────────────────────────── */

async function saveBrand() {
    const name = document.getElementById('brand-name').value.trim();
    if (!name) {
        alert('Enter a brand name');
        return;
    }

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
        const res = await fetch(`${API}/api/brands/${name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        const data = await res.json();

        // Add to brand select
        const select = document.getElementById('brand-select');
        let found = false;
        for (const opt of select.options) {
            if (opt.value === name) { found = true; break; }
        }
        if (!found) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
        select.value = name;
        state.brand = name;

        alert(`Brand "${name}" saved!`);
    } catch (e) {
        alert(`Failed to save brand: ${e.message}`);
    }
}

/* ─── Export for Platform ───────────────────────────────────────────────── */

async function exportForPlatform() {
    if (!state.jobId) return;

    const platform = document.getElementById('premium-platform').value;
    if (platform === 'auto') {
        alert('Select a specific platform from the Premium Features panel first.');
        return;
    }

    try {
        const res = await fetch(`${API}/api/premium/export/${state.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform }),
        });
        const data = await res.json();

        if (data.error) {
            alert(`Export failed: ${data.error}`);
        } else {
            alert(`Exported for ${data.preset_name}!\nSize: ${data.size_mb} MB\nReady to download.`);
        }
    } catch (e) {
        alert(`Export error: ${e.message}`);
    }
}

/* ─── Thumbnail Generation ─────────────────────────────────────────────── */

async function generateThumbnail() {
    if (!state.jobId) return;

    try {
        const res = await fetch(`${API}/api/premium/thumbnail/${state.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();

        if (data.error) {
            alert(`Thumbnail failed: ${data.error}`);
        } else {
            window.open(`${API}/api/premium/thumbnail/${state.jobId}/download`, '_blank');
        }
    } catch (e) {
        alert(`Thumbnail error: ${e.message}`);
    }
}

/* ─── Reset ────────────────────────────────────────────────────────────── */

function resetWorkflow() {
    state.exampleFile = null;
    state.examplePath = null;
    state.rawFile = null;
    state.rawPath = null;
    state.jobId = null;

    // Reset UI
    ['example', 'raw'].forEach(type => {
        const dz = document.getElementById(`dropzone-${type}`);
        dz.querySelector('.dropzone-text').textContent = `Drop ${type} video here`;
        dz.querySelector('.dropzone-icon').textContent = type === 'example' ? '\u25B6' : '\uD83C\uDFA5';
        dz.querySelector('.dropzone-sub').textContent = 'or click to browse';
        document.getElementById(`${type}-info`).style.display = 'none';
    });

    [1, 2, 3].forEach(n => {
        document.getElementById(`step-${n}`).classList.remove('done');
        document.getElementById(`step${n}-status`).textContent = '';
    });

    document.getElementById('preview-video').style.display = 'none';
    document.getElementById('monitor-placeholder').style.display = 'block';
    document.getElementById('results-container').style.display = 'none';
    document.getElementById('timeline-container').style.display = 'none';
    document.getElementById('progress-container').style.display = 'none';
    document.getElementById('instructions').value = '';

    updateProcessButton();
}
