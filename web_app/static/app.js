let currentFilename = null;
let analysisData = null;
let videoDuration = 0;

const videoPlayer = document.getElementById('videoPlayer');
const videoSection = document.getElementById('videoSection');
const resultsSection = document.getElementById('resultsSection');
const timelineBar = document.getElementById('timelineBar');
const currentTimeLabel = document.getElementById('currentTime');
const durationLabel = document.getElementById('duration');

videoPlayer.addEventListener('loadedmetadata', () => {
    videoDuration = videoPlayer.duration;
    durationLabel.textContent = formatTime(videoDuration);
});

videoPlayer.addEventListener('timeupdate', () => {
    currentTimeLabel.textContent = formatTime(videoPlayer.currentTime);
});

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

async function uploadVideo() {
    const fileInput = document.getElementById('videoInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadStatus = document.getElementById('uploadStatus');

    if (!fileInput.files || fileInput.files.length === 0) {
        uploadStatus.innerHTML = '<span style="color: red;">Please select a video file</span>';
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    uploadStatus.innerHTML = '<span style="color: blue;">Uploading... <div class="loading"></div></span>';

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            currentFilename = result.filename;
            uploadStatus.innerHTML = '<span style="color: green;">✓ Video uploaded successfully!</span>';

            document.getElementById('videoSource').src = `/video/${currentFilename}`;
            videoPlayer.load();

            videoSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            clearTimeline();
        } else {
            uploadStatus.innerHTML = `<span style="color: red;">Error: ${result.detail}</span>`;
        }
    } catch (error) {
        uploadStatus.innerHTML = `<span style="color: red;">Upload failed: ${error.message}</span>`;
    } finally {
        uploadBtn.disabled = false;
    }
}

async function analyzeVideo() {
    if (!currentFilename) {
        alert('Please upload a video first');
        return;
    }

    const analyzeBtn = document.getElementById('analyzeBtn');
    const analysisStatus = document.getElementById('analysisStatus');

    analyzeBtn.disabled = true;
    analysisStatus.innerHTML = '<span style="color: blue;">Analyzing video with Gemini... This may take a while. <div class="loading"></div></span>';

    try {
        const response = await fetch(`/analyze/${currentFilename}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            analysisData = result;

            displayResults();
            createTimeline();

            analysisStatus.innerHTML = '<span style="color: green;">✓ Analysis complete!</span>';
            resultsSection.classList.remove('hidden');
        } else {
            analysisStatus.innerHTML = `<span style="color: red;">Error: ${result.detail}</span>`;
        }
    } catch (error) {
        analysisStatus.innerHTML = `<span style="color: red;">Analysis failed: ${error.message}</span>`;
    } finally {
        analyzeBtn.disabled = false;
    }
}

function displayResults() {
    const dinoResults = document.getElementById('dinoResults');
    const geminiResults = document.getElementById('geminiResults');

    if (!analysisData) return;

    // Summary panel
    let summaryHTML = `
        <p><strong>Video Duration:</strong> ${formatTime(analysisData.total_duration)}</p>
        <p><strong>Incidents Detected:</strong> ${analysisData.total_incidents}</p>
        <p><strong>Random Sampling:</strong> Every 1 second</p>
        <p><strong>Detection Threshold:</strong> Score > 0.80</p>
    `;
    dinoResults.innerHTML = summaryHTML;

    // Incidents panel
    let geminiHTML = '';

    if (analysisData.total_incidents === 0) {
        geminiHTML = '<p>No incidents detected. All random scores were below 0.80.</p>';
    } else {
        geminiHTML = '<h3>Detected Incidents</h3>';
        geminiHTML += '<ul class="incident-list">';

        analysisData.incidents.forEach(incident => {
            geminiHTML += `
                <li class="incident-item" onclick="seekToTime(${incident.timestamp}); showIncidentDetails(${JSON.stringify(incident).replace(/"/g, '&quot;')})">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="incident-time">${formatTime(incident.timestamp)}</span>
                        <span class="confidence-badge">Score: ${incident.random_score}</span>
                    </div>
                    <p style="margin-top: 8px; font-size: 0.9em; color: #666;">
                        Clip: ${formatTime(incident.clip_start)} - ${formatTime(incident.clip_end)}
                    </p>
                    <p style="margin-top: 8px; font-size: 0.95em; line-height: 1.5;">
                        ${incident.analysis.substring(0, 150)}${incident.analysis.length > 150 ? '...' : ''}
                    </p>
                </li>
            `;
        });
        geminiHTML += '</ul>';
    }

    geminiResults.innerHTML = geminiHTML;
}

function createTimeline() {
    clearTimeline();

    if (!videoDuration || videoDuration === 0) {
        setTimeout(createTimeline, 500);
        return;
    }

    if (analysisData && analysisData.incidents) {
        analysisData.incidents.forEach(incident => {
            createMarker(incident);
        });
    }
}

function createMarker(incident) {
    const marker = document.createElement('div');
    marker.className = 'incident-marker gemini';

    const position = (incident.timestamp / videoDuration) * 100;
    marker.style.left = `${position}%`;

    marker.setAttribute('data-time', formatTime(incident.timestamp));
    marker.setAttribute('data-timestamp', incident.timestamp);

    marker.addEventListener('click', () => {
        seekToTime(incident.timestamp);
        showIncidentDetails(incident);
    });

    timelineBar.appendChild(marker);
}

function clearTimeline() {
    timelineBar.innerHTML = '';
}

function seekToTime(timestamp) {
    videoPlayer.currentTime = timestamp;
    videoPlayer.play();
}

function showIncidentDetails(incident) {
    const detailsDiv = document.getElementById('incidentDetails');

    let html = `<h4 style="color: #4ecdc4; margin-bottom: 10px;">
        Incident at ${formatTime(incident.timestamp)}
    </h4>`;

    html += `<p><strong>Random Score:</strong> ${incident.random_score}</p>`;
    html += `<p><strong>Clip Duration:</strong> ${formatTime(incident.clip_start)} - ${formatTime(incident.clip_end)}</p>`;
    html += `<div style="margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px; line-height: 1.6;">
        <strong>Gemini Analysis:</strong><br><br>
        ${incident.analysis}
    </div>`;

    detailsDiv.innerHTML = html;
}

timelineBar.addEventListener('click', (e) => {
    const rect = timelineBar.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const time = percentage * videoDuration;
    seekToTime(time);
});
