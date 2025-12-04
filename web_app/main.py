from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from pathlib import Path
import uvicorn
from typing import List, Dict, Any
import cv2
from dotenv import load_dotenv

# Load environment variables from root .env file
load_dotenv()

# Import predict functions from root models.py
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import predict_image, predict_video

app = FastAPI(title="Driving Analysis Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("web_app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="web_app/static"), name="static")

CLIPS_DIR = Path("web_app/clips")
CLIPS_DIR.mkdir(exist_ok=True)

@app.on_event("startup")
async def startup_event():
    print("Driving Analysis Web App started!")
    print("Using Gemini VLM for video analysis")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("web_app/templates/index.html", "r") as f:
        return f.read()

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename.endswith(('.mp4', '.avi', '.mov', '.MP4')):
        raise HTTPException(status_code=400, detail="Only video files are allowed")

    for existing_file in UPLOAD_DIR.glob("*"):
        existing_file.unlink()

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": file.filename, "message": "Video uploaded successfully"}

@app.get("/video/{filename}")
async def get_video(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(file_path, media_type="video/mp4")

def extract_clip(video_path: str, start_time: float, end_time: float, output_path: str):
    """Extract a clip from video between start_time and end_time (in seconds)"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Ensure times are within bounds
    start_time = max(0, start_time)

    # Set up video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Seek to start time
    cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)

    current_time = start_time
    while current_time < end_time:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        current_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000

    cap.release()
    out.release()

    return output_path

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps
    cap.release()
    return duration

FRAMES_DIR = Path("web_app/frames")
FRAMES_DIR.mkdir(exist_ok=True)

@app.post("/score_frame")
async def score_frame(file: UploadFile = File(...)):
    """Score a single frame using DINO model"""
    try:
        # Save frame temporarily
        frame_path = FRAMES_DIR / f"temp_{file.filename}"
        with open(frame_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Get DINO score
        score = predict_image(str(frame_path))

        # Clean up
        frame_path.unlink()

        return JSONResponse(content={"score": round(score, 4)})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

def merge_overlapping_intervals(intervals: List[tuple]) -> List[tuple]:
    """Merge overlapping time intervals"""
    if not intervals:
        return []

    # Sort by start time
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]

    for current in sorted_intervals[1:]:
        last = merged[-1]
        # If current overlaps with last, merge them
        if current[0] <= last[1]:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)

    return merged

@app.post("/analyze_flags/{filename}")
async def analyze_flags(filename: str, flags: List[float]):
    """Aggregate flags into clips and analyze with Gemini"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        # Clear old clips
        for clip_file in CLIPS_DIR.glob("*"):
            clip_file.unlink()

        duration = get_video_duration(str(file_path))
        print(f"Video duration: {duration:.2f} seconds")
        print(f"Received {len(flags)} flags: {flags}")

        # Create intervals for each flag (10s before to 5s after)
        intervals = []
        for flag_time in flags:
            start = max(0, flag_time - 10)
            end = min(duration, flag_time + 5)
            intervals.append((start, end))

        # Merge overlapping intervals
        merged_intervals = merge_overlapping_intervals(intervals)
        print(f"Merged into {len(merged_intervals)} clips: {merged_intervals}")

        # Extract and analyze each merged clip
        incidents = []
        for i, (clip_start, clip_end) in enumerate(merged_intervals):
            clip_filename = f"clip_{i}_{clip_start:.1f}_{clip_end:.1f}.mp4"
            clip_path = CLIPS_DIR / clip_filename

            print(f"Extracting clip {i+1}/{len(merged_intervals)}: {clip_start:.1f}s to {clip_end:.1f}s")
            extract_clip(str(file_path), clip_start, clip_end, str(clip_path))

            # Analyze with Gemini
            print(f"Analyzing clip {i+1} with Gemini...")
            gemini_analysis = predict_video(str(clip_path))

            incidents.append({
                "clip_number": i + 1,
                "clip_start": clip_start,
                "clip_end": clip_end,
                "analysis": gemini_analysis
            })
            print(f"Clip {i+1} analysis complete!")

        print(f"All analysis complete! {len(incidents)} clips analyzed.")

        return JSONResponse(content={
            "total_duration": duration,
            "total_flags": len(flags),
            "incidents": incidents,
            "total_clips": len(incidents)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
