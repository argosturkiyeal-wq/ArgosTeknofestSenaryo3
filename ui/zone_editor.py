"""
Streamlit Poligon Cizim ve Bolge Duzenleyici Bileseni.
st_canvas (streamlit-drawable-canvas) kullanarak interaktif bolge cizimi saglar.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

import cv2
import numpy as np
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# Root path adjustment
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.zones import Zone, ZoneRule, load_zones, save_zones


def get_sample_background_image(image_path: str | None = None) -> np.ndarray:
    """Load image from path or return a default blank operational canvas."""
    if image_path and Path(image_path).exists():
        img = cv2.imread(image_path)
        if img is not None:
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Return default 640x480 dark operational frame if no image available
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add grid lines for visual reference
    for x in range(0, 640, 80):
        cv2.line(blank, (x, 0), (x, 480), (40, 40, 40), 1)
    for y in range(0, 480, 60):
        cv2.line(blank, (0, y), (640, y), (40, 40, 40), 1)

    cv2.putText(blank, "TEKNOFEST 2026 - Saha Görüntüsü / Poligon Çizim Tuvali", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    return blank


def render_zone_editor():
    st.header("📍 Bölge Çizim ve Düzenleme Arayüzü")
    st.caption("Ekranda mouse (fare) ile tıklayarak poligon alanları çizebilir ve kurallarıyla 'zones.json' dosyasına kaydedebilirsiniz.")

    # 1. Load existing zones
    json_path = config.BASE_DIR / "zones.json"
    existing_zones = load_zones(json_path)

    # 2. Select image or default
    st.subheader("1. Kamera Karesi Seçimi")
    col_img1, col_img2 = st.columns([2, 1])
    uploaded_frame = col_img1.file_uploader("Çizim yapılacak kare görselini yükleyin (Opsiyonel)", type=["png", "jpg", "jpeg"])

    image_path = None
    if uploaded_frame:
        temp_path = config.OUTPUT_DIR / "editor_frame.jpg"
        with open(temp_path, "wb") as f:
            f.write(uploaded_frame.getbuffer())
        image_path = str(temp_path)

    bg_img = get_sample_background_image(image_path)
    img_h, img_w, _ = bg_img.shape

    # 3. Canvas options
    st.subheader("2. Poligon Çizim Tuvali (st_canvas)")
    c_opts1, c_opts2, c_opts3 = st.columns(3)
    stroke_color = c_opts1.color_picker("Çizgi Rengi", "#FF0000")
    fill_color = c_opts2.color_picker("Dolgu Rengi (Şeffaf)", "#FF000022")
    drawing_mode = c_opts3.selectbox("Çizim Aracı Mode", ["polygon", "transform"])

    st.info("💡 **Nasıl Çizilir?** Tuval üzerinde sol fare tuşuyla tıklayarak poligon köşelerini ekleyin. Çizimi bitirmek için ilk noktaya tekrar tıklayın veya çift tıklayın.")

    # 4. Render st_canvas
    canvas_result = st_canvas(
        fill_color=fill_color,
        stroke_width=3,
        stroke_color=stroke_color,
        background_image=uploaded_frame if uploaded_frame else None,
        background_color="#1E1E1E" if not uploaded_frame else None,
        height=img_h,
        width=img_w,
        drawing_mode=drawing_mode,
        key="zone_canvas",
    )

    # 5. Extract polygons from canvas_result
    drawn_polygons = []
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])
        for obj in objects:
            if obj.get("type") == "path":
                # Convert path commands (M, L, etc.) to (x, y) coordinates
                path_pts = []
                path_cmds = obj.get("path", [])
                left = obj.get("left", 0)
                top = obj.get("top", 0)
                scale_x = obj.get("scaleX", 1)
                scale_y = obj.get("scaleY", 1)

                for cmd in path_cmds:
                    if len(cmd) >= 3 and cmd[0] in ["M", "L"]:
                        px = left + cmd[1] * scale_x
                        py = top + cmd[2] * scale_y
                        # Normalize to 0.0 - 1.0
                        norm_x = round(max(0.0, min(1.0, px / img_w)), 4)
                        norm_y = round(max(0.0, min(1.0, py / img_h)), 4)
                        path_pts.append((norm_x, norm_y))

                if len(path_pts) >= 3:
                    drawn_polygons.append(path_pts)

    st.markdown("---")
    st.subheader("3. Bölge Bilgileri ve Kuralları")

    with st.form("new_zone_form"):
        col_f1, col_f2, col_f3 = st.columns(3)
        zone_id = col_f1.text_input("Bölge ID (Benzersiz)", f"zone_0{len(existing_zones) + 1}")
        zone_name = col_f2.text_input("Bölge Adı", "Kriti̇k Saha Bölgesi")
        zone_type = col_f3.selectbox("Bölge Tipi", ["yasakli", "yaya_yolu", "arac_yolu", "yukleme_alani"])

        col_r1, col_r2 = st.columns(2)
        helmet_req = col_r1.checkbox("Baret Zorunlu", value=True)
        vest_req = col_r2.checkbox("Yelek Zorunlu", value=False)

        forbidden_classes_str = st.text_input("Yasaklı Sınıflar (Virgülle ayırın)", "person, forklift")
        allowed_classes_str = st.text_input("İzin Verilen Sınıflar (Virgülle ayırın)", "")

        speed_limit = st.number_input("Hız Limiti (km/h - Opsiyonel)", min_value=0.0, max_value=120.0, value=0.0)

        submit_btn = st.form_submit_button("💾 Bölgeyi zones.json'a Kaydet", type="primary")

        if submit_btn:
            if not drawn_polygons:
                st.error("❌ Lütfen öncelikle tuval üzerinde en az 3 noktalı bir poligon çizin!")
            else:
                last_poly = drawn_polygons[-1]
                forbidden_list = [s.strip() for s in forbidden_classes_str.split(",") if s.strip()]
                allowed_list = [s.strip() for s in allowed_classes_str.split(",") if s.strip()]

                rule = ZoneRule(
                    allowed_classes=allowed_list,
                    forbidden_classes=forbidden_list,
                    helmet_required=helmet_req,
                    vest_required=vest_req,
                    speed_limit_kmh=speed_limit if speed_limit > 0 else None,
                )

                new_zone = Zone(
                    zone_id=zone_id,
                    name=zone_name,
                    type=zone_type,
                    polygon=last_poly,
                    rules=rule,
                )

                # Filter out any zone with duplicate zone_id
                updated_zones = [z for z in existing_zones if z.zone_id != zone_id]
                updated_zones.append(new_zone)

                save_zones(updated_zones, json_path)
                st.success(f"✅ Bölge `{zone_id}` ({zone_name}) başarıyla `zones.json` dosyasına kaydedildi!")
                st.json(new_zone.to_dict())

    st.markdown("---")
    st.subheader("📋 Mevcut Kayıtlı Bölge Listesi (`zones.json`)")
    if existing_zones:
        for z in existing_zones:
            with st.expander(f"📍 {z.zone_id} — {z.name} ({z.type})"):
                st.json(z.to_dict())
    else:
        st.write("Henüz kayıtlı bölge bulunmuyor.")
