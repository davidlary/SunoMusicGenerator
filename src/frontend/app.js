/**
 * SunoMusicGenerator Frontend
 *
 * Vanilla JavaScript application for interacting with the API.
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';

// Tab switching
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

        // Load status if status tab
        if (tabName === 'status') {
            loadStatus();
        }
    });
});

// Form submission
document.getElementById('generateForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const songId = document.getElementById('songId').value;
    const title = document.getElementById('title').value;
    const narrative = document.getElementById('narrative').value;
    const tags = document.getElementById('tags').value;
    const forceRegenerate = document.getElementById('forceRegenerate').checked;

    // Hide previous results/errors
    document.getElementById('result').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');

    // Show progress
    document.getElementById('progress').classList.remove('hidden');
    document.getElementById('progressText').textContent = 'Generating full song...';

    try {
        const response = await fetch(`${API_BASE_URL}/pipeline/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                song_id: songId,
                narrative_text: narrative,
                title: title,
                tags: tags,
                force_regenerate: forceRegenerate
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Generation failed');
        }

        // Hide progress
        document.getElementById('progress').classList.add('hidden');

        // Show result
        displayResult(data);

    } catch (error) {
        console.error('Error:', error);

        // Hide progress
        document.getElementById('progress').classList.add('hidden');

        // Show error
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = error.message;
    }
});

// Display generation result
function displayResult(data) {
    const resultDiv = document.getElementById('result');
    const contentDiv = document.getElementById('resultContent');

    contentDiv.innerHTML = `
        <div class="result-item">
            <h4>🎤 Lyrics</h4>
            <p><strong>Path:</strong> ${data.lyrics.path}</p>
            <p><strong>Model:</strong> ${data.lyrics.model}</p>
            <p><strong>Regenerated:</strong> ${data.lyrics.regenerated ? 'Yes' : 'No (existing)'}</p>
        </div>

        <div class="result-item">
            <h4>🎵 Audio</h4>
            <p><strong>Directory:</strong> ${data.audio.directory}</p>
            <p><strong>Clips:</strong> ${data.audio.clip_ids.length}</p>
            <p><strong>Regenerated:</strong> ${data.audio.regenerated ? 'Yes' : 'No (existing)'}</p>
        </div>

        <div class="result-item">
            <h4>🎨 Cover Art</h4>
            <p><strong>Path:</strong> ${data.cover.path}</p>
            <p><strong>Size:</strong> ${(data.cover.size / 1024 / 1024).toFixed(2)} MB</p>
            <p><strong>Regenerated:</strong> ${data.cover.regenerated ? 'Yes' : 'No (existing)'}</p>
        </div>
    `;

    resultDiv.classList.remove('hidden');
}

// Load status
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
            container.innerHTML = '<p style="color: #64748b;">No songs generated yet.</p>';
            return;
        }

        // Create table
        let html = `
            <table class="status-table">
                <thead>
                    <tr>
                        <th>Song ID</th>
                        <th>Title</th>
                        <th>Lyrics</th>
                        <th>Audio</th>
                        <th>Cover</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.songs.forEach(song => {
            html += `
                <tr>
                    <td><strong>${song.song_id}</strong></td>
                    <td>${song.title}</td>
                    <td>${getBadge(song.has_lyrics)}</td>
                    <td>${getBadge(song.has_audio)}</td>
                    <td>${getBadge(song.has_cover)}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<p style="color: #dc2626;">Error loading status: ${error.message}</p>`;
    }
}

// Get status badge
function getBadge(hasItem) {
    if (hasItem) {
        return '<span class="status-badge success">✓</span>';
    } else {
        return '<span class="status-badge pending">✗</span>';
    }
}

// Refresh status button
document.getElementById('refreshBtn').addEventListener('click', loadStatus);

// Load status on page load
window.addEventListener('DOMContentLoaded', () => {
    // Status will be loaded when tab is clicked
});
