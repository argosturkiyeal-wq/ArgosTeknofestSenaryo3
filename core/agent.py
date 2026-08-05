import json
import logging
import re

import requests
import streamlit as st

import config

logger = logging.getLogger(__name__)

LLAMA_SERVER_URL = config.LLAMA_SERVER_URL
JSON_OUTPUT_PATH = str(config.JSON_OUTPUT_PATH)

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
