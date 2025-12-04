# Driving Analysis Web App

A web application for analyzing driving videos using random sampling and Google Gemini VLM for detailed analysis.

## Features

- Upload driving videos (MP4, AVI, MOV formats)
- Random sampling: Samples every 3 seconds with random scores (0.00-1.00)
- When random score > 0.80:
  - Extracts a 15-second clip (10 seconds before + 5 seconds after)
  - Sends clip to Gemini VLM for detailed AI analysis
- Interactive video player with timeline
- Visual timeline markers showing detected incidents
- Click markers to view full Gemini analysis with random scores

## Prerequisites

1. Python 3.8 or higher
2. Trained DINO model checkpoint: `dino_classifier_89auc_v1_12.4.3:24.pt` (in root directory)
3. Google Gemini API key (for video analysis)
4. PyTorch with appropriate backend (CPU, CUDA, or MPS for Apple Silicon)

## Installation

1. Install dependencies (from root directory):
```bash
pip install -r requirements.txt
```

Or if you're already in the web_app directory:
```bash
pip install -r ../requirements.txt
```

2. Set up environment variables:
   - Copy `.env.example` to `.env` in the root directory
   - Add your Google API key:
```
GOOGLE_API_KEY=your_google_api_key_here
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
2. **Analyze**: Once uploaded, click "Analyze Video" to start the analysis (this may take a while)
3. **View Results**:
   - Left panel shows analysis summary (duration, # incidents detected)
   - Right panel lists all detected incidents with previews
   - Teal markers on timeline indicate incident locations
4. **Interact**: Click on any marker or incident to view full Gemini analysis

## How It Works

1. **Frame Extraction**: For every second of the video, extracts a single frame
2. **DINO Analysis**: Runs each frame through the DINO classifier (`predict_image()` from `models.py`)
   - Returns incident probability score (0.0-1.0)
   - Uses trained DINOv3 model with dual-path binary classifier
3. **Threshold Detection**: If DINO score > 0.8, flags as potential incident
4. **Clip Extraction**: For flagged incidents:
   - Extracts 15-second clip (10s before + 5s after trigger point)
   - Saves clip temporarily to `web_app/clips/`
5. **Gemini Analysis**: Uploads clip to Google Gemini API (`predict_video()` from `models.py`)
6. **Results**: Returns detailed analysis with timestamps, DINO scores, and Gemini insights

## API Endpoints

- `GET /` - Web interface
- `POST /upload` - Upload video file
- `GET /video/{filename}` - Stream uploaded video
- `POST /analyze/{filename}` - Analyze video and return incidents

## Notes

- Only one video can be analyzed at a time (previous uploads are overwritten)
- Video files are stored temporarily in `web_app/uploads/`
- Extracted frames are stored in `web_app/frames/` and cleared on each analysis
- Extracted clips are stored in `web_app/clips/` and cleared on each analysis
- Requires trained DINO model checkpoint: `dino_classifier_89auc_v1_12.4.3:24.pt` in root directory
- Uses `models.py` from root directory for predictions
- Gemini analysis requires internet connection and API key
- Analysis time depends on video length and number of incidents detected
- DINO model runs on available hardware (MPS for Apple Silicon, CPU otherwise)

## Troubleshooting

**DINO model not loading:**
- Ensure `dino_classifier_89auc_v1_12.4.3:24.pt` is in the root directory
- Check PyTorch installation: `python -c "import torch; print(torch.__version__)"`
- Verify that `models.py` can be imported from the web app
- Check for DINOv3 model download (happens on first run via torch.hub)

**API key not working:**
- Verify `GOOGLE_API_KEY` is set correctly in `.env` file
- Ensure the `.env` file is in the root directory of the project
- Check that you have a valid Google API key with Gemini access

**Gemini analysis failing:**
- Check internet connection
- Ensure you have API quota remaining
- Verify the API key has permission to use Gemini models
- Allow 5-second delay for Gemini file upload processing

**Video not playing:**
- Try converting video to MP4 format
- Ensure video codec is supported by browser (H.264 recommended)
- Check that the video file is not corrupted

**Analysis taking too long:**
- DINO runs on every frame (1 per second), so longer videos take more time
- Each incident triggers a Gemini analysis which adds ~10-15 seconds
- Consider reducing video length or adjusting detection threshold
