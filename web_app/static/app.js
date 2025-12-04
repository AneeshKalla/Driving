let currentFilename = null;
let dinoData = null;
let geminiData = null;
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
    analysisStatus.innerHTML = '<span style="color: blue;">Analyzing video with DINO and Gemini... <div class="loading"></div></span>';

    try {
        const response = await fetch(`/analyze/full/${currentFilename}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            dinoData = result.dino;
            geminiData = result.gemini;

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

    if (dinoData) {
        let dinoHTML = `
            <p><strong>Total Frames Analyzed:</strong> ${dinoData.total_frames}</p>
            <p><strong>Frame Interval:</strong> ${dinoData.frame_interval}s</p>
            <p><strong>Detection Threshold:</strong> ${dinoData.threshold}</p>
            <p><strong>Incidents Detected:</strong> ${dinoData.incidents.length}</p>
        `;

        if (dinoData.incidents.length > 0) {
            dinoHTML += '<ul class="incident-list">';
            dinoData.incidents.forEach((incident, index) => {
                dinoHTML += `
                    <li class="incident-item" onclick="seekToTime(${incident.timestamp})">
                        <span class="incident-time">${formatTime(incident.timestamp)}</span>
                        <span class="confidence-badge">${(incident.confidence * 100).toFixed(1)}%</span>
                    </li>
                `;
            });
            dinoHTML += '</ul>';
        }

        dinoResults.innerHTML = dinoHTML;
    }

    if (geminiData) {
        let geminiHTML = '';

        if (geminiData.error) {
            geminiHTML = `<p style="color: red;">${geminiData.analysis}</p>`;
        } else {
            geminiHTML = `
                <div style="white-space: pre-wrap; line-height: 1.8;">${geminiData.analysis}</div>
            `;

            if (geminiData.incidents.length > 0) {
                geminiHTML += '<h3 style="margin-top: 20px;">Flagged Incidents:</h3>';
                geminiHTML += '<ul class="incident-list">';
                geminiData.incidents.forEach(incident => {
                    geminiHTML += `
                        <li class="incident-item" onclick="seekToTime(${incident.timestamp})">
                            <span class="incident-time">${formatTime(incident.timestamp)}</span>
                            <p style="margin-top: 5px;">${incident.description}</p>
                        </li>
                    `;
                });
                geminiHTML += '</ul>';
            }
        }

        geminiResults.innerHTML = geminiHTML;
    }
}

function createTimeline() {
    clearTimeline();

    if (!videoDuration || videoDuration === 0) {
        setTimeout(createTimeline, 500);
        return;
    }

    if (dinoData && dinoData.incidents) {
        dinoData.incidents.forEach(incident => {
            createMarker(incident.timestamp, 'dino', incident);
        });
    }

    if (geminiData && geminiData.incidents) {
        geminiData.incidents.forEach(incident => {
            createMarker(incident.timestamp, 'gemini', incident);
        });
    }
}

function createMarker(timestamp, type, data) {
    const marker = document.createElement('div');
    marker.className = `incident-marker ${type}`;

    const position = (timestamp / videoDuration) * 100;
    marker.style.left = `${position}%`;

    marker.setAttribute('data-time', formatTime(timestamp));
    marker.setAttribute('data-timestamp', timestamp);

    marker.addEventListener('click', () => {
        seekToTime(timestamp);
        showIncidentDetails(data, type);
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

function showIncidentDetails(data, type) {
    const detailsDiv = document.getElementById('incidentDetails');

    let html = `<h4 style="color: ${type === 'dino' ? '#ff6b6b' : '#4ecdc4'}; margin-bottom: 10px;">
        ${type.toUpperCase()} Detection
    </h4>`;

    html += `<p><strong>Timestamp:</strong> ${formatTime(data.timestamp)}</p>`;

    if (type === 'dino') {
        html += `<p><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(1)}%</p>`;
        html += `<p><strong>Type:</strong> ${data.type}</p>`;
    } else {
        html += `<p><strong>Description:</strong> ${data.description}</p>`;
    }

    detailsDiv.innerHTML = html;
}

timelineBar.addEventListener('click', (e) => {
    const rect = timelineBar.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const time = percentage * videoDuration;
    seekToTime(time);
});
