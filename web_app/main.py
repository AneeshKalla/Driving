from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from pathlib import Path
import uvicorn
from typing import List, Dict, Any

from web_app.models import DinoAnalyzer, GeminiAnalyzer

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

dino_analyzer = None
gemini_analyzer = None

@app.on_event("startup")
async def startup_event():
    global dino_analyzer, gemini_analyzer
    print("Loading DINO model...")
    dino_analyzer = DinoAnalyzer()
    print("Initializing Gemini analyzer...")
    gemini_analyzer = GeminiAnalyzer()
    print("Models loaded successfully!")

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

@app.post("/analyze/dino/{filename}")
async def analyze_with_dino(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        results = dino_analyzer.analyze(str(file_path))
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DINO analysis failed: {str(e)}")

@app.post("/analyze/gemini/{filename}")
async def analyze_with_gemini(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        results = gemini_analyzer.analyze(str(file_path))
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini analysis failed: {str(e)}")

@app.post("/analyze/full/{filename}")
async def analyze_full(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        dino_results = dino_analyzer.analyze(str(file_path))
        gemini_results = gemini_analyzer.analyze(str(file_path))

        return JSONResponse(content={
            "dino": dino_results,
            "gemini": gemini_results
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
