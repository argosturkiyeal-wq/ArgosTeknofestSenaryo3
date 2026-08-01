import streamlit as st
import os
import subprocess
import time
import cv2
import shutil
import json
import re
import base64
import requests
from datetime import datetime

# ============================================================
# AYARLAR VE SABİTLER
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KOD_DIR = os.path.join(BASE_DIR, "Kod")
FRAMES_DIR = os.path.join(KOD_DIR, "frames")
VIDEO_OUTPUT_PATH = os.path.join(KOD_DIR, "video_kesit.mp4")
JSON_OUTPUT_PATH = os.path.join(KOD_DIR, "analiz_sonucu.json")

# Model ve Araç Yolları
LLAMA_CLI = "/home/rabia/llama.cpp/build_120a/bin/llama-cli"
LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"

# Model Konfigürasyonları
MODELS = {
    "8B": {
        "model_path": "/home/rabia/llama.cpp/models/Qwen3-VL-8B/Qwen3VL-8B-Instruct-Q8_0.gguf",
        "mmproj_path": "/home/rabia/llama.cpp/models/Qwen3-VL-8B/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf",
        "ngl": "28",
        "ctx": "24576",
        "ub": "4096"
    },
    "32B": {
        "model_path": "/home/rabia/llama.cpp/models/Qwen3-VL-32B/Qwen3-VL-32B-Instruct.Q5_K_M.gguf",
        "mmproj_path": "/home/rabia/llama.cpp/models/Qwen3-VL-32B/Qwen3-VL-32B-Instruct.mmproj-f16.gguf",
        "ngl": "0",
        "ctx": "24576",
        "ub": "24576"
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

st.set_page_config(layout="wide", page_title="TEKNOFEST Senaryo 3 - Video Analiz & Karar Destek Ajanı", page_icon="🛸")

# Session State Başlatma
if 'analysis_completed' not in st.session_state:
    st.session_state['analysis_completed'] = False
if 'video_ready' not in st.session_state:
    st.session_state['video_ready'] = False
if 'model_result' not in st.session_state:
    st.session_state['model_result'] = ""
if 'last_duration' not in st.session_state:
    st.session_state['last_duration'] = 0.0
if 'parsed_json' not in st.session_state:
    st.session_state['parsed_json'] = None
if 'action_logs' not in st.session_state:
    st.session_state['action_logs'] = []
if 'saved_json_path' not in st.session_state:
    st.session_state['saved_json_path'] = ""
if 'tools_executed' not in st.session_state:
    st.session_state['tools_executed'] = False

# ============================================================
# MOCK FONKSİYONLAR VE ARAÇ KAYIT DEFTERİ (TOOL REGISTRY)
# ============================================================
def mock_saglik_ekibi_cagir(detay=""):
    log = f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 MOCK SAĞLIK EKİBİ ÇAĞRILDI: {detay}"
    st.session_state['action_logs'].append(log)
    return log

def mock_guvenlik_alert_ver(detay=""):
    log = f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ MOCK GÜVENLİK BİLDİRİMİ GÖNDERİLDİ: {detay}"
    st.session_state['action_logs'].append(log)
    return log

def mock_olay_kaydi_olustur(detay=""):
    log = f"[{datetime.now().strftime('%H:%M:%S')}] 📝 MOCK OLAY KAZA KAYDI OLUŞTURULDU: {detay}"
    st.session_state['action_logs'].append(log)
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
# YARDIMCI FONKSİYONLAR
# ============================================================
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
    duration = end_sec - start_sec
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", source_path,
        "-t", str(duration),
        "-c", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        st.error(f"Video kesme hatası: {result.stderr}")
        return False
    return True

def extract_frames(video_path, fps, start_total_sec=0, max_dim=640):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0, []

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps == 0: video_fps = 30
    frame_interval = max(1, int(video_fps / fps))
    
    frame_count = 0
    saved_count = 0
    extracted_frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % frame_interval == 0:
            # Görsel Boyutlandırma (Aspect Ratio Korunarak Vision Token Tasarrufu)
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

            # RAM Bellekte JPEG Sıkıştırma (%85 Kalite) ve Doğrudan Base64 Kodlama (Disk I/O Bypass)
            success, buffer = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if success:
                b64_str = base64.b64encode(buffer).decode('utf-8')
                
                # Mutlak Zamansal Farkındalık (Video Kesit Ofseti)
                sec_elapsed = start_total_sec + int(frame_count / video_fps)
                m, s = divmod(sec_elapsed, 60)
                timestamp_str = f"{m:02d}:{s:02d}"
                
                extracted_frames.append({"b64": b64_str, "timestamp": timestamp_str})
                saved_count += 1
        
        frame_count += 1
    
    cap.release()
    return saved_count, extracted_frames

def parse_json_response(raw_text):
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except Exception:
        pass

    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass

    bracket_match = re.search(r'(\{.*?\})', raw_text, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1))
        except Exception:
            pass

    # Akıllı Düzeltme: Eğer model serbest metin verdiyse metni otomatik özet formatına çevir
    clean_text = re.sub(r'⚠️ Sunucuya bağlanılamadı.*', '', raw_text).strip()
    return {
        "summary": clean_text if clean_text else "Analiz tamamlandı.",
        "events": [{"time": "00:00", "event": "Video analizi tamamlandı"}],
        "risk": "Orta" if any(w in clean_text.lower() for w in ["faul", "kaza", "düşme", "risk", "tehlike", "ihlal", "yaralanma"]) else "Düşük",
        "actions": ["Saha durumunu ve operasyonu takip etmeye devam et"],
        "triggered_tools": []
    }

def save_json_to_file(parsed_data, raw_text):
    try:
        data_to_save = parsed_data if (parsed_data and isinstance(parsed_data, dict)) else {"summary": "Ayrıştırılamayan ham metin", "raw_output": raw_text}
        with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        return JSON_OUTPUT_PATH
    except Exception as e:
        st.error(f"JSON kaydedilemedi: {e}")
        return ""

def check_llama_server_health(server_url=LLAMA_SERVER_URL):
    """
    Arka plandaki llama-server servisinin erişilebilirliğini ve sağlık durumunu kontrol eder.
    """
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

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def run_analysis_generator(image_items, prompt, model_config):
    content = [{"type": "text", "text": prompt}]
    for item in image_items:
        if isinstance(item, dict):
            b64_img = item.get("b64") or (encode_image_to_base64(item["path"]) if "path" in item else "")
            ts = item.get("timestamp", "00:00")
        else:
            b64_img = encode_image_to_base64(item) if isinstance(item, str) else ""
            ts = "00:00"
            
        content.append({
            "type": "text",
            "text": f"\n[Zaman Damgası: {ts}] Kare Görseli:"
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
        })
    
    payload = {
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 1500,
        "repeat_penalty": 1.2
    }
    
    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            yield text
        else:
            yield f"⚠️ Sunucu Hatası (Status {response.status_code}): {response.text}"
    except Exception as e:
        yield f"⚠️ Sunucuya bağlanılamadı ({LLAMA_SERVER_URL}). Lütfen arka planda llama-server'ın çalıştığından emin olun! Hata: {e}"

def run_aggregator_agent(chunk_observations, user_prompt, model_config):
    """
    Tüm parçalardan gelen görsel gözlemleri sentezleyen ve TEKİL, KUSURSUZ bir JSON üreten Nihai Karar Destek Ajanı.
    """
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
  "summary": "Videodaki genel durumun kısa ve net Türkçe özeti (Kullanıcı sorusunun yanıtı dahil)",
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
        "messages": [{"role": "user", "content": aggregator_prompt}],
        "temperature": 0.1,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=90)
        if response.status_code == 200:
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            # Response format json_object desteklenmiyorsa fallback
            payload.pop("response_format", None)
            res2 = requests.post(LLAMA_SERVER_URL, json=payload, timeout=90)
            if res2.status_code == 200:
                return res2.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        pass
        
    return obs_text

# ============================================================
# ARAYÜZ (TEKNOFEST SENARYO 3 ÖZEL)
# ============================================================

st.title("🛸 TEKNOFEST Yapay Zeka Dil Ajanları Yarışması")
st.subheader("Senaryo 3: Video Analiz ve Operasyonel Karar Destek Ajanı")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🖥️ Sunucu Sağlık Durumu (Health Check)")
    server_status = check_llama_server_health()
    
    if server_status["online"]:
        st.success(f"🟢 **Model Sunucusu Aktif**\n\n- Adres: `127.0.0.1:8080`\n- Yanıt Süresi: `{server_status['latency_ms']} ms`")
    else:
        st.error("🔴 **Model Sunucusu Çevrimdışı!**\n\n`http://127.0.0.1:8080` servisine erişilemiyor.")
        with st.expander("🛠️ Sunucuyu Başlatma Talimatı"):
            st.code("""/home/rabia/llama.cpp/build_120a/bin/llama-server \\
  -m /home/rabia/llama.cpp/models/Qwen3-VL-8B/Qwen3VL-8B-Instruct-Q8_0.gguf \\
  --mmproj /home/rabia/llama.cpp/models/Qwen3-VL-8B/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf \\
  --host 127.0.0.1 \\
  --port 8080 \\
  -c 24576 \\
  -ub 4096 \\
  -np 2 \\
  -ngl 28 \\
  -fa 1""", language="bash")

    st.markdown("---")
    st.header("⚙️ Model ve Parametreler")
    selected_model = st.selectbox(
        "Model",
        options=["8B", "32B"],
        index=0,
        help="8B: Hızlı çıkarım (28 NGL GPU), 32B: Yüksek doğruluk (CPU/GPU hibrit)"
    )
    
    st.markdown("---")
    st.header("🤖 Ajan Çalışma Modu (Tool Calling)")
    agent_mode = st.radio(
        "Araç Tetikleme Modu",
        options=["🤖 Tam Otonom (Otomatik Araç Tetikleme)", "👨‍✈️ İnsan Denetimli (Operatör Onaylı)"],
        index=0,
        help="Otonom modda ajan riskli durumlarda araçları (sağlık/güvenlik/kayıt) otomatik çalıştırır."
    )

    st.markdown("---")
    st.header("📹 Video Yükleme")
    uploaded_video = st.file_uploader("Bir operasyon/saha videosu seçin", type=["mp4", "mov", "avi", "webm"])
    
    source_video_path = None
    if uploaded_video:
        source_video_path = save_uploaded_file(uploaded_video)
        st.success(f"Video yüklendi: {uploaded_video.name}")
    else:
        st.info("Lütfen bir video dosyası yükleyin.")

    st.markdown("---")
    st.header("⏱️ Zaman ve Kare Ayarları")
    
    c1, c2, c3 = st.columns(3)
    start_h = c1.number_input("Baş. Saat", 0, 23, 0)
    start_m = c2.number_input("Baş. Dak", 0, 59, 0)
    start_s = c3.number_input("Baş. San", 0, 59, 0)
    
    c4, c5, c6 = st.columns(3)
    end_h = c4.number_input("Bit. Saat", 0, 23, 0)
    end_m = c5.number_input("Bit. Dak", 0, 59, 0)
    end_s = c6.number_input("Bit. San", 0, 59, 30)

    start_total_sec = start_h * 3600 + start_m * 60 + start_s
    end_total_sec = end_h * 3600 + end_m * 60 + end_s

    st.markdown("---")
    st.header("🖼️ Görsel Çözünürlük ve Hız Ayarı")
    resolution_option = st.selectbox(
        "Görsel Çözünürlük Modu",
        options=["🚀 Hızlı (640px)", "⚖️ Dengeli (896px)", "🔍 Tam Çözünürlük (Orijinal)"],
        index=0,
        help="640px: Maksimum hız (~4x hızlanma). 896px: Dengeli detay ve hız. Tam Çözünürlük: Orijinal ham görsel."
    )
    
    max_dim_map = {
        "🚀 Hızlı (640px)": 640,
        "⚖️ Dengeli (896px)": 896,
        "🔍 Tam Çözünürlük (Orijinal)": 0
    }
    target_max_dim = max_dim_map[resolution_option]

    fps_val = st.number_input("FPS (Analiz Kare Sıklığı)", min_value=1, max_value=30, value=2)
    chunk_size = st.number_input("Chunk Boyutu (Resim Sayısı)", min_value=1, max_value=100, value=10)
    
    st.markdown("---")
    prompt_val = st.text_area("İstem (TEKNOFEST System Prompt)", value=DEFAULT_TEKNOFEST_PROMPT, height=240)
    
    st.markdown("---")
    run_btn = st.button("🚀 Analiz ve Karar Destek Başlat", type="primary", use_container_width=True)

    if run_btn:
        st.session_state['analysis_completed'] = False
        st.session_state['video_ready'] = False
        st.session_state['model_result'] = ""
        st.session_state['parsed_json'] = None
        st.session_state['saved_json_path'] = ""
        st.session_state['tools_executed'] = False
        st.session_state['action_logs'] = []




def render_analysis_results(container, agent_mode):
    with container:
        parsed = st.session_state.get('parsed_json')
        saved_path = st.session_state.get('saved_json_path')
        
        if saved_path:
            st.success(f"✅ Analiz tamamlandı! Çıktı JSON dosyası olarak kaydedildi: `{saved_path}`")
            
            try:
                with open(saved_path, "r", encoding="utf-8") as jf:
                    json_bytes = jf.read()
                st.download_button(
                    label="📥 JSON Dosyasını İndir",
                    data=json_bytes,
                    file_name="analiz_sonucu.json",
                    mime="application/json"
                )
            except Exception:
                pass

        if parsed and isinstance(parsed, dict):
            risk_val = parsed.get("risk", "Bilinmiyor")
            risk_color = "🔴" if any(r in str(risk_val).lower() for r in ["yüksek", "kritik", "danger"]) else ("🟡" if "orta" in str(risk_val).lower() else "🟢")
            
            m1, m2 = st.columns([1, 2])
            m1.metric("Risk Seviyesi", f"{risk_color} {risk_val}")
            m2.info(f"**Özet:** {parsed.get('summary', 'Özet bilgisi üretilmedi.')}")

            st.markdown("---")
            
            st.subheader("⏱️ Zaman Damgalı Olaylar")
            events = parsed.get("events", [])
            if events and isinstance(events, list) and len(events) > 0:
                for ev in events:
                    t_val = ev.get("time", "--:--") if isinstance(ev, dict) else ""
                    e_val = ev.get("event", str(ev)) if isinstance(ev, dict) else str(ev)
                    st.markdown(f"- **`[{t_val}]`** {e_val}")
            else:
                st.write("Herhangi bir spesifik zaman damgalı olay listelenmedi.")

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
                        st.info(f"⚡ **Açılan Araç:** {tool_info['name_tr']} | **Gerekçe:** {detay_txt}")
                        
                        # İnsan Denetimli Modda Manuel Onay Butonları
                        if "İnsan Denetimli" in agent_mode:
                            if st.button(f"✅ Onayla ve Çalıştır: {tool_info['name_tr']}", key=f"btn_{t_name}"):
                                if t_name in TOOLS:
                                    TOOLS[t_name]["func"](detay=detay_txt)
                                    st.success(f"{tool_info['name_tr']} operatör onayıyla çalıştırıldı!")
                                    st.rerun()
            else:
                st.write("Ajan herhangi bir özel araç tetikleme ihtiyacı görmedi.")

            st.markdown("---")

            st.subheader("🛡️ Operatör Aksiyon Önerileri & Manuel Butonlar")
            actions = parsed.get("actions", [])
            if actions and isinstance(actions, list) and len(actions) > 0:
                for act in actions:
                    st.warning(f"• **Aksiyon Önerisi:** {act}")
                
                st.markdown("##### ⚡ Operatör Manuel Aksiyon Butonları")
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
            else:
                st.write("Aksiyon önerisi bulunmuyor.")

        else:
            st.warning("Model çıktısından görsel kartlar oluşturulamadı. Üretilen yanıt JSON dosyasına aktarıldı.")

        if st.session_state.get('action_logs'):
            st.markdown("---")
            st.subheader("📜 Tetiklenen Mock Sistem İşlem Günlüğü (Logs)")
            for l in st.session_state['action_logs']:
                st.code(l, language="text")

        st.info(f"Analiz İşlem Süresi: {st.session_state.get('last_duration', 0):.2f} saniye")

# --- ANA EKRAN ---
col_video, col_result = st.columns([1.2, 1.8])

video_placeholder = col_video.empty()
result_container = col_result.container()

if run_btn:
    if not server_status["online"]:
        st.error("❌ Analiz başlatılamıyor: Model sunucusu (llama-server) çevrimdışı! Lütfen sol menüdeki başlatma talimatını takip edin.")
    elif not source_video_path:
        st.error("Lütfen önce bir video dosyası seçin!")
    elif fps_val is None:
        st.error("Lütfen FPS değerini girin!")
    elif chunk_size is None:
        st.error("Lütfen chunk boyutunu girin!")
    elif end_total_sec <= start_total_sec:
        st.error("Bitiş zamanı başlangıç zamanından büyük olmalıdır!")
    else:
        with result_container:
            if cut_video(source_video_path, start_total_sec, end_total_sec, VIDEO_OUTPUT_PATH):
                st.session_state['video_ready'] = True
                
                video_placeholder.subheader("🎥 İşlenen Video Kesiti")
                video_placeholder.video(VIDEO_OUTPUT_PATH)
                
                frame_count, frames = extract_frames(VIDEO_OUTPUT_PATH, fps_val, start_total_sec, target_max_dim)
                
                if frame_count > 0:
                    analysis_start_time = time.time()
                    frame_chunks = [frames[i:i + chunk_size] for i in range(0, len(frames), chunk_size)]
                    total_chunks = len(frame_chunks)

                    output_area = st.empty()
                    chunk_outputs = []

                    model_config = MODELS[selected_model]

                    with st.spinner("🤖 Ajan video karelerini analiz ediyor ve kararları işliyor..."):
                        # 1. AŞAMA: Kare bazlı görsel algı parçaları
                        for chunk_idx, frame_chunk in enumerate(frame_chunks):
                            output_area.info(f"⏳ **1. Aşama (Görsel Algı):** Parça {chunk_idx + 1}/{total_chunks} ({len(frame_chunk)} kare) işleniyor...")
                            chunk_text = ""
                            for line in run_analysis_generator(frame_chunk, prompt_val, model_config):
                                chunk_text += line + " "
                            chunk_outputs.append(chunk_text)

                        # 2. AŞAMA: Nihai Özetleyici Ajan ile Bütünleşik Karar Sentezi
                        output_area.info("⏳ **2. Aşama (Nihai Karar Ajanı):** Tüm parçalar sentezleniyor ve TEKİL JSON kararı üretiliyor...")
                        final_aggregated_text = run_aggregator_agent(chunk_outputs, prompt_val, model_config)

                    analysis_end_time = time.time()
                    elapsed_time = analysis_end_time - analysis_start_time

                    st.session_state['analysis_completed'] = True
                    st.session_state['model_result'] = final_aggregated_text
                    st.session_state['last_duration'] = elapsed_time
                    st.session_state['selected_model'] = selected_model
                    
                    parsed_result = parse_json_response(final_aggregated_text)
                    st.session_state['parsed_json'] = parsed_result
                    
                    saved_path = save_json_to_file(parsed_result, final_aggregated_text)
                    st.session_state['saved_json_path'] = saved_path

                    # Otonom Araç Çalıştırma Mantığı
                    is_auto = "Tam Otonom" in agent_mode
                    execute_agent_tools(parsed_result, auto_execute=is_auto)
                    st.session_state['tools_executed'] = True

                    # Ekran Kartlarını Anında Ekrana Çiz
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
    video_placeholder.info("⬅️ Sol menüden yarışma şartnamesine uygun ayarları yapıp 'Analiz ve Karar Destek Başlat' butonuna basın.")
