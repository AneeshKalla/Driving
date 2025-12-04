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
import random

# Load environment variables from root .env file
load_dotenv()

# Import Gemini for video analysis
from google import genai
from time import sleep

client = genai.Client()

def predict_video(path: str):
    """Analyze video clip with Gemini VLM"""
    myfile = client.files.upload(file=path)
    sleep(5)
    response = client.models.generate_content(
        model="gemini-3-pro-preview", contents=[myfile, "Explain what bad driving is happening in the video, if any."]
    )
    return response.text

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

@app.post("/analyze/{filename}")
async def analyze_video(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        # Clear old clips
        for clip_file in CLIPS_DIR.glob("*"):
            clip_file.unlink()

        # Get video duration
        duration = get_video_duration(str(file_path))
        print(f"Video duration: {duration:.2f} seconds")

        # Phase 1: Sample every 3 seconds and extract clips where random score > 0.8
        clips_to_analyze = []

        # Sample every 3 seconds
        for second in range(0, int(duration), 3):
            # Generate random score (0.00 to 1.00)
            random_score = round(random.random(), 2)
            print(f"Second {second}: random score = {random_score}")

            if random_score > 0.8:
                # Extract clip: 10 seconds before to 5 seconds after
                clip_start = second - 10
                clip_end = second + 5

                # Create clip
                clip_filename = f"clip_{second}s.mp4"
                clip_path = CLIPS_DIR / clip_filename

                print(f"Extracting clip from {clip_start}s to {clip_end}s...")
                extract_clip(str(file_path), clip_start, clip_end, str(clip_path))

                clips_to_analyze.append({
                    "timestamp": second,
                    "clip_start": max(0, clip_start),
                    "clip_end": min(duration, clip_end),
                    "random_score": random_score,
                    "clip_path": str(clip_path)
                })

        # Phase 2: Send all clips to Gemini at once
        print(f"\nPhase 2: Analyzing {len(clips_to_analyze)} clips with Gemini VLM...")
        incidents = []

        for i, clip_data in enumerate(clips_to_analyze):
            print(f"Analyzing clip {i+1}/{len(clips_to_analyze)} (timestamp: {clip_data['timestamp']}s)...")
            gemini_analysis = predict_video(clip_data['clip_path'])

            incidents.append({
                "timestamp": clip_data["timestamp"],
                "clip_start": clip_data["clip_start"],
                "clip_end": clip_data["clip_end"],
                "random_score": clip_data["random_score"],
                "analysis": gemini_analysis
            })
            print(f"Clip {i+1} analysis complete!")

        print(f"\nAll analysis complete! Found {len(incidents)} incidents.")

        return JSONResponse(content={
            "total_duration": duration,
            "incidents": incidents,
            "total_incidents": len(incidents)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
