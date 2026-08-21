import base64
import time

import cv2
import numpy as np
import requests

import config
from core.detection import detect_frame, detections_to_text

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

Sadece karelerde açıkça gördüğün nesneleri ve olayları yaz. Bir mekan türü, nesne veya kişi rolü hakkında emin değilsen tahmin etme; 'belirsiz' de. Görmediğin bir detayı asla uydurma.

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

        # YOLO on-elek: VLM'e kareyi "kor" gostermek yerine, onceden
        # tespit edilmis nesneleri (kisi/baret/yelek/forklift) metin
        # olarak da veriyoruz - dusuk seviyeli algi, yuksek seviyeli
        # yoruma (VLM) kanit olarak akar.
        img_arr = cv2.imdecode(np.frombuffer(base64.b64decode(b64_img), dtype=np.uint8), cv2.IMREAD_COLOR)
        detections = detect_frame(img_arr) if img_arr is not None else []
        det_text = detections_to_text(detections, ts)

        content.append({
            "type": "text",
            "text": f"\n[Zaman Damgası: {ts}] Kare Görseli:\n{det_text}"
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
