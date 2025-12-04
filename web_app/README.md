# Driving Analysis Web App

A web application for analyzing driving videos using Google Gemini VLM to detect and analyze driving incidents.

## Features

- Upload driving videos (MP4, AVI, MOV formats)
- Random sampling analysis: Samples every second of the video
- When a detection threshold is exceeded (score > 0.8):
  - Extracts a 15-second clip (10 seconds before + 5 seconds after)
  - Sends clip to Gemini for detailed AI analysis
- Interactive video player with timeline
- Visual timeline markers showing detected incidents
- Click markers to view full Gemini analysis with timestamps

## Prerequisites

1. Python 3.8 or higher
2. Google Gemini API key (for video analysis)

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

1. **Random Sampling**: The backend samples the video every 1 second
2. **Threshold Detection**: For each second, generates a random score (0.00-1.00)
3. **Clip Extraction**: If score > 0.8:
   - Extracts 15-second clip (10s before + 5s after trigger point)
   - Saves clip temporarily to `web_app/clips/`
4. **Gemini Analysis**: Uploads clip to Google Gemini API
5. **Results**: Returns detailed analysis with timestamps and detected behaviors

## API Endpoints

- `GET /` - Web interface
- `POST /upload` - Upload video file
- `GET /video/{filename}` - Stream uploaded video
- `POST /analyze/{filename}` - Analyze video and return incidents

## Notes

- Only one video can be analyzed at a time (previous uploads are overwritten)
- Video files are stored temporarily in `web_app/uploads/`
- Extracted clips are stored in `web_app/clips/` and cleared on each analysis
- Gemini analysis requires internet connection and API key
- Analysis time depends on video length and number of incidents detected

## Troubleshooting

**API key not working:**
- Verify `GOOGLE_API_KEY` is set correctly in `.env` file
- Ensure the `.env` file is in the root directory of the project
- Check that you have a valid Google API key with Gemini access

**Gemini analysis failing:**
- Check internet connection
- Ensure you have API quota remaining
- Verify the API key has permission to use Gemini models

**Video not playing:**
- Try converting video to MP4 format
- Ensure video codec is supported by browser (H.264 recommended)
- Check that the video file is not corrupted
