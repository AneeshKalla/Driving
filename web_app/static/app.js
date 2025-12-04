let currentFilename = null;
let analysisData = null;
let videoDuration = 0;
let flagTimestamps = [];

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
            flagTimestamps = [];
        } else {
            uploadStatus.innerHTML = `<span style="color: red;">Error: ${result.detail}</span>`;
        }
    } catch (error) {
        uploadStatus.innerHTML = `<span style="color: red;">Upload failed: ${error.message}</span>`;
    } finally {
        uploadBtn.disabled = false;
    }
}

function captureFrame(video, time) {
    return new Promise((resolve) => {
        video.currentTime = time;
        video.onseeked = () => {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            canvas.toBlob((blob) => {
                resolve(blob);
            }, 'image/jpeg', 0.95);
        };
    });
}

async function analyzeVideo() {
    if (!currentFilename) {
        alert('Please upload a video first');
        return;
    }

    if (!videoDuration || videoDuration === 0) {
        alert('Video not loaded yet. Please wait.');
        return;
    }

    const analyzeBtn = document.getElementById('analyzeBtn');
    const analysisStatus = document.getElementById('analysisStatus');

    analyzeBtn.disabled = true;
    clearTimeline();
    flagTimestamps = [];

    try {
        // Phase 1: Extract and score frames
        analysisStatus.innerHTML = '<span style="color: blue;">Extracting and scoring frames... <div class="loading"></div></span>';

        const frameInterval = 1; // Sample every 1 second
        const totalFrames = Math.floor(videoDuration);

        for (let second = 0; second < totalFrames; second++) {
            analysisStatus.innerHTML = `<span style="color: blue;">Scoring frame ${second + 1}/${totalFrames}... <div class="loading"></div></span>`;

            // Capture frame at this timestamp
            const frameBlob = await captureFrame(videoPlayer, second);

            // Send frame to backend for scoring
            const formData = new FormData();
            formData.append('file', frameBlob, `frame_${second}.jpg`);

            const response = await fetch('/score_frame', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                const score = result.score;
                console.log(`Frame at ${second}s: score = ${score}`);

                // If score > 0.8, flag it
                if (score > 0.8) {
                    flagTimestamps.push(second);
                    addFlagMarker(second, score);
                }
            } else {
                console.error(`Failed to score frame at ${second}s`);
            }
        }

        console.log(`Total flags: ${flagTimestamps.length}`, flagTimestamps);

        // Phase 2: Analyze flagged clips with Gemini
        if (flagTimestamps.length === 0) {
            analysisStatus.innerHTML = '<span style="color: green;">✓ Analysis complete! No incidents detected (all scores < 0.80).</span>';
            analysisData = {
                total_duration: videoDuration,
                total_flags: 0,
                total_clips: 0,
                incidents: []
            };
            displayResults();
            resultsSection.classList.remove('hidden');
        } else {
            analysisStatus.innerHTML = `<span style="color: blue;">Analyzing ${flagTimestamps.length} flagged clips with Gemini... <div class="loading"></div></span>`;

            const analyzeResponse = await fetch(`/analyze_flags/${currentFilename}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(flagTimestamps)
            });

            const analyzeResult = await analyzeResponse.json();

            if (analyzeResponse.ok) {
                analysisData = analyzeResult;
                analysisStatus.innerHTML = '<span style="color: green;">✓ Analysis complete!</span>';
                displayResults();
                resultsSection.classList.remove('hidden');
            } else {
                analysisStatus.innerHTML = `<span style="color: red;">Error: ${analyzeResult.detail}</span>`;
            }
        }

    } catch (error) {
        analysisStatus.innerHTML = `<span style="color: red;">Analysis failed: ${error.message}</span>`;
        console.error('Analysis error:', error);
    } finally {
        analyzeBtn.disabled = false;
    }
}

function addFlagMarker(timestamp, score) {
    const marker = document.createElement('div');
    marker.className = 'incident-marker flag';
    marker.style.backgroundColor = 'red';

    const position = (timestamp / videoDuration) * 100;
    marker.style.left = `${position}%`;

    marker.setAttribute('data-time', formatTime(timestamp));
    marker.setAttribute('data-timestamp', timestamp);
    marker.setAttribute('data-score', score);

    marker.addEventListener('click', () => {
        seekToTime(timestamp);
    });

    timelineBar.appendChild(marker);
}

function displayResults() {
    const dinoResults = document.getElementById('dinoResults');
    const geminiResults = document.getElementById('geminiResults');

    if (!analysisData) return;

    // Summary panel
    let summaryHTML = `
        <p><strong>Video Duration:</strong> ${formatTime(analysisData.total_duration)}</p>
        <p><strong>Flags Detected:</strong> ${analysisData.total_flags}</p>
        <p><strong>Merged Clips:</strong> ${analysisData.total_clips}</p>
        <p><strong>Detection Threshold:</strong> DINO Score > 0.80</p>
    `;
    dinoResults.innerHTML = summaryHTML;

    // Incidents panel
    let geminiHTML = '';

    if (analysisData.total_clips === 0) {
        geminiHTML = '<p>No incidents detected. All DINO scores were below 0.80.</p>';
    } else {
        geminiHTML = '<h3>Analyzed Clips</h3>';
        geminiHTML += '<ul class="incident-list">';

        analysisData.incidents.forEach(incident => {
            geminiHTML += `
                <li class="incident-item" onclick="seekToTime(${incident.clip_start}); showIncidentDetails(${JSON.stringify(incident).replace(/"/g, '&quot;')})">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="incident-time">Clip ${incident.clip_number}</span>
                        <span class="confidence-badge">${formatTime(incident.clip_start)} - ${formatTime(incident.clip_end)}</span>
                    </div>
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
        Clip ${incident.clip_number}: ${formatTime(incident.clip_start)} - ${formatTime(incident.clip_end)}
    </h4>`;

    html += `<p><strong>Duration:</strong> ${(incident.clip_end - incident.clip_start).toFixed(1)}s</p>`;
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
