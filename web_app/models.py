import torch
import torch.nn as nn
from torchvision import transforms
import cv2
from PIL import Image
import numpy as np
from typing import List, Dict, Any
import os
from google import genai

class DinoBinaryClassifier(nn.Module):
    def __init__(self, backbone, feature_dim=384):
        super().__init__()
        self.backbone = backbone
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 1)
        )

    def forward(self, x):
        with torch.no_grad():
            features = self.backbone(x)
        if isinstance(features, dict):
            features = features['x_norm_patchtokens'].mean(dim=1)
        elif len(features.shape) == 3:
            features = features.mean(dim=1)
        logits = self.classifier(features)
        return logits

class DinoAnalyzer:
    def __init__(self, model_path="dino_classifier.pt", frame_interval=0.5, threshold=0.5):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.frame_interval = frame_interval
        self.threshold = threshold

        print(f"Loading DINO model on {self.device}...")

        # Load DINOv3 from local directory
        local_dinov3_path = "dinov3"
        if not os.path.exists(local_dinov3_path):
            raise FileNotFoundError(
                f"DINOv3 repository not found at '{local_dinov3_path}'. "
                f"Please clone it first:\n"
                f"git clone https://github.com/facebookresearch/dinov2.git dinov3"
            )

        print(f"Loading DINOv3 from local directory: {local_dinov3_path}")
        backbone = torch.hub.load(
            repo_or_dir=local_dinov3_path,
            model="dinov2_vits14",
            source="local",
            pretrained=True
        )
        backbone.eval()
        backbone.to(self.device)

        self.model = DinoBinaryClassifier(backbone, feature_dim=384)

        if os.path.exists(model_path):
            print(f"Loading classifier weights from {model_path}...")
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
        else:
            print(f"Warning: Model weights not found at {model_path}, using untrained classifier")

        self.model.eval()
        self.model.to(self.device)

        self.transform = transforms.Compose([
            transforms.Resize((518, 518)),  # DINOv2 input size
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def extract_frames(self, video_path: str) -> List[tuple]:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval_count = int(fps * self.frame_interval)

        frames = []
        timestamps = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval_count == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                timestamp = frame_idx / fps
                frames.append(pil_image)
                timestamps.append(timestamp)

            frame_idx += 1

        cap.release()
        return list(zip(frames, timestamps))

    def analyze(self, video_path: str) -> Dict[str, Any]:
        print(f"Extracting frames from {video_path}...")
        frame_data = self.extract_frames(video_path)

        if not frame_data:
            return {
                "incidents": [],
                "total_frames": 0,
                "message": "No frames extracted from video"
            }

        print(f"Analyzing {len(frame_data)} frames...")
        incidents = []

        with torch.no_grad():
            for frame, timestamp in frame_data:
                tensor = self.transform(frame).unsqueeze(0).to(self.device)
                logits = self.model(tensor)
                prob = torch.sigmoid(logits).item()

                if prob > self.threshold:
                    incidents.append({
                        "timestamp": round(timestamp, 2),
                        "confidence": round(prob, 4),
                        "type": "incident_detected"
                    })

        return {
            "incidents": incidents,
            "total_frames": len(frame_data),
            "frame_interval": self.frame_interval,
            "threshold": self.threshold,
            "message": f"Found {len(incidents)} potential incidents"
        }

class GeminiAnalyzer:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    def analyze(self, video_path: str) -> Dict[str, Any]:
        if not self.client:
            return {
                "analysis": "Gemini API key not configured. Please set GEMINI_API_KEY environment variable.",
                "incidents": [],
                "error": True
            }

        try:
            print(f"Uploading video to Gemini: {video_path}")
            myfile = self.client.files.upload(file=video_path)

            print("Generating analysis with Gemini...")
            response = self.client.models.generate_content(
                model="gemini-3-pro-preview",
                contents=[
                    myfile,
                    "Analyze this driving video step by step. Provide timestamps for key events. Identify any bad driving behaviors such as: unsafe lane changes, following too closely, failure to yield, distracted driving, speeding, or any traffic violations. Be specific about what happens and when."
                ]
            )

            analysis_text = response.text

            incidents = self._parse_incidents(analysis_text)

            return {
                "analysis": analysis_text,
                "incidents": incidents,
                "error": False
            }

        except Exception as e:
            return {
                "analysis": f"Error during Gemini analysis: {str(e)}",
                "incidents": [],
                "error": True
            }

    def _parse_incidents(self, text: str) -> List[Dict[str, Any]]:
        incidents = []
        lines = text.split('\n')

        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['unsafe', 'bad', 'violation', 'dangerous', 'collision', 'crash', 'cut off', 'too close']):
                timestamp = self._extract_timestamp(line)
                incidents.append({
                    "timestamp": timestamp,
                    "description": line.strip(),
                    "type": "gemini_flagged"
                })

        return incidents

    def _extract_timestamp(self, text: str) -> float:
        import re
        patterns = [
            r'(\d+):(\d+)',
            r'(\d+)s',
            r'at\s+(\d+)',
            r'(\d+)\s+second'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if ':' in pattern:
                    minutes = int(match.group(1))
                    seconds = int(match.group(2))
                    return minutes * 60 + seconds
                else:
                    return float(match.group(1))

        return 0.0
