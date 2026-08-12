import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import config
from core.sampler import save_uploaded_file, cut_video, extract_frames_adaptive, find_best_matching_frame
from core.vision import MODELS, DEFAULT_TEKNOFEST_PROMPT, check_llama_server_health, run_analysis_generator
from core.agent import run_react_agent, save_json_to_file
from core.tools import TOOL_REGISTRY, TOOL_CALL_LOG, EVENT_BUS_LOG, mock_saglik_ekibi_cagir, mock_guvenlik_alert_ver, mock_olay_kaydi_olustur

# ============================================================
# AYARLAR VE SABİTLER
# ============================================================
VIDEO_OUTPUT_PATH = str(config.VIDEO_OUTPUT_PATH)

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
if 'react_trace' not in st.session_state:
    st.session_state['react_trace'] = []
if 'react_iteration_limit_reached' not in st.session_state:
    st.session_state['react_iteration_limit_reached'] = False
if 'react_aborted' not in st.session_state:
    st.session_state['react_aborted'] = False
if 'react_abort_reason' not in st.session_state:
    st.session_state['react_abort_reason'] = None
if 'saved_json_path' not in st.session_state:
    st.session_state['saved_json_path'] = ""
if 'extracted_frames_cache' not in st.session_state:
    st.session_state['extracted_frames_cache'] = []

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
        st.session_state['react_trace'] = []
        st.session_state['react_iteration_limit_reached'] = False
        st.session_state['react_aborted'] = False
        st.session_state['react_abort_reason'] = None
        st.session_state['saved_json_path'] = ""
        st.session_state['metrics'] = {}
        st.session_state['extracted_frames_cache'] = []

def render_analysis_results(container):
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
        aborted = st.session_state.get('react_aborted', False)

        if aborted:
            st.error(f"❌ ReAct döngüsü model sunucusundan yanıt alamadığı için durduruldu: {st.session_state.get('react_abort_reason', 'Bilinmeyen hata')}")
        elif parse_failed:
            st.error(f"❌ Model yanıt verdi ama çıktısı geçerli JSON değildi: {parsed.get('error', 'Bilinmeyen hata')}")
            with st.expander("🔍 Ham Model Çıktısı (hata ayıklama için)"):
                st.code(st.session_state.get('model_result', ''), language="text")
        elif saved_path:
            st.success(f"✅ Analiz tamamlandı! Çıktı kaydedildi: `{saved_path}`")
            try:
                with open(saved_path, "r", encoding="utf-8") as jf:
                    st.download_button("📥 JSON İndir", jf.read(), "analiz_sonucu_v2.json", "application/json")
            except Exception:
                pass

        # 🔄 REACT ADIM İZİ (gerçek tool-calling loop'unun çalıştırdığı adımlar)
        trace = st.session_state.get('react_trace', [])
        if st.session_state.get('react_iteration_limit_reached'):
            st.warning(f"⚠️ ReAct döngüsü {config.MAX_REACT_ITERATIONS} adımda tamamlanamadı (iterasyon limiti doldu). Bu NİHAİ bir sonuç değildir — aşağıda o ana kadar toplanan adımlar listelidir.")
        if trace:
            with st.expander(f"🔄 ReAct Adım İzi ({len(trace)} araç çağrısı)"):
                for step in trace:
                    tool_info = TOOL_REGISTRY.get(step["tool"], {"name_tr": step["tool"]})
                    st.markdown(f"**Adım {step['step']} — {tool_info['name_tr']}**")
                    st.json({"arguments": step["arguments"], "result": step["result"]})

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

        if TOOL_CALL_LOG or EVENT_BUS_LOG:
            st.markdown("---")
            st.subheader("📜 Event Bus & Tetiklenen Sistem İşlem Günlüğü (Logs)")
            for entry in TOOL_CALL_LOG:
                tool_info = TOOL_REGISTRY.get(entry["tool"], {"name_tr": entry["tool"]})
                st.code(f"[{entry['ts']}] 🔧 {tool_info['name_tr']} — args: {entry['arguments']} -> sonuç: {entry['result']}", language="text")
            for entry in EVENT_BUS_LOG:
                st.code(f"[{entry['ts']}] 📡 [EVENT BUS - {entry['topic']}] Payload: {json.dumps(entry['payload'], ensure_ascii=False)}", language="text")

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

                    # 4. Sentezleme (ReAct Ajanı — çok adımlı tool-calling)
                    t_agg_start = time.time()
                    output_area.info("⏳ **2. Aşama (Nihai Karar Ajanı):** ReAct döngüsü çalışıyor (araçlar tetikleniyor, adımlar zincirleniyor)...")
                    react_result = run_react_agent(chunk_outputs, prompt_val, model_config)
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
                    st.session_state['model_result'] = react_result["final_raw"]
                    st.session_state['react_trace'] = react_result["trace"]
                    st.session_state['react_iteration_limit_reached'] = react_result["iteration_limit_reached"]
                    st.session_state['react_aborted'] = react_result["aborted"]
                    st.session_state['react_abort_reason'] = react_result["abort_reason"]

                    parsed_result = react_result["final"]
                    st.session_state['parsed_json'] = parsed_result

                    parse_failed = isinstance(parsed_result, dict) and parsed_result.get("status") == "failed"

                    if parse_failed or parsed_result is None:
                        st.session_state['saved_json_path'] = ""
                    else:
                        saved_path = save_json_to_file(parsed_result, react_result["final_raw"], st.session_state['metrics'])
                        st.session_state['saved_json_path'] = saved_path

                    render_analysis_results(result_container)
                else:
                    st.error("Frame çıkarılamadı!")
            else:
                st.error("Video kesme hatası!")

if st.session_state.get('video_ready') and not run_btn:
    video_placeholder.subheader("🎥 İşlenen Video Kesiti")
    video_placeholder.video(VIDEO_OUTPUT_PATH)

if st.session_state.get('analysis_completed') and not run_btn:
    render_analysis_results(result_container)

if not run_btn and not st.session_state.get('video_ready'):
    video_placeholder.info("⬅️ Sol menüden ayarları yapıp 'Analiz ve Karar Destek Başlat' butonuna basın.")
