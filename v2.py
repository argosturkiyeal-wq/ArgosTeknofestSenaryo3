import streamlit as st
import os
import subprocess
import time
import cv2
import shutil
import json
import re
import base64
import logging
import requests
import numpy as np
from datetime import datetime

import config

logger = logging.getLogger(__name__)

# ============================================================
# AYARLAR VE SABİTLER
# ============================================================
KOD_DIR = str(config.KOD_DIR)
FRAMES_DIR = str(config.FRAMES_DIR)
VIDEO_OUTPUT_PATH = str(config.VIDEO_OUTPUT_PATH)
JSON_OUTPUT_PATH = str(config.JSON_OUTPUT_PATH)

LLAMA_SERVER_URL = config.LLAMA_SERVER_URL

# Model Konfigürasyonları
MODELS = {
    "8B": {
        "model_path": str(config.MODEL_PATH),
        "mmproj_path": str(config.MMPROJ_PATH),
        "ngl": "28",
        "ctx": "24576",
        "ub": "4096"
    }
}

DEFAULT_TEKNOFEST_PROMPT = """Sen bir Savunma Sanayii ve Saha Operasyonu Güvenlik Karar Destek Ajanısın.
Verilen video karelerini zamansal akış içinde analiz et. Her kareye karşılık gelen zaman damgası [Zaman Damgası: MM:SS] şeklinde etiketlenmiştir.

Kullanabileceğin Otonom Araçlar (Tools):
1. mock_saglik_ekibi_cagir(detay): Yaralanma, düşme veya hareketsiz kişi durumlarında tetikle.
2. mock_guvenlik_alert_ver(detay): Güvenlik ihlali, tehlikeli bölgeye yaklaşma veya riskli durumlarda tetikle.
3. mock_olay_kaydi_olustur(detay): Tespit edilen her kaza, olay veya kural ihlali için tetikle.

Çıktıyı SADECE ve KESİNLİKLE aşağıdaki JSON formatında Türkçe olarak üret. Başka hiçbir açıklama metni yazma:

{
  "summary": "Videodaki genel durumun kısa ve net Türkçe özeti",
  "events": [
    {"time": "00:15", "event": "Tespit edilen 1. olay veya tehlike"},
    {"time": "00:20", "event": "Tespit edilen 2. olay veya tehlike"}
  ],
  "risk": "Düşük / Orta / Yüksek / Kritik",
  "actions": [
    "Operatör için 1. aksiyon önerisi",
    "Operatör için 2. aksiyon önerisi"
  ],
  "triggered_tools": [
    {
      "tool_name": "mock_saglik_ekibi_cagir",
      "args": {"detay": "00:20'de tespit edilen hareketsiz kişi için acil çağrı"}
    },
    {
      "tool_name": "mock_olay_kaydi_olustur",
      "args": {"detay": "Kaza ve yaralanma olay kaydı oluşturuldu"}
    }
  ]
}"""

# Klasörleri oluştur
os.makedirs(KOD_DIR, exist_ok=True)
os.makedirs(FRAMES_DIR, exist_ok=True)

st.set_page_config(layout="wide", page_title="TEKNOFEST v2 (Savant Mimarı Entegreli) - Video Analiz & Karar Destek Ajanı", page_icon="⚡")

# Session State Başlatma
if 'analysis_completed' not in st.session_state:
    st.session_state['analysis_completed'] = False
if 'video_ready' not in st.session_state:
    st.session_state['video_ready'] = False
if 'model_result' not in st.session_state:
    st.session_state['model_result'] = ""
if 'metrics' not in st.session_state:
    st.session_state['metrics'] = {}
if 'parsed_json' not in st.session_state:
    st.session_state['parsed_json'] = None
if 'action_logs' not in st.session_state:
    st.session_state['action_logs'] = []
if 'saved_json_path' not in st.session_state:
    st.session_state['saved_json_path'] = ""
if 'extracted_frames_cache' not in st.session_state:
    st.session_state['extracted_frames_cache'] = []

# ============================================================
# SAVANT TİPİ EVENT BUS & MOCK TOOLS
# ============================================================
def publish_event_to_bus(topic, payload):
    """Savant tarzı çoklu dış sistem yayıncısı (Event Publisher Mock)."""
    ts = datetime.now().strftime('%H:%M:%S')
    log = f"[{ts}] 📡 [EVENT BUS - {topic}] Payload: {json.dumps(payload, ensure_ascii=False)}"
    st.session_state['action_logs'].append(log)
    return log

def mock_saglik_ekibi_cagir(detay=""):
    log = f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 MOCK SAĞLIK EKİBİ ÇAĞRILDI: {detay}"
    st.session_state['action_logs'].append(log)
    publish_event_to_bus("DISPATCH_HEALTH_TEAM", {"detay": detay, "priority": "HIGH"})
    return log

def mock_guvenlik_alert_ver(detay=""):
    log = f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ MOCK GÜVENLİK BİLDİRİMİ GÖNDERİLDİ: {detay}"
    st.session_state['action_logs'].append(log)
    publish_event_to_bus("SECURITY_ALERT_BROADCAST", {"detay": detay, "level": "WARNING"})
    return log

def mock_olay_kaydi_olustur(detay=""):
    log = f"[{datetime.now().strftime('%H:%M:%S')}] 📝 MOCK OLAY KAZA KAYDI OLUŞTURULDU: {detay}"
    st.session_state['action_logs'].append(log)
    publish_event_to_bus("INCIDENT_LOG_CREATED", {"detay": detay, "status": "LOGGED"})
    return log

TOOLS = {
    "mock_saglik_ekibi_cagir": {
        "func": mock_saglik_ekibi_cagir,
        "description": "Yaralanma veya acil medikal durumlarda sağlık ekibini çağırır.",
        "name_tr": "🚨 Sağlık Ekibini Çağır"
    },
    "mock_guvenlik_alert_ver": {
        "func": mock_guvenlik_alert_ver,
        "description": "Güvenlik ihlali veya tehlikelerde güvenlik birimini uyarır.",
        "name_tr": "🛡️ Güvenliği Uyar"
    },
    "mock_olay_kaydi_olustur": {
        "func": mock_olay_kaydi_olustur,
        "description": "Olay/kaza kaydı oluşturur.",
        "name_tr": "📝 Olayı Kaydet"
    }
}

def execute_agent_tools(parsed_json, auto_execute=True):
    if not parsed_json or not isinstance(parsed_json, dict):
        return []
    
    triggered_tools = parsed_json.get("triggered_tools", [])
    executed_results = []
    
    if isinstance(triggered_tools, list):
        for tool_call in triggered_tools:
            if isinstance(tool_call, dict):
                tool_name = tool_call.get("tool_name")
                args = tool_call.get("args", {})
                detay = args.get("detay", "Otomatik ajan tetiklemesi") if isinstance(args, dict) else str(args)
                
                if tool_name in TOOLS:
                    if auto_execute:
                        log = TOOLS[tool_name]["func"](detay)
                        executed_results.append({"status": "executed", "name": tool_name, "log": log, "detay": detay})
                    else:
                        executed_results.append({"status": "pending", "name": tool_name, "detay": detay})
    return executed_results

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
        file_path = os.path.join(KOD_DIR, uploaded_file.name)
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

def parse_json_response(raw_text):
    if not raw_text:
        return None

    last_exc = None

    try:
        return json.loads(raw_text)
    except Exception as e:
        last_exc = e

    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception as e:
            last_exc = e

    bracket_match = re.search(r'(\{.*?\})', raw_text, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1))
        except Exception as e:
            last_exc = e

    logger.error("JSON parse failed: %s | raw response head: %r", last_exc, raw_text[:200])
    return {"status": "failed", "error": str(last_exc)}

def save_json_to_file(parsed_data, raw_text, telemetry_metrics):
    try:
        data_to_save = parsed_data if (parsed_data and isinstance(parsed_data, dict)) else {"summary": "Ayrıştırılamayan ham metin", "raw_output": raw_text}
        data_to_save["telemetry_metrics"] = telemetry_metrics
        with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        return JSON_OUTPUT_PATH
    except Exception as e:
        st.error(f"JSON kaydedilemedi: {e}")
        return ""

def check_llama_server_health(server_url=LLAMA_SERVER_URL):
    base_url = server_url.rsplit("/v1/", 1)[0]
    health_endpoint = f"{base_url}/health"
    models_endpoint = f"{base_url}/v1/models"
    
    start_time = time.time()
    try:
        res = requests.get(health_endpoint, timeout=2.0)
        latency_ms = round((time.time() - start_time) * 1000, 1)
        if res.status_code == 200:
            return {"online": True, "status": "ok", "latency_ms": latency_ms, "endpoint": health_endpoint}
    except Exception:
        pass

    try:
        res = requests.get(models_endpoint, timeout=2.0)
        latency_ms = round((time.time() - start_time) * 1000, 1)
        if res.status_code == 200:
            return {"online": True, "status": "ok", "latency_ms": latency_ms, "endpoint": models_endpoint}
    except Exception as e:
        return {"online": False, "status": "offline", "error": str(e), "latency_ms": 0}

    return {"online": False, "status": "error", "error": "Sunucu yanıt vermedi.", "latency_ms": 0}

def run_analysis_generator(image_items, prompt, model_config):
    content = [{"type": "text", "text": prompt}]
    for item in image_items:
        b64_img = item.get("b64", "")
        ts = item.get("timestamp", "00:00")
            
        content.append({
            "type": "text",
            "text": f"\n[Zaman Damgası: {ts}] Kare Görseli:"
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
        })
    
    payload = {
        "model": config.MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "temperature": config.TEMPERATURE,
        "max_tokens": config.VISION_MAX_TOKENS,
        "repeat_penalty": 1.2
    }

    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            yield text
        else:
            yield f"⚠️ Sunucu Hatası (Status {response.status_code}): {response.text}"
    except Exception as e:
        yield f"⚠️ Sunucuya bağlanılamadı ({LLAMA_SERVER_URL}). Hata: {e}"

def run_aggregator_agent(chunk_observations, user_prompt, model_config):
    obs_text = "\n\n".join([
        f"--- Parça {idx+1} Gözlemleri ---\n{res}"
        for idx, res in enumerate(chunk_observations) if res and res.strip()
    ])
    
    aggregator_prompt = f"""Sen TEKNOFEST Savunma Sanayii ve Saha Operasyonu Güvenlik Karar Destek Ajanısın.
Aşağıda bir videonun tüm zaman parçalarından elde edilen görsel analiz gözlemleri bulunmaktadır:

=== BÜTÜNLEŞİK SAHA GÖZLEMLERİ ===
{obs_text}
==================================

Kullanıcı İsteği / Sorusu: "{user_prompt}"

Kullanabileceğin Otonom Araçlar (Tools):
1. mock_saglik_ekibi_cagir(detay): Yaralanma, düşme veya hareketsiz kişi durumlarında tetikle.
2. mock_guvenlik_alert_ver(detay): Güvenlik ihlali, tehlikeli bölgeye yaklaşma veya riskli durumlarda tetikle.
3. mock_olay_kaydi_olustur(detay): Tespit edilen her kaza, olay veya kural ihlali için tetikle.

Gözlemleri sentezle. Çıktıyı SADECE ve KESİNLİKLE aşağıdaki JSON formatında Türkçe olarak üret. Başka hiçbir açıklama metni yazma:

{{
  "summary": "Videodaki genel durumun kısa ve net Türkçe özeti",
  "events": [
    {{"time": "00:15", "event": "Tespit edilen 1. olay veya tehlike"}},
    {{"time": "00:20", "event": "Tespit edilen 2. olay veya tehlike"}}
  ],
  "risk": "Düşük / Orta / Yüksek / Kritik",
  "actions": [
    "Operatör için 1. aksiyon önerisi"
  ],
  "triggered_tools": [
    {{
      "tool_name": "mock_saglik_ekibi_cagir",
      "args": {{"detay": "00:20'de tespit edilen olay için acil çağrı"}}
    }}
  ]
}}"""

    payload = {
        "model": config.MODEL_NAME,
        "messages": [{"role": "user", "content": aggregator_prompt}],
        "temperature": config.TEMPERATURE,
        "max_tokens": config.AGGREGATOR_MAX_TOKENS,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=config.AGGREGATOR_REQUEST_TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            payload.pop("response_format", None)
            res2 = requests.post(LLAMA_SERVER_URL, json=payload, timeout=config.AGGREGATOR_REQUEST_TIMEOUT)
            if res2.status_code == 200:
                return res2.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass
        
    return obs_text

# ============================================================
# ARAYÜZ (TEKNOFEST SENARYO 3 & SAVANT MİMARİ ENTEGRASYONU)
# ============================================================
st.title("🛸 TEKNOFEST Yapay Zeka Dil Ajanları Yarışması - v2")
st.subheader("Senaryo 3: Video Analiz & Karar Destek Ajanı (Savant Mimari Entegreli)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🖥️ Sunucu Sağlık Durumu (Health Check)")
    server_status = check_llama_server_health()
    
    if server_status["online"]:
        st.success(f"🟢 **Model Sunucusu Aktif**\n\n- Gecikme: `{server_status['latency_ms']} ms`")
    else:
        st.error("🔴 **Model Sunucusu Çevrimdışı!**")

    st.markdown("---")
    st.header("⚙️ Model ve Örnekleme Ayarları")
    selected_model = st.selectbox("Model", options=["8B"], index=0)
    
    sampling_mode = st.selectbox(
        "Kare Örnekleme Modu (Savant Style)",
        options=["Sabit FPS", "Adaptif (Sahne Duyarlı - Savant Style)"],
        index=0,
        help="Adaptif mod hareket algılandığında kare sıklığını artırarak hız ve doğruluk dengesi kurar."
    )

    agent_mode = st.radio(
        "Araç Tetikleme Modu",
        options=["🤖 Tam Otonom (Otomatik Araç Tetikleme)", "👨‍✈️ İnsan Denetimli (Operatör Onaylı)"],
        index=0
    )

    st.markdown("---")
    st.header("📹 Video Yükleme")
    uploaded_video = st.file_uploader("Bir operasyon/saha videosu seçin", type=["mp4", "mov", "avi", "webm"])
    
    source_video_path = save_uploaded_file(uploaded_video) if uploaded_video else None

    st.markdown("---")
    st.header("⏱️ Zaman ve Kare Ayarları")
    c1, c2, c3 = st.columns(3)
    start_h, start_m, start_s = c1.number_input("Baş. Saat", 0, 23, 0), c2.number_input("Baş. Dak", 0, 59, 0), c3.number_input("Baş. San", 0, 59, 0)
    
    c4, c5, c6 = st.columns(3)
    end_h, end_m, end_s = c4.number_input("Bit. Saat", 0, 23, 0), c5.number_input("Bit. Dak", 0, 59, 0), c6.number_input("Bit. San", 0, 59, 30)

    start_total_sec = start_h * 3600 + start_m * 60 + start_s
    end_total_sec = end_h * 3600 + end_m * 60 + end_s

    resolution_option = st.selectbox(
        "Görsel Çözünürlük",
        options=["🚀 Hızlı (640px)", "⚖️ Dengeli (896px)", "🔍 Orijinal"],
        index=0
    )
    max_dim_map = {"🚀 Hızlı (640px)": 640, "⚖️ Dengeli (896px)": 896, "🔍 Orijinal": 0}
    target_max_dim = max_dim_map[resolution_option]

    fps_val = st.number_input("FPS (Hedef Kare Sıklığı)", 1, 30, config.DEFAULT_FPS)
    chunk_size = st.number_input("Chunk Boyutu", 1, 100, config.DEFAULT_CHUNK_SIZE)
    
    prompt_val = st.text_area("İstem (System Prompt)", value=DEFAULT_TEKNOFEST_PROMPT, height=200)
    
    run_btn = st.button("🚀 Analiz ve Karar Destek Başlat", type="primary", use_container_width=True)

    if run_btn:
        st.session_state['analysis_completed'] = False
        st.session_state['video_ready'] = False
        st.session_state['model_result'] = ""
        st.session_state['parsed_json'] = None
        st.session_state['saved_json_path'] = ""
        st.session_state['action_logs'] = []
        st.session_state['metrics'] = {}
        st.session_state['extracted_frames_cache'] = []

def render_analysis_results(container, agent_mode):
    with container:
        parsed = st.session_state.get('parsed_json')
        saved_path = st.session_state.get('saved_json_path')
        metrics = st.session_state.get('metrics', {})
        frames_cache = st.session_state.get('extracted_frames_cache', [])
        
        # 📊 SAVANT TELEMETRİ METRİKLERİ PANOLARI
        if metrics:
            st.subheader("📊 Savant Tarzı Telemetri & Performans Analitiği (Metrics Breakdown)")
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Video Kesme", f"{metrics.get('cut_time', 0):.2f}s")
            m2.metric("Kare Çıkarma", f"{metrics.get('extract_time', 0):.2f}s")
            m3.metric("Görsel AI", f"{metrics.get('vision_time', 0):.2f}s")
            m4.metric("Sentez AI", f"{metrics.get('agg_time', 0):.2f}s")
            m5.metric("Toplam Uçtan Uca", f"{metrics.get('total_time', 0):.2f}s")
            m6.metric("İşlem Hızı", f"{metrics.get('throughput_fps', 0):.1f} FPS")
            st.markdown("---")

        parse_failed = isinstance(parsed, dict) and parsed.get("status") == "failed"

        if parse_failed:
            st.error(f"❌ Model çıktısı JSON olarak ayrıştırılamadı: {parsed.get('error', 'Bilinmeyen hata')}")
        elif saved_path:
            st.success(f"✅ Analiz tamamlandı! Çıktı kaydedildi: `{saved_path}`")
            try:
                with open(saved_path, "r", encoding="utf-8") as jf:
                    st.download_button("📥 JSON İndir", jf.read(), "analiz_sonucu_v2.json", "application/json")
            except Exception:
                pass

        if parsed and isinstance(parsed, dict) and not parse_failed:
            risk_val = parsed.get("risk", "Bilinmiyor")
            risk_color = "🔴" if any(r in str(risk_val).lower() for r in ["yüksek", "kritik", "danger"]) else ("🟡" if "orta" in str(risk_val).lower() else "🟢")
            
            c_left, c_right = st.columns([1, 2])
            c_left.metric("Risk Seviyesi", f"{risk_color} {risk_val}")
            c_right.info(f"**Özet:** {parsed.get('summary', 'Özet bilgisi üretilmedi.')}")

            st.markdown("---")
            st.subheader("⏱️ Zaman Damgalı Olaylar")
            events = parsed.get("events", [])
            if events and isinstance(events, list) and len(events) > 0:
                for ev in events:
                    t_val = ev.get("time", "--:--") if isinstance(ev, dict) else ""
                    e_val = ev.get("event", str(ev)) if isinstance(ev, dict) else str(ev)
                    st.markdown(f"- **`[{t_val}]`** {e_val}")
            else:
                st.write("Herhangi bir olay listelenmedi.")

            # 📸 KRİTİK AN GÖRSEL VURGULAYICI (THUMBNAIL HIGHLIGHTS)
            if events and frames_cache:
                st.markdown("---")
                st.subheader("📸 Tespit Edilen Kritik Olay Kareleri (Thumbnail Highlights)")
                highlight_cols = st.columns(min(4, max(1, len(events))))
                for idx, ev in enumerate(events):
                    if isinstance(ev, dict):
                        t_val = ev.get("time", "")
                        matched_frame = find_best_matching_frame(t_val, frames_cache)
                        col_target = highlight_cols[idx % len(highlight_cols)]
                        with col_target:
                            if matched_frame and matched_frame.get("b64"):
                                st.image(f"data:image/jpeg;base64,{matched_frame['b64']}", caption=f"[{t_val}] {ev.get('event', '')}", use_container_width=True)
                            else:
                                st.caption(f"[{t_val}] Görsel kare eşleşti")

            st.markdown("---")
            st.subheader("🤖 Ajan Tarafından Tetiklenen / Önerilen Araçlar (Tools)")
            triggered_tools = parsed.get("triggered_tools", [])
            if triggered_tools and isinstance(triggered_tools, list) and len(triggered_tools) > 0:
                for t_item in triggered_tools:
                    if isinstance(t_item, dict):
                        t_name = t_item.get("tool_name", "")
                        t_args = t_item.get("args", {})
                        detay_txt = t_args.get("detay", "") if isinstance(t_args, dict) else str(t_args)
                        tool_info = TOOLS.get(t_name, {"name_tr": t_name})
                        st.info(f"⚡ **Araç:** {tool_info['name_tr']} | **Gerekçe:** {detay_txt}")
                        
                        if "İnsan Denetimli" in agent_mode:
                            if st.button(f"✅ Onayla ve Çalıştır: {tool_info['name_tr']}", key=f"btn_{t_name}"):
                                if t_name in TOOLS:
                                    TOOLS[t_name]["func"](detay=detay_txt)
                                    st.success(f"{tool_info['name_tr']} çalıştırıldı!")
                                    st.rerun()
            else:
                st.write("Özel araç tetikleme ihtiyacı görülmedi.")

            st.markdown("---")
            st.subheader("🛡️ Operatör Aksiyon Önerileri & Manuel Butonlar")
            actions = parsed.get("actions", [])
            if actions:
                for act in actions:
                    st.warning(f"• **Aksiyon Önerisi:** {act}")
                
                b1, b2, b3 = st.columns(3)
                if b1.button("🚨 Sağlık Ekibini Çağır"):
                    mock_saglik_ekibi_cagir(parsed.get('summary', 'Acil durum'))
                    st.success("Sağlık ekibi bilgilendirildi!")
                if b2.button("🛡️ Güvenliği Uyar"):
                    mock_guvenlik_alert_ver(parsed.get('summary', 'Güvenlik ihlali'))
                    st.success("Güvenlik birimi uyarıldı!")
                if b3.button("📝 Olayı Kaydet"):
                    mock_olay_kaydi_olustur(parsed.get('summary', 'Olay kaydı'))
                    st.success("Olay günlüğe kaydedildi!")

        if st.session_state.get('action_logs'):
            st.markdown("---")
            st.subheader("📜 Event Bus & Tetiklenen Sistem İşlem Günlüğü (Logs)")
            for l in st.session_state['action_logs']:
                st.code(l, language="text")

# --- ANA EKRAN ---
col_video, col_result = st.columns([1.2, 1.8])
video_placeholder = col_video.empty()
result_container = col_result.container()

if run_btn:
    if not server_status["online"]:
        st.error("❌ Analiz başlatılamıyor: Model sunucusu çevrimdışı!")
    elif not source_video_path:
        st.error("Lütfen önce bir video dosyası seçin!")
    elif end_total_sec <= start_total_sec:
        st.error("Bitiş zamanı başlangıç zamanından büyük olmalıdır!")
    else:
        with result_container:
            total_start_time = time.time()
            
            # 1. Video Kırpma
            ok, cut_time = cut_video(source_video_path, start_total_sec, end_total_sec, VIDEO_OUTPUT_PATH)
            if ok:
                st.session_state['video_ready'] = True
                video_placeholder.subheader("🎥 İşlenen Video Kesiti")
                video_placeholder.video(VIDEO_OUTPUT_PATH)
                
                # 2. Kare Çıkarma (Adaptif veya Sabit)
                frame_count, frames, extract_time = extract_frames_adaptive(
                    VIDEO_OUTPUT_PATH, fps_val, sampling_mode, start_total_sec, target_max_dim
                )
                st.session_state['extracted_frames_cache'] = frames
                
                if frame_count > 0:
                    model_config = MODELS[selected_model]
                    frame_chunks = [frames[i:i + chunk_size] for i in range(0, len(frames), chunk_size)]
                    total_chunks = len(frame_chunks)
                    output_area = st.empty()
                    chunk_outputs = []

                    # 3. Görsel Algı (Vision AI)
                    t_vis_start = time.time()
                    with st.spinner("🤖 Ajan video karelerini analiz ediyor..."):
                        for chunk_idx, frame_chunk in enumerate(frame_chunks):
                            output_area.info(f"⏳ **1. Aşama (Görsel Algı):** Parça {chunk_idx + 1}/{total_chunks} ({len(frame_chunk)} kare) işleniyor...")
                            chunk_text = ""
                            for line in run_analysis_generator(frame_chunk, prompt_val, model_config):
                                chunk_text += line + " "
                            chunk_outputs.append(chunk_text)
                    t_vis_end = time.time()
                    vision_time = t_vis_end - t_vis_start

                    # 4. Sentezleme (Aggregator AI)
                    t_agg_start = time.time()
                    output_area.info("⏳ **2. Aşama (Nihai Karar Ajanı):** Parçalar sentezleniyor ve JSON üretiliyor...")
                    final_aggregated_text = run_aggregator_agent(chunk_outputs, prompt_val, model_config)
                    t_agg_end = time.time()
                    agg_time = t_agg_end - t_agg_start
                    
                    total_end_time = time.time()
                    total_time = total_end_time - total_start_time
                    throughput_fps = frame_count / total_time if total_time > 0 else 0

                    # Telemetri Saklama
                    st.session_state['metrics'] = {
                        "cut_time": cut_time,
                        "extract_time": extract_time,
                        "vision_time": vision_time,
                        "agg_time": agg_time,
                        "total_time": total_time,
                        "throughput_fps": throughput_fps,
                        "frame_count": frame_count
                    }

                    st.session_state['analysis_completed'] = True
                    st.session_state['model_result'] = final_aggregated_text
                    
                    parsed_result = parse_json_response(final_aggregated_text)
                    st.session_state['parsed_json'] = parsed_result

                    parse_failed = isinstance(parsed_result, dict) and parsed_result.get("status") == "failed"

                    if parse_failed:
                        st.session_state['saved_json_path'] = ""
                    else:
                        saved_path = save_json_to_file(parsed_result, final_aggregated_text, st.session_state['metrics'])
                        st.session_state['saved_json_path'] = saved_path

                        is_auto = "Tam Otonom" in agent_mode
                        execute_agent_tools(parsed_result, auto_execute=is_auto)

                    render_analysis_results(result_container, agent_mode)
                else:
                    st.error("Frame çıkarılamadı!")
            else:
                st.error("Video kesme hatası!")

if st.session_state.get('video_ready') and not run_btn:
    video_placeholder.subheader("🎥 İşlenen Video Kesiti")
    video_placeholder.video(VIDEO_OUTPUT_PATH)

if st.session_state.get('analysis_completed') and not run_btn:
    render_analysis_results(result_container, agent_mode)

if not run_btn and not st.session_state.get('video_ready'):
    video_placeholder.info("⬅️ Sol menüden ayarları yapıp 'Analiz ve Karar Destek Başlat' butonuna basın.")
