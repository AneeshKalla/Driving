let currentFilename = null;
let analysisData = null;
let videoDuration = 0;
let flagTimestamps = [];
let flaggedTimestamps = new Set(); // Track timestamps we've already flagged
let shouldAnalyze = false;
let frameInFlight = false;
let finalizeWhenIdle = false;
let lastAnalyzedTime = null;
let isFinalizing = false;

const videoPlayer = document.getElementById('videoPlayer');
const videoSection = document.getElementById('videoSection');
const resultsSection = document.getElementById('resultsSection');
const timelineBar = document.getElementById('timelineBar');
const currentTimeLabel = document.getElementById('currentTime');
const durationLabel = document.getElementById('duration');
const analysisStatus = document.getElementById('analysisStatus');
const frameScoreBox = document.getElementById('frameScoreBox');

videoPlayer.addEventListener('loadedmetadata', () => {
    videoDuration = videoPlayer.duration;
    durationLabel.textContent = formatTime(videoDuration);
});

videoPlayer.addEventListener('timeupdate', () => {
    currentTimeLabel.textContent = formatTime(videoPlayer.currentTime);
});

// Start analyzing as soon as playback begins
videoPlayer.addEventListener('play', () => {
    if (!currentFilename) {
        analysisStatus.innerHTML = '<span style="color: red;">Upload a video to start analysis.</span>';
        videoPlayer.pause();
        return;
    }

    shouldAnalyze = true;
    finalizeWhenIdle = false;
    analysisStatus.innerHTML = '<span style="color: blue;">Live analysis running during playback...</span>';
    queueFrameAnalysis();
});

// Pause analysis when playback pauses
videoPlayer.addEventListener('pause', () => {
    shouldAnalyze = false;
    if (!videoPlayer.ended) {
        analysisStatus.innerHTML = '<span style="color: #666;">Analysis paused.</span>';
    }
});

// Wrap up when playback finishes
videoPlayer.addEventListener('ended', () => {
    shouldAnalyze = false;
    finalizeWhenIdle = true;
    if (!frameInFlight) {
        handlePlaybackComplete();
    }
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
            uploadStatus.innerHTML = '<span style="color: green;">Video uploaded successfully!</span>';

            document.getElementById('videoSource').src = `/video/${currentFilename}`;
            videoPlayer.load();
            videoPlayer.pause();
            videoPlayer.currentTime = 0;

            videoSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            analysisData = null;
            clearTimeline();
            flagTimestamps = [];
            flaggedTimestamps.clear();
            shouldAnalyze = false;
            frameInFlight = false;
            finalizeWhenIdle = false;
            lastAnalyzedTime = null;
            isFinalizing = false;
            analysisStatus.innerHTML = '<span style="color: #666;">Press play to start live analysis.</span>';
            frameScoreBox.textContent = 'Waiting for analysis...';
        } else {
            uploadStatus.innerHTML = `<span style="color: red;">Error: ${result.detail}</span>`;
        }
    } catch (error) {
        uploadStatus.innerHTML = `<span style="color: red;">Upload failed: ${error.message}</span>`;
    } finally {
        uploadBtn.disabled = false;
    }
}

function captureCurrentFrame() {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        canvas.width = videoPlayer.videoWidth;
        canvas.height = videoPlayer.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(videoPlayer, 0, 0, canvas.width, canvas.height);

        canvas.toBlob((blob) => {
            resolve(blob);
        }, 'image/jpeg', 0.95);
    });
}

function queueFrameAnalysis() {
    if (!shouldAnalyze || videoPlayer.paused || videoPlayer.ended || frameInFlight) {
        return;
    }
    requestAnimationFrame(() => analyzeCurrentFrame());
}

function handlePlaybackComplete() {
    finalizeWhenIdle = false;
    shouldAnalyze = false;

    if (flagTimestamps.length > 0) {
        finalizeAnalysis();
    } else {
        analysisStatus.innerHTML = '<span style="color: green;">Playback complete! No incidents detected.</span>';
    }
}

async function analyzeCurrentFrame() {
    if (!shouldAnalyze || videoPlayer.paused || videoPlayer.ended || frameInFlight || !currentFilename) {
        return;
    }

    frameInFlight = true;

    const currentTime = Number(videoPlayer.currentTime.toFixed(3));

    // Avoid re-sending the exact same frame if playback has not advanced
    if (lastAnalyzedTime !== null && Math.abs(currentTime - lastAnalyzedTime) < 0.05) {
        frameInFlight = false;
        setTimeout(queueFrameAnalysis, 50);
        return;
    }

    lastAnalyzedTime = currentTime;
    const frameLabel = formatTime(currentTime);
    analysisStatus.innerHTML = `<span style="color: blue;">Analyzing frame at ${frameLabel}... <div class="loading"></div></span>`;

    try {
        const frameBlob = await captureCurrentFrame();

        const formData = new FormData();
        formData.append('file', frameBlob, `frame_${currentTime}.jpg`);

        const response = await fetch('/score_frame', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            const score = result.score;

            // If score > 0.8, flag it
            if (score > 0.8) {
                const roundedTimestamp = Number(currentTime.toFixed(2));
                if (!flaggedTimestamps.has(roundedTimestamp)) {
                    flaggedTimestamps.add(roundedTimestamp);
                    flagTimestamps.push(roundedTimestamp);
                    addFlagMarker(roundedTimestamp, score);
                }
                analysisStatus.innerHTML = `<span style="color: red;">Incident flagged at ${frameLabel} (score: ${score.toFixed(4)})</span>`;
                frameScoreBox.textContent = `Frame ${frameLabel} • Score: ${score.toFixed(4)} • Flagged`;
            } else {
                analysisStatus.innerHTML = `<span style="color: green;">Frame at ${frameLabel}: ${score.toFixed(4)}</span>`;
                frameScoreBox.textContent = `Frame ${frameLabel} • Score: ${score.toFixed(4)}`;
            }
        } else {
            analysisStatus.innerHTML = `<span style="color: red;">Failed to score frame at ${frameLabel}</span>`;
            frameScoreBox.textContent = `Frame ${frameLabel} • Scoring failed`;
        }
    } catch (error) {
        console.error('Frame analysis error:', error);
        analysisStatus.innerHTML = `<span style="color: red;">Frame analysis error: ${error.message}</span>`;
        frameScoreBox.textContent = `Frame ${frameLabel} • Error: ${error.message}`;
    } finally {
        frameInFlight = false;

        if (videoPlayer.ended || finalizeWhenIdle) {
            handlePlaybackComplete();
        } else if (shouldAnalyze) {
            queueFrameAnalysis();
        }
    }
}

async function finalizeAnalysis() {
    if (flagTimestamps.length === 0 || isFinalizing) {
        return;
    }

    isFinalizing = true;
    analysisStatus.innerHTML = `<span style="color: blue;">Analyzing ${flagTimestamps.length} flagged clips with Gemini... <div class="loading"></div></span>`;

    try {
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
            analysisStatus.innerHTML = '<span style="color: green;">Analysis complete!</span>';
            displayResults();
            resultsSection.classList.remove('hidden');
            const mergedClips = analysisData?.incidents ? analysisData.incidents.length : analysisData.total_clips;
            frameScoreBox.textContent = `Merged clips analyzed: ${mergedClips}`;
        } else {
            analysisStatus.innerHTML = `<span style="color: red;">Error: ${analyzeResult.detail}</span>`;
        }
    } catch (error) {
        analysisStatus.innerHTML = `<span style="color: red;">Analysis failed: ${error.message}</span>`;
        console.error('Finalization error:', error);
    } finally {
        isFinalizing = false;
    }
}

function addFlagMarker(timestamp, score) {
    if (!videoDuration) {
        return;
    }

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

    const mergedClips = analysisData?.incidents ? analysisData.incidents.length : analysisData.total_clips;

    // Summary panel
    let summaryHTML = `
        <p><strong>Video Duration:</strong> ${formatTime(analysisData.total_duration)}</p>
        <p><strong>Flags Detected:</strong> ${analysisData.total_flags}</p>
        <p><strong>Merged Clips:</strong> ${mergedClips}</p>
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
