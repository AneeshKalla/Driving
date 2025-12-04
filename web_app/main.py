from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from pathlib import Path
import uvicorn
from typing import List, Dict, Any
import random
import cv2
from google import genai

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

gemini_client = None

@app.on_event("startup")
async def startup_event():
    global gemini_client
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        gemini_client = genai.Client(api_key=api_key)
        print("Gemini client initialized successfully!")
    else:
        print("Warning: GEMINI_API_KEY not found in environment variables")

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

    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")

    try:
        # Clear old clips
        for clip_file in CLIPS_DIR.glob("*"):
            clip_file.unlink()

        # Get video duration
        duration = get_video_duration(str(file_path))
        print(f"Video duration: {duration:.2f} seconds")

        incidents = []

        # Sample every second
        for second in range(int(duration)):
            # Generate random number (0.00 to 1.00)
            random_score = round(random.random(), 2)
            print(f"Second {second}: score = {random_score}")

            if random_score > 0.8:
                # Extract clip: 10 seconds before to 5 seconds after
                clip_start = second - 10
                clip_end = second + 5

                # Create clip
                clip_filename = f"clip_{second}s.mp4"
                clip_path = CLIPS_DIR / clip_filename

                print(f"Extracting clip from {clip_start}s to {clip_end}s...")
                extract_clip(str(file_path), clip_start, clip_end, str(clip_path))

                # Send to Gemini
                print(f"Analyzing clip with Gemini...")
                uploaded_file = gemini_client.files.upload(file=str(clip_path))

                response = gemini_client.models.generate_content(
                    model="gemini-3-pro-preview",
                    contents=[
                        uploaded_file,
                        "Analyze this driving video clip. Identify any bad driving behaviors such as: unsafe lane changes, following too closely, failure to yield, distracted driving, speeding, or any traffic violations. Be specific and concise about what happens."
                    ]
                )

                incidents.append({
                    "timestamp": second,
                    "clip_start": max(0, clip_start),
                    "clip_end": min(duration, clip_end),
                    "random_score": random_score,
                    "analysis": response.text
                })

                print(f"Analysis complete for second {second}")

        return JSONResponse(content={
            "total_duration": duration,
            "incidents": incidents,
            "total_incidents": len(incidents)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
