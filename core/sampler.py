import os
import re
import subprocess
import time
import base64

import cv2
import numpy as np
import streamlit as st

import config

OUTPUT_DIR = str(config.OUTPUT_DIR)

# ============================================================
# YARDIMCI FONKSİYONLAR & ADAPTİF KARE ÖRNEKLEME
# ============================================================
def parse_timestamp_to_seconds(ts_str):
    if not ts_str:
        return None
    cleaned = re.sub(r'[^\d:]', '', str(ts_str)).strip()
    parts = cleaned.split(':')
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 1:
            return int(parts[0])
    except Exception:
        return None
    return None

def find_best_matching_frame(t_val, frames_cache):
    if not t_val or not frames_cache:
        return None
    target_sec = parse_timestamp_to_seconds(t_val)
    if target_sec is None:
        return next((f for f in frames_cache if f.get("timestamp") == t_val), None)

    # Zaman farkı en az (matematiksel olarak en yakın) kareyi bul
    return min(frames_cache, key=lambda f: abs(f.get("sec_elapsed", 0.0) - target_sec))

def save_uploaded_file(uploaded_file):
    try:
        file_path = os.path.join(OUTPUT_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    except Exception as e:
        st.error(f"Dosya kaydedilirken hata oluştu: {e}")
        return None

def cut_video(source_path, start_sec, end_sec, output_path):
    t0 = time.time()
    duration = end_sec - start_sec
    cmd = [
        config.FFMPEG_BINARY, "-y",
        "-ss", str(start_sec),
        "-i", source_path,
        "-t", str(duration),
        "-c", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    t1 = time.time()
    if result.returncode != 0:
        st.error(f"Video kesme hatası: {result.stderr}")
        return False, 0.0
    return True, (t1 - t0)

def extract_frames_adaptive(video_path, fps, sampling_mode="Sabit FPS", start_total_sec=0, max_dim=640):
    """
    Savant İlhamlı Adaptif / Dinamik Kare Örnekleyici.
    - Sabit FPS: Belirtilen aralıklarda kare alır.
    - Adaptif (Sahne Duyarlı): Hareket algılandığında kare örnekleme sıklığını dinamik artırır.
    """
    t0 = time.time()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0, [], 0.0

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps == 0: video_fps = 30
    base_frame_interval = max(1, int(video_fps / fps))

    frame_count = 0
    saved_count = 0
    extracted_frames = []

    prev_gray = None
    motion_threshold = 12.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        should_extract = False

        # Algılama Modu Kararı
        if sampling_mode == "Adaptif (Sahne Duyarlı - Savant Style)":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if prev_gray is not None:
                frame_diff = cv2.absdiff(prev_gray, gray)
                motion_score = np.mean(frame_diff)

                # Hareket yüksekse sık kare al, düşükse seyrek
                if motion_score > motion_threshold:
                    adaptive_interval = max(1, int(base_frame_interval / 2))
                else:
                    adaptive_interval = base_frame_interval * 2
            else:
                adaptive_interval = base_frame_interval

            prev_gray = gray
            if frame_count % adaptive_interval == 0:
                should_extract = True
        else:
            if frame_count % base_frame_interval == 0:
                should_extract = True

        if should_extract:
            # Aspect Ratio Koruyarak Resize (Token Tasarrufu)
            if max_dim > 0:
                h, w = frame.shape[:2]
                if max(h, w) > max_dim:
                    scale = max_dim / float(max(h, w))
                    new_w, new_h = int(w * scale), int(h * scale)
                    frame_to_encode = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                else:
                    frame_to_encode = frame
            else:
                frame_to_encode = frame

            # RAM seviyesinde JPEG ve Base64
            success, buffer = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if success:
                b64_str = base64.b64encode(buffer).decode('utf-8')
                sec_elapsed = start_total_sec + (float(frame_count) / float(video_fps))
                m, s = divmod(int(sec_elapsed), 60)
                timestamp_str = f"{m:02d}:{s:02d}"

                extracted_frames.append({
                    "b64": b64_str,
                    "timestamp": timestamp_str,
                    "sec_elapsed": sec_elapsed,
                    "frame_idx": saved_count
                })
                saved_count += 1

        frame_count += 1

    cap.release()
    t1 = time.time()
    return saved_count, extracted_frames, (t1 - t0)
