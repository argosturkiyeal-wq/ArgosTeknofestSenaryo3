import json
import logging
import re
from datetime import datetime

import requests
import streamlit as st
from json_repair import repair_json

import config
import core.memory as memory
from core.tools import execute_tool, get_tools_schema

logger = logging.getLogger(__name__)

LLAMA_SERVER_URL = config.LLAMA_SERVER_URL
JSON_OUTPUT_PATH = str(config.JSON_OUTPUT_PATH)

# "on timeout, retry twice" — sabit bir davranış, config'e taşınacak bir ayar değil.
REACT_TIMEOUT_RETRIES = 2

REACT_SYSTEM_PROMPT = f"""Sen bir Savunma Sanayii ve Saha Operasyonu Güvenlik Karar Destek Ajanısın.
Sana verilen, zaman damgalı video gözlemlerini analiz ederek sahadaki durumu değerlendirir ve gerektiğinde tanımlı araçları (tools) çağırarak somut aksiyonlar alırsın.

Birden fazla adımda, birden fazla aracı sırayla çağırabilirsin. Bir aracın sonucunu gördükten sonra ona göre başka bir araç çağırman tamamen normaldir (ör. önce olay kaydı oluştur, sonra sağlık ekibi çağır, sonra vardiya amirine bildir). Durum tam olarak ele alındığında — gerekli tüm araçlar tetiklendiğinde ya da hiçbir araç gerekmediğinde — daha fazla araç çağırma ve nihai değerlendirmeni yaz.

Operatörün isteği belirsizse tahmin etme, netleştirici soru sor.

Geçmiş örüntü kontrolü:
- "Geçmiş kayıtlar" bu videodan DEĞİL, sistemde saklı, önceki analizlerden gelen kalıcı veritabanı kayıtlarıdır. Bu videonun kendi içinde aynı ihlalin birkaç kez görünmesi "geçmiş örüntü" SAYILMAZ ve mock_gecmis_sorgula çağırmak için tek başına yeterli değildir.
- Videoda kkd_ihlali, dusme, arac_kazasi, tehlikeli_yakinlik, bolge_ihlali, yetkisiz_giris veya personel_toplanmasi kategorilerinden birine giren somut bir olay tespit ettiğinde, o olayla ilgili diğer araçları çağırmadan ÖNCE, aynı bölge için mock_gecmis_sorgula'yı çağır ve sistemde bununla ilgili geçmiş kayıt olup olmadığına bak.
- Sorgu sonucu bir örüntü gösteriyorsa (aynı tip olay 3 veya daha fazla kez kayıtlıysa), bunu özette açıkça belirt ve vardiya amirine yapısal bir bildirim öner.
- Video hiçbir somut olay/tehlike içermiyorsa (olay_tipi atanacak bir şey yoksa) geçmişi sorgulama — iterasyon bütçesini boşa harcama.

Daha fazla araç çağırmana gerek kalmadığında, SADECE ve KESİNLİKLE aşağıdaki JSON formatında Türkçe olarak nihai değerlendirmeni üret. Başka hiçbir açıklama metni yazma:

{{
  "summary": "Videodaki genel durumun kısa ve net Türkçe özeti",
  "events": [
    {{"time": "00:15", "event": "Tespit edilen 1. olay veya tehlike", "olay_tipi": "..."}}
  ],
  "risk": "Düşük / Orta / Yüksek / Kritik",
  "actions": [
    "Operatör için 1. aksiyon önerisi"
  ]
}}

Her event nesnesine olay_tipi alanı ekle ve değeri şu listeden seç: {", ".join(config.OLAY_TIPLERI)}. Emin değilsen "diger" kullan."""

def _build_react_messages(chunk_observations, user_prompt):
    obs_text = "\n\n".join([
        f"--- Parça {idx+1} Gözlemleri ---\n{res}"
        for idx, res in enumerate(chunk_observations) if res and res.strip()
    ])

    user_content = f"""=== BÜTÜNLEŞİK SAHA GÖZLEMLERİ ===
{obs_text}
==================================

Kullanıcı İsteği / Sorusu: "{user_prompt}\""""

    return [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

def _call_model(messages):
    """
    llama-server'a tek bir tur gönderir. Zaman aşımında REACT_TIMEOUT_RETRIES
    kadar tekrar dener; başka bir hata ya da tekrar denemeler tükenirse
    (response_json, None) yerine (None, hata_mesaji) döner — asla exception
    fırlatmaz.
    """
    payload = {
        "model": config.MODEL_NAME,
        "messages": messages,
        "tools": get_tools_schema(),
        "temperature": config.TEMPERATURE,
        "max_tokens": config.REACT_MAX_TOKENS,
    }

    attempts = REACT_TIMEOUT_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=config.REACT_REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            logger.warning("ReAct model çağrısı zaman aşımına uğradı (deneme %d/%d)", attempt, attempts)
            if attempt == attempts:
                return None, f"Model {attempts} denemede de zaman aşımına uğradı ({config.REACT_REQUEST_TIMEOUT}s)."
            continue
        except Exception as e:
            return None, f"Sunucuya bağlanılamadı ({LLAMA_SERVER_URL}). Hata: {e}"

        if response.status_code == 200:
            return response.json(), None
        return None, f"Sunucu hatası (status {response.status_code}): {response.text[:300]}"

    return None, "Model çağrısı başarısız oldu."

def _bolge_cikar(trace):
    """Trace'teki araç çağrısı argümanlarından en yakın bölge/konum bilgisini bulur.
    Bilinen sınır: ajan hiç araç çağırmazsa (düşük riskli video) bölge None kalır
    ve o kayıt bölge bazlı sorgulara düşmez. Poligon tabanlı bölge sistemi
    geldiğinde bu heuristik gereksizleşecek."""
    for step in trace:
        args = step.get("arguments") or {}
        for anahtar in ("bolge", "konum", "hedef_bolge"):
            if args.get(anahtar):
                return args[anahtar]
    return None

def _kaydet_hafizaya(video_id, final, trace):
    """Başarılı bir final JSON'daki olayları hafızaya yazar. Hata analizi çökertmez, sadece loglanır."""
    if not isinstance(final, dict) or final.get("status") == "failed":
        return
    events = final.get("events")
    if not events:
        return
    try:
        memory.kaydet_olaylar(video_id, events, bolge=_bolge_cikar(trace))
    except Exception as e:
        logger.error("Hafızaya olay kaydı başarısız: %s", e)

def run_react_agent(chunk_observations, user_prompt, model_config=None, video_id=None):
    """
    ReAct döngüsü: model her turda ya bir/birden çok araç çağırır ya da nihai
    cevabını verir. Araç sonuçları mesaj geçmişine (tool_call_id eşleşmesiyle)
    eklenerek modelin önceki adımlara göre akıl yürütmesi (chaining) sağlanır.

    Dönüş:
        {
          "final": parse edilmiş nihai JSON (dict) ya da None,
          "final_raw": modelin son turdaki ham metin cevabı,
          "trace": [{"step": int, "tool": str, "arguments": dict, "result": dict}, ...],
          "iteration_limit_reached": bool,
          "aborted": bool,
          "abort_reason": str ya da None,
        }
    """
    if video_id is None:
        video_id = datetime.now().strftime("video_%Y%m%d_%H%M%S")

    messages = _build_react_messages(chunk_observations, user_prompt)
    trace = []
    seen_calls = set()
    step_counter = 0

    for _ in range(config.MAX_REACT_ITERATIONS):
        response_json, error = _call_model(messages)

        if error is not None:
            logger.error("ReAct model çağrısı başarısız, döngü iptal ediliyor: %s", error)
            return {
                "final": {"status": "failed", "error": error},
                "final_raw": "",
                "trace": trace,
                "iteration_limit_reached": False,
                "aborted": True,
                "abort_reason": error,
            }

        message = response_json.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            final_raw = message.get("content", "") or ""
            final = parse_json_response(final_raw)
            _kaydet_hafizaya(video_id, final, trace)
            return {
                "final": final,
                "final_raw": final_raw,
                "trace": trace,
                "iteration_limit_reached": False,
                "aborted": False,
                "abort_reason": None,
            }

        # Kritik: tool_calls içeren assistant mesajı, tool sonuçlarından ÖNCE eklenmeli.
        messages.append({
            "role": "assistant",
            "content": message.get("content", "") or "",
            "tool_calls": tool_calls,
        })

        for call in tool_calls:
            step_counter += 1
            call_id = call.get("id", f"call_{step_counter}")
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")

            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except (json.JSONDecodeError, TypeError) as e:
                result = {"status": "error", "error": f"Argümanlar geçerli JSON değil: {e}"}
                trace.append({"step": step_counter, "tool": tool_name, "arguments": raw_args, "result": result})
                messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})
                continue

            dedup_key = (tool_name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
            if dedup_key in seen_calls:
                result = {
                    "status": "error",
                    "error": f"'{tool_name}' bu argümanlarla zaten başarıyla çalıştırıldı, tekrar çağırmaya gerek yok."
                }
            else:
                result = execute_tool(tool_name, arguments)
                if isinstance(result, dict) and result.get("status") == "ok":
                    seen_calls.add(dedup_key)

            trace.append({"step": step_counter, "tool": tool_name, "arguments": arguments, "result": result})
            messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})

    logger.warning("ReAct döngüsü %d adımda tamamlanamadı, iterasyon limiti doldu.", config.MAX_REACT_ITERATIONS)
    return {
        "final": None,
        "final_raw": "",
        "trace": trace,
        "iteration_limit_reached": True,
        "aborted": False,
        "abort_reason": None,
    }

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

    # Son çare: kaçırılmamış tırnak, eksik virgül gibi ufak sözdizimi hatalarını
    # veriyi UYDURMADAN onarmayı dener. Onaramazsa (boş string döner) düşer, hata verir.
    try:
        repaired = repair_json(raw_text, return_objects=True)
        if isinstance(repaired, dict):
            logger.warning("JSON parse: json_repair ile kurtarıldı. Orijinal hata: %s", last_exc)
            return repaired
    except Exception:
        pass

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
