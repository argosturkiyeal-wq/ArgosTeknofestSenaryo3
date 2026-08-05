import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Filesystem paths
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "outputs")))
FRAMES_DIR = Path(os.getenv("FRAMES_DIR", str(OUTPUT_DIR / "frames")))
VIDEO_OUTPUT_PATH = Path(os.getenv("VIDEO_OUTPUT_PATH", str(OUTPUT_DIR / "video_kesit.mp4")))
JSON_OUTPUT_PATH = Path(os.getenv("JSON_OUTPUT_PATH", str(OUTPUT_DIR / "analiz_sonucu.json")))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "Qwen3VL-8B-Instruct-Q4_K_M.gguf")))
MMPROJ_PATH = Path(os.getenv("MMPROJ_PATH", str(BASE_DIR / "models" / "mmproj-Qwen3VL-8B-Instruct-F16.gguf")))

# External tools
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")

# llama-server
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8080/v1/chat/completions")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))
AGGREGATOR_REQUEST_TIMEOUT = int(os.getenv("AGGREGATOR_REQUEST_TIMEOUT", "90"))

# Model / generation
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3vl")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
VISION_MAX_TOKENS = int(os.getenv("VISION_MAX_TOKENS", "1500"))
AGGREGATOR_MAX_TOKENS = int(os.getenv("AGGREGATOR_MAX_TOKENS", "1200"))

# Frame sampling defaults
DEFAULT_FPS = int(os.getenv("DEFAULT_FPS", "2"))
DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "10"))

# ReAct loop (wired up in the tool-calling work)
MAX_REACT_ITERATIONS = int(os.getenv("MAX_REACT_ITERATIONS", "5"))
