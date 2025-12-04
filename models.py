import os
import json
import tempfile
import subprocess
from itertools import islice

import pandas as pd
from huggingface_hub import list_repo_files, hf_hub_download

from pathlib import Path
import tqdm
import os
import urllib
from PIL import Image

import torch
import torchvision.transforms.functional as TF
import numpy as np
import os
import urllib
from PIL import Image

import torch
import torchvision.transforms.functional as TF
import numpy as np

print("PyTorch version:", torch.__version__)

# --- device selection for Mac ---
if torch.backends.mps.is_available():
    DEVICE = "mps"
    print("Using Apple Silicon GPU (MPS).")
else:
    DEVICE = "cpu"
    print("Using CPU.")



PATCH_SIZE = 16
IMAGE_SIZE = 768

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

def resize_transform(
    image: Image.Image,
    image_size: int = IMAGE_SIZE,
    patch_size: int = PATCH_SIZE,
):
    w, h = image.size
    h_patches = image_size // patch_size
    w_patches = int((w * image_size) / (h * patch_size))
    return TF.to_tensor(
        TF.resize(image, (h_patches * patch_size, w_patches * patch_size))
    )

def normalize_image(t: torch.Tensor) -> torch.Tensor:
    return TF.normalize(t, mean=IMAGENET_MEAN, std=IMAGENET_STD)

DINOV3_REPO = "facebookresearch/dinov3"
#MODEL_NAME = "dinov3_vith16plus"  # HP model
MODEL_NAME = "dinov3_vits16plus"


# Optional: allow user to override with a local clone
DINOV3_LOCATION = os.getenv("DINOV3_LOCATION", DINOV3_REPO)
SOURCE = "local" if DINOV3_LOCATION != DINOV3_REPO else "github"

print("Loading model:", MODEL_NAME)
print("From:", DINOV3_LOCATION, "| source:", SOURCE)

model = torch.hub.load(
    repo_or_dir=DINOV3_LOCATION,
    model=MODEL_NAME,
    source=SOURCE,
)

model = model.to(DEVICE).eval()
print("Model loaded on:", DEVICE)

MODEL_TO_NUM_LAYERS = {
    "dinov3_vits16": 12,
    "dinov3_vits16plus": 12,
    "dinov3_vitb16": 12,
    "dinov3_vitl16": 24,
    "dinov3_vith16plus": 32,
    "dinov3_vit7b16": 40,
}

N_LAYERS = MODEL_TO_NUM_LAYERS[MODEL_NAME]

from torch.utils.data import Dataset, DataLoader, Sampler
from PIL import Image


def frame_to_tensor(img: Image.Image) -> torch.Tensor:
    # Resize to multiples of patch size and normalize with ImageNet stats
    tensor_img = resize_transform(img, image_size=IMAGE_SIZE, patch_size=PATCH_SIZE)
    return normalize_image(tensor_img)

import torch.nn as nn

# Infer feature dimension from the loaded DINO backbone
FEATURE_DIM = getattr(model, "num_features", getattr(model, "embed_dim", None))
if FEATURE_DIM is None:
    raise ValueError("Could not infer feature dimension from the DINO model.")

import torch
import torch.nn as nn

class AttnPool1D(nn.Module):
    """
    Learned attention pooling over a sequence of tokens.
    Uses a single learned query token to attend over patch tokens.
    """
    def __init__(self, dim: int, num_heads: int = 4):
        super().__init__()
        self.query = nn.Parameter(torch.randn(1, 1, dim))   # (1, 1, D)
        self.attn = nn.MultiheadAttention(
            embed_dim=dim,
            num_heads=num_heads,
            batch_first=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, N, D) patch tokens
        returns: (B, D) pooled feature
        """
        B, N, D = x.shape
        q = self.query.expand(B, -1, -1)    # (B, 1, D)
        pooled, _ = self.attn(q, x, x)      # (B, 1, D)
        return pooled.squeeze(1)            # (B, D)


class DinoDualPathBinaryClassifier(nn.Module):
    """
    - Frozen DINOv3 backbone
    - Path 1: deeper MLP on CLS token (global path)
    - Path 2: attention pooling over patch tokens + MLP (local path)
    - Final logit = cls_logit + patch_logit
    """
    def __init__(
        self,
        backbone,
        feature_dim: int,
        n_layers: int,
        layers=None,
        dropout: float = 0,
        patch_heads: int = 4,
    ):
        super().__init__()
        self.backbone = backbone
        self.layers = layers or [n_layers - 1]  # default: last layer

        # freeze DINO backbone
        for p in self.backbone.parameters():
            p.requires_grad = False

        # ---- CLS path: deeper MLP ----
        self.cls_head = nn.Sequential(
            nn.LayerNorm(feature_dim),
            nn.Linear(feature_dim, feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(feature_dim, feature_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(feature_dim // 2, feature_dim // 4),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(feature_dim // 4, 1),   # scalar logit from CLS path
        )

        # ---- Patch path: attention pooling + MLP ----
        self.patch_pool = AttnPool1D(feature_dim, num_heads=patch_heads)

        self.patch_head = nn.Sequential(
            nn.LayerNorm(feature_dim),
            nn.Linear(feature_dim, feature_dim),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(feature_dim, feature_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(feature_dim // 2, feature_dim // 4),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(feature_dim // 4, 1),   # scalar logit from patch path
        )

    def forward(self, x: torch.Tensor):
        """
        x: (B, 3, H, W) preprocessed frames (already resized & normalized)
        """
        feats = self.backbone.get_intermediate_layers(
            x,
            n=self.layers,
            reshape=False,
            norm=True,
        )
        tokens = feats[-1]                 # (B, T, D) where T = 1 + extra + patches
        cls_tok = tokens[:, 0, :]         # (B, D)
        patch_tok = tokens[:, 1:, :]      # (B, T-1, D) (registers+patches, that's fine)

        # CLS path
        cls_logit = self.cls_head(cls_tok).squeeze(-1)        # (B,)

        # Patch path: attention pooling over tokens
        patch_pooled = self.patch_pool(patch_tok)             # (B, D)
        patch_logit = self.patch_head(patch_pooled).squeeze(-1)  # (B,)

        # Combine the two paths at the final node
        logit = cls_logit + patch_logit                       # (B,)

        return logit, cls_logit, patch_logit, cls_tok, patch_tok


classifier = DinoDualPathBinaryClassifier(backbone=model, feature_dim=FEATURE_DIM, n_layers=N_LAYERS).to(DEVICE)
criterion = nn.BCEWithLogitsLoss()
optimizer = torch.optim.Adam(classifier.parameters(), lr=3e-4)

checkpoint = torch.load("dino_classifier_89auc_v1_12.4.3:24.pt", map_location=DEVICE)
classifier.load_state_dict(checkpoint["model_state"])
optimizer.load_state_dict(checkpoint["optimizer_state"])
classifier.to(DEVICE).eval()  # set eval as needed
print("Model and optimizer restored")

from PIL import Image
import torch

def predict_image(path: str):
    img = Image.open(path).convert("RGB")
    x = frame_to_tensor(img).unsqueeze(0).to(DEVICE)  # (1, 3, H, W)

    with torch.no_grad():
        logits, *_ = classifier(x)
        prob = torch.sigmoid(logits)[0].item()

    return prob  # probability in [0,1]; logit is logits[0].item() if you need it


from google import genai
from time import sleep
client = genai.Client()

def predict_video(path: str):
    myfile = client.files.upload(file=path)
    sleep(5)
    response = client.models.generate_content(
        model="gemini-3-pro-preview", contents=[myfile, "Explain what bad driving is happening in the video, if any."]
    )
    return(response.text)