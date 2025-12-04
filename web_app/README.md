# Driving Analysis Web App

A web application for analyzing driving videos using AI models (DINO and Gemini VLM) to detect incidents and provide detailed feedback.

## Features

- Upload driving videos (MP4, AVI, MOV formats)
- Automatic analysis using two AI models:
  - **DINO (DINOv3)**: On-device incident detection with confidence scores
  - **Gemini VLM**: Detailed step-by-step analysis of driving behavior
- Interactive video player with timeline
- Visual timeline markers showing detected incidents
- Click markers to view detailed feedback and jump to that moment in the video

## Prerequisites

1. Python 3.8 or higher
2. DINO classifier model file: `dino_classifier.pt` (should be in the root directory)
3. Gemini API key (for Gemini VLM analysis)

## Installation

1. Install dependencies (from root directory):
```bash
pip install -r requirements.txt
```

Or if you're already in the web_app directory:
```bash
pip install -r ../requirements.txt
```

2. Set up Gemini API key (optional, but required for Gemini analysis):
```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# Linux/Mac
export GEMINI_API_KEY=your_api_key_here
```

## Running the Application

### Quick Start (Recommended)

From the root directory, run the dev script (automatically opens browser):
```bash
python dev.py
```

The browser will automatically open to `http://localhost:8000`

### Alternative Methods

**Option 1 - Run main.py directly:**
```bash
python web_app/main.py
```

**Option 2 - Using uvicorn:**
```bash
uvicorn web_app.main:app --reload --host 0.0.0.0 --port 8000
```

Then manually navigate to `http://localhost:8000` in your browser.

## Usage

1. **Upload a Video**: Click "Choose File" and select a driving video, then click "Upload Video"
2. **Analyze**: Once uploaded, click "Analyze Video" to start the analysis
3. **View Results**:
   - See DINO detection results on the left panel
   - See Gemini analysis on the right panel
   - Red markers on timeline = DINO detections
   - Teal markers on timeline = Gemini flagged incidents
4. **Interact**: Click on any marker to jump to that timestamp and view details

## How It Works

### DINO Analysis
- Extracts frames from video at 0.5-second intervals
- Runs each frame through DINOv3 vision transformer
- Binary classifier detects potential incidents
- Returns timestamps and confidence scores (0-1)

### Gemini Analysis
- Uploads video to Gemini API
- Uses Gemini-3-pro-preview model
- Receives detailed step-by-step analysis
- Identifies specific bad driving behaviors with timestamps

## API Endpoints

- `GET /` - Web interface
- `POST /upload` - Upload video file
- `GET /video/{filename}` - Stream video
- `POST /analyze/dino/{filename}` - DINO analysis only
- `POST /analyze/gemini/{filename}` - Gemini analysis only
- `POST /analyze/full/{filename}` - Both analyses

## Notes

- Only one video can be analyzed at a time (previous uploads are overwritten)
- Video files are stored temporarily in `web_app/uploads/`
- DINO model runs locally (CPU/GPU based on availability)
- Gemini analysis requires internet connection and API key
- First analysis may take longer due to model loading

## Troubleshooting

**DINO model not loading:**
- Ensure `dino_classifier.pt` is in the root directory
- Check PyTorch installation: `python -c "import torch; print(torch.__version__)"`

**Gemini analysis failing:**
- Verify GEMINI_API_KEY is set correctly
- Check internet connection
- Ensure you have API quota remaining

**Video not playing:**
- Try converting video to MP4 format
- Ensure video codec is supported by browser (H.264 recommended)
