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

# ReAct loop
MAX_REACT_ITERATIONS = int(os.getenv("MAX_REACT_ITERATIONS", "5"))
REACT_MAX_TOKENS = int(os.getenv("REACT_MAX_TOKENS", "800"))
REACT_REQUEST_TIMEOUT = int(os.getenv("REACT_REQUEST_TIMEOUT", "120"))

# Hafıza (memory) katmanı
DB_PATH = Path(os.getenv("DB_PATH", str(OUTPUT_DIR / "memory.db")))
OLAY_TIPLERI = [
    "kkd_ihlali", "dusme", "arac_kazasi", "tehlikeli_yakinlik",
    "bolge_ihlali", "yetkisiz_giris", "personel_toplanmasi", "diger"
]

# N6: head/helmet eslestirme esikleri (core.detection.baret_durumu icin)
# Kalibrasyon gerekebilir - cok yuksek IoU esigi baretleri kacirabilir.
HEAD_HELMET_IOU_THRESHOLD = float(os.getenv("HEAD_HELMET_IOU_THRESHOLD", "0.1"))
HEAD_HELMET_TOP_REGION_RATIO = float(os.getenv("HEAD_HELMET_TOP_REGION_RATIO", "0.6"))

# YOLO tespit modelleri (core.detection.detect_frame icin): {isim: agirlik yolu}.
# Yeni bir model egitimi bittiginde (ör. yaya_yolu) buraya tek satir eklemek
# yeterli; detect_frame() ve onu cagiran kod degismeden devreye girer.
YOLO_MODEL_PATHS: dict[str, Path] = {
    "sh17": BASE_DIR / "model" / "sh17.pt",         # KKD: baret, yelek, eldiven vb. (17 sinif)
    "forklift": BASE_DIR / "model" / "forklift.pt",  # tek sinif: forklift
}

# Model basina guven esigi. SH17 genis ve kucuk nesneler (el, kulak vb.)
# icerdigi icin dusuk esikte kalmali; forklift modeli tek sinif + yuksek
# precision'a (0.995) sahip oldugu icin daha yuksek esik yeterli/tercih edilir.
YOLO_MODEL_CONF: dict[str, float] = {
    "sh17": float(os.getenv("SH17_CONF_THRESHOLD", "0.25")),
    "forklift": float(os.getenv("FORKLIFT_CONF_THRESHOLD", "0.40")),
}
