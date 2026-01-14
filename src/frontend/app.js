/**
 * SunoMusicGenerator Enhanced Frontend
 *
 * Features:
 * - Source file discovery and table view
 * - Per-song generation actions
 * - Prompt editor with versioning
 * - Cover art version management
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';

// ========================================
// Tab Management
// ========================================

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;

        // Update buttons
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(tabName).classList.add('active');

        // Load data when tab activates
        if (tabName === 'sources') {
            loadSources();
        } else if (tabName === 'status') {
            loadStatus();
        } else if (tabName === 'covers') {
            populateCoverSongSelect();
        }
    });
});

// ========================================
// Sources Tab - Main View
// ========================================

async function loadSources() {
    const container = document.getElementById('sourcesContainer');
    container.innerHTML = '<p class="loading">Loading sources...</p>';

    try {
        const response = await fetch(`${API_BASE_URL}/sources/list`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load sources');
        }

        if (data.sources.length === 0) {
            container.innerHTML = '<p class="info-message">No source files found in Songs/*/Text/*.txt</p>';
            return;
        }

        // Create table
        let html = `
            <table class="sources-table">
                <thead>
                    <tr>
                        <th>Song ID</th>
                        <th>Title</th>
                        <th>Preview</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.sources.forEach(source => {
            const status = `
                <div class="status-indicators">
                    <span class="status-indicator ${source.has_lyrics ? 'success' : 'pending'}" title="Lyrics">L</span>
                    <span class="status-indicator ${source.has_audio ? 'success' : 'pending'}" title="Audio">A</span>
                    <span class="status-indicator ${source.has_cover ? 'success' : 'pending'}" title="Cover">C</span>
                </div>
            `;

            html += `
                <tr>
                    <td><strong>${source.song_id}</strong></td>
                    <td>${source.title || '<em>Not set</em>'}</td>
                    <td class="text-preview">${source.text_preview || 'No preview'}</td>
                    <td>${status}</td>
                    <td class="action-buttons">
                        <button onclick="generateLyrics('${source.song_id}')" class="btn-action" title="Generate Lyrics">🎤 Lyrics</button>
                        <button onclick="generateAudio('${source.song_id}')" class="btn-action" title="Generate Audio">🎵 Audio</button>
                        <button onclick="generateCover('${source.song_id}')" class="btn-action" title="Generate Cover">🎨 Cover</button>
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading sources:', error);
        container.innerHTML = `<p class="error-message">Error: ${error.message}</p>`;
    }
}

// ========================================
// Generation Actions
// ========================================

function showModal(title, message) {
    const modal = document.getElementById('progressModal');
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    document.getElementById('modalError').classList.add('hidden');
    modal.classList.add('active');
}

function hideModal() {
    document.getElementById('progressModal').classList.remove('active');
}

function showModalError(message) {
    const errorDiv = document.getElementById('modalError');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

async function generateLyrics(songId) {
    showModal('Generating Lyrics', `Creating lyrics for ${songId}...`);

    try {
        // First, read the source text
        const sourcePath = `Songs/${songId}/Text/${songId}.txt`;

        // We need to read the file from the server
        // For now, we'll let the backend handle this
        const response = await fetch(`${API_BASE_URL}/lyrics/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                song_id: songId,
                narrative_text: '', // Backend will read from file
                prompt_template_path: 'prompts/EurekaProtocol.md',
                force_regenerate: false
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Lyrics generation failed');
        }

        hideModal();
        alert(`✅ Lyrics generated successfully!\nPath: ${data.path}`);
        loadSources(); // Refresh table

    } catch (error) {
        showModalError(error.message);
        console.error('Error:', error);
    }
}

async function generateAudio(songId) {
    showModal('Generating Audio', `Creating audio for ${songId}...`);

    try {
        // Check if lyrics exist
        const lyricsPath = `Songs/${songId}/Lyrics/${songId}.txt`;

        // Read lyrics and generate
        const response = await fetch(`${API_BASE_URL}/audio/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                song_id: songId,
                lyrics: '', // Backend will read from file
                title: songId, // Use song ID as title for now
                tags: 'educational, rock',
                download_formats: ['wav', 'mp3'],
                force_regenerate: false
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Audio generation failed');
        }

        hideModal();
        alert(`✅ Audio generated successfully!\nDirectory: ${data.directory}\nClips: ${data.clip_ids.length}`);
        loadSources(); // Refresh table

    } catch (error) {
        showModalError(error.message);
        console.error('Error:', error);
    }
}

async function generateCover(songId) {
    showModal('Generating Cover Art', `Creating cover art for ${songId}...`);

    try {
        // Check if lyrics exist and generate cover
        const response = await fetch(`${API_BASE_URL}/cover/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                song_id: songId,
                lyrics: '', // Backend will read from file
                prompt_template_path: 'prompts/CoverArtPrompt.md',
                force_regenerate: false
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Cover generation failed');
        }

        hideModal();
        alert(`✅ Cover art generated successfully!\nPath: ${data.path}\nSize: ${(data.size / 1024 / 1024).toFixed(2)} MB`);
        loadSources(); // Refresh table

    } catch (error) {
        showModalError(error.message);
        console.error('Error:', error);
    }
}

// ========================================
// Prompts Tab
// ========================================

let currentPromptName = '';

document.getElementById('loadPromptBtn').addEventListener('click', loadPrompt);
document.getElementById('savePromptBtn').addEventListener('click', savePrompt);

async function loadPrompt() {
    const promptName = document.getElementById('promptSelect').value;
    const textarea = document.getElementById('promptContent');
    const status = document.getElementById('promptStatus');

    status.textContent = 'Loading...';
    status.className = 'status-loading';

    try {
        const response = await fetch(`${API_BASE_URL}/prompts/read?prompt_name=${promptName}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load prompt');
        }

        textarea.value = data.content;
        currentPromptName = promptName;
        status.textContent = `✓ Loaded ${promptName}`;
        status.className = 'status-success';

        setTimeout(() => {
            status.textContent = '';
        }, 3000);

    } catch (error) {
        console.error('Error loading prompt:', error);
        status.textContent = `✗ Error: ${error.message}`;
        status.className = 'status-error';
    }
}

async function savePrompt() {
    if (!currentPromptName) {
        alert('Please load a prompt first');
        return;
    }

    const content = document.getElementById('promptContent').value;
    const status = document.getElementById('promptStatus');

    if (!content.trim()) {
        alert('Prompt content cannot be empty');
        return;
    }

    status.textContent = 'Saving...';
    status.className = 'status-loading';

    try {
        const response = await fetch(`${API_BASE_URL}/prompts/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt_name: currentPromptName,
                content: content
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to save prompt');
        }

        status.textContent = `✓ Saved! Backup: ${data.timestamp}`;
        status.className = 'status-success';

    } catch (error) {
        console.error('Error saving prompt:', error);
        status.textContent = `✗ Error: ${error.message}`;
        status.className = 'status-error';
    }
}

// ========================================
// Cover Art Versions Tab
// ========================================

async function populateCoverSongSelect() {
    const select = document.getElementById('coverSongSelect');

    try {
        const response = await fetch(`${API_BASE_URL}/sources/list`);
        const data = await response.json();

        if (response.ok) {
            select.innerHTML = '<option value="">-- Select a song --</option>';
            data.sources.forEach(source => {
                if (source.has_cover) {
                    select.innerHTML += `<option value="${source.song_id}">${source.song_id} - ${source.title || 'Untitled'}</option>`;
                }
            });
        }
    } catch (error) {
        console.error('Error loading songs:', error);
    }
}

document.getElementById('loadCoverVersionsBtn').addEventListener('click', loadCoverVersions);

async function loadCoverVersions() {
    const songId = document.getElementById('coverSongSelect').value;
    const container = document.getElementById('coverVersionsContainer');

    if (!songId) {
        alert('Please select a song');
        return;
    }

    container.innerHTML = '<p class="loading">Loading cover versions...</p>';

    try {
        const response = await fetch(`${API_BASE_URL}/cover/versions/${songId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load cover versions');
        }

        if (data.versions.length === 0) {
            container.innerHTML = '<p class="info-message">No cover art versions found</p>';
            return;
        }

        let html = '<div class="cover-versions-grid">';

        data.versions.forEach(version => {
            const activeClass = version.is_active ? 'active-cover' : '';
            const activeLabel = version.is_active ? '<span class="active-label">ACTIVE</span>' : '';

            html += `
                <div class="cover-version-card ${activeClass}">
                    <div class="cover-preview">
                        <img src="${version.file_path}" alt="Cover version ${version.version_id}"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22><rect width=%22200%22 height=%22200%22 fill=%22%23ccc%22/><text x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 dy=%22.3em%22>No Image</text></svg>'">
                    </div>
                    <div class="cover-info">
                        ${activeLabel}
                        <p><strong>Version:</strong> ${version.version_id}</p>
                        <p><strong>Created:</strong> ${version.created_at}</p>
                        <p><strong>Size:</strong> ${(version.size / 1024 / 1024).toFixed(2)} MB</p>
                        ${!version.is_active ? `<button onclick="promoteCover('${songId}', '${version.version_id}')" class="btn-action">✓ Set as Active</button>` : ''}
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading cover versions:', error);
        container.innerHTML = `<p class="error-message">Error: ${error.message}</p>`;
    }
}

async function promoteCover(songId, versionId) {
    if (!confirm(`Set version ${versionId} as the active cover for ${songId}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/cover/promote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                song_id: songId,
                version_id: versionId
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to promote cover');
        }

        alert(`✅ Cover version ${versionId} is now active!`);
        loadCoverVersions(); // Refresh

    } catch (error) {
        alert(`Error: ${error.message}`);
        console.error('Error promoting cover:', error);
    }
}

// ========================================
// Status Tab
// ========================================

async function loadStatus() {
    const container = document.getElementById('statusContainer');
    container.innerHTML = '<p class="loading">Loading...</p>';

    try {
        const response = await fetch(`${API_BASE_URL}/status`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error('Failed to load status');
        }

        if (data.songs.length === 0) {
            container.innerHTML = '<p class="info-message">No songs generated yet.</p>';
            return;
        }

        let html = `
            <table class="status-table">
                <thead>
                    <tr>
                        <th>Song ID</th>
                        <th>Title</th>
                        <th>Lyrics</th>
                        <th>Audio</th>
                        <th>Cover</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.songs.forEach(song => {
            html += `
                <tr>
                    <td><strong>${song.song_id}</strong></td>
                    <td>${song.title}</td>
                    <td>${getStatusBadge(song.has_lyrics)}</td>
                    <td>${getStatusBadge(song.has_audio)}</td>
                    <td>${getStatusBadge(song.has_cover)}</td>
                    <td>${song.created_at}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<p class="error-message">Error loading status: ${error.message}</p>`;
    }
}

function getStatusBadge(hasItem) {
    return hasItem
        ? '<span class="status-badge success">✓</span>'
        : '<span class="status-badge pending">✗</span>';
}

// ========================================
// Event Listeners
// ========================================

document.getElementById('refreshSourcesBtn').addEventListener('click', loadSources);
document.getElementById('refreshStatusBtn').addEventListener('click', loadStatus);

// ========================================
// Initialize
// ========================================

window.addEventListener('DOMContentLoaded', () => {
    loadSources(); // Load sources on startup
});
