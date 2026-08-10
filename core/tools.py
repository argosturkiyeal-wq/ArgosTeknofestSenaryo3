import random
from datetime import datetime, timedelta

import config
import core.memory as memory

# ============================================================
# SAVANT TİPİ EVENT BUS
# ============================================================
EVENT_BUS_LOG = []

def publish_event_to_bus(topic, payload):
    """Savant tarzı çoklu dış sistem yayıncısı (Event Publisher Mock)."""
    entry = {"ts": datetime.now().strftime('%H:%M:%S'), "topic": topic, "payload": payload}
    EVENT_BUS_LOG.append(entry)
    return entry

# ============================================================
# MOCK ARAÇ FONKSİYONLARI
# ============================================================
def mock_saglik_ekibi_cagir(detay="", konum="Belirtilmedi", aciliyet="orta"):
    ticket_id = f"SGL-{datetime.now().year}-{random.randint(1000, 9999):04d}"
    eta_dk = {"dusuk": 15, "orta": 8, "yuksek": 4, "kritik": 2}.get(aciliyet, 8)
    result = {
        "status": "ok",
        "ticket_id": ticket_id,
        "konum": konum,
        "aciliyet": aciliyet,
        "eta_dk": eta_dk,
        "mesaj": f"Sağlık ekibi {konum} bölgesine yönlendirildi. Tahmini varış süresi {eta_dk} dakika."
    }
    publish_event_to_bus("DISPATCH_HEALTH_TEAM", {"detay": detay, "konum": konum, "aciliyet": aciliyet, "ticket_id": ticket_id})
    return result

def mock_guvenlik_alert_ver(detay="", seviye="uyari"):
    ticket_id = f"GUV-{datetime.now().year}-{random.randint(1000, 9999):04d}"
    result = {
        "status": "ok",
        "ticket_id": ticket_id,
        "seviye": seviye,
        "bildirilen_birim": "Saha Güvenlik Ekibi",
        "mesaj": f"Güvenlik bildirimi '{seviye}' seviyesinde Saha Güvenlik Ekibi'ne iletildi."
    }
    publish_event_to_bus("SECURITY_ALERT_BROADCAST", {"detay": detay, "seviye": seviye, "ticket_id": ticket_id})
    return result

def mock_olay_kaydi_olustur(detay="", olay_tipi="diger"):
    kayit_no = f"OLY-{datetime.now().year}-{random.randint(1000, 9999):04d}"
    result = {
        "status": "ok",
        "kayit_no": kayit_no,
        "olay_tipi": olay_tipi,
        "mesaj": f"Olay kaydı '{kayit_no}' numarasıyla ({olay_tipi}) sisteme işlendi."
    }
    publish_event_to_bus("INCIDENT_LOG_CREATED", {"detay": detay, "olay_tipi": olay_tipi, "kayit_no": kayit_no})
    return result

def mock_alan_kapat(bolge="", tahmini_sure_dk=10):
    kapatma_id = f"ALN-{datetime.now().year}-{random.randint(1000, 9999):04d}"
    yeniden_acilis = (datetime.now() + timedelta(minutes=tahmini_sure_dk)).strftime('%H:%M')
    result = {
        "status": "ok",
        "kapatma_id": kapatma_id,
        "bolge": bolge,
        "tahmini_sure_dk": tahmini_sure_dk,
        "tahmini_yeniden_acilis": yeniden_acilis,
        "mesaj": f"'{bolge}' bölgesi {tahmini_sure_dk} dakikalığına kapatıldı. Tahmini yeniden açılış: {yeniden_acilis}."
    }
    publish_event_to_bus("AREA_CLOSED", {"bolge": bolge, "tahmini_sure_dk": tahmini_sure_dk, "kapatma_id": kapatma_id})
    return result

def mock_kamera_yonlendir(hedef_bolge=""):
    kamera_id = f"KAM-{random.randint(1, 24):02d}"
    result = {
        "status": "ok",
        "kamera_id": kamera_id,
        "hedef_bolge": hedef_bolge,
        "stream_url": f"rtsp://saha-kamera.local/{kamera_id.lower()}",
        "mesaj": f"{kamera_id} kamerası '{hedef_bolge}' bölgesine yönlendirildi."
    }
    publish_event_to_bus("CAMERA_REDIRECTED", {"hedef_bolge": hedef_bolge, "kamera_id": kamera_id})
    return result

def mock_vardiya_amirine_bildir(mesaj="", oncelik="normal"):
    bildirim_id = f"VRD-{datetime.now().year}-{random.randint(1000, 9999):04d}"
    result = {
        "status": "ok",
        "bildirim_id": bildirim_id,
        "iletildi_kisi": "Vardiya Amiri",
        "oncelik": oncelik,
        "mesaj": f"Bildirim ({oncelik}) vardiya amirine iletildi: \"{mesaj}\""
    }
    publish_event_to_bus("SHIFT_SUPERVISOR_NOTIFIED", {"mesaj": mesaj, "oncelik": oncelik, "bildirim_id": bildirim_id})
    return result

def mock_kkd_ihlali_raporla(kisi_sayisi=0, ihlal_tipi="baretsiz"):
    rapor_no = f"KKD-{datetime.now().year}-{random.randint(1000, 9999):04d}"
    result = {
        "status": "ok",
        "rapor_no": rapor_no,
        "kisi_sayisi": kisi_sayisi,
        "ihlal_tipi": ihlal_tipi,
        "onerilen_aksiyon": "İlgili personel sahadan uyarılacak ve KKD eğitimine yönlendirilecek.",
        "mesaj": f"{kisi_sayisi} kişi için '{ihlal_tipi}' KKD ihlali raporu oluşturuldu."
    }
    publish_event_to_bus("PPE_VIOLATION_REPORTED", {"kisi_sayisi": kisi_sayisi, "ihlal_tipi": ihlal_tipi, "rapor_no": rapor_no})
    return result

def mock_gecmis_sorgula(bolge="", gun_sayisi=7, olay_tipi=None):
    kayitlar = memory.sorgula(bolge=bolge, gun_sayisi=gun_sayisi, olay_tipi=olay_tipi)
    return {
        "status": "ok",
        "kayit_sayisi": len(kayitlar),
        "ozet": memory.ozet_cikar(kayitlar)
    }

# ============================================================
# ARAÇ KAYIT DEFTERİ (Turkce isim + calistirilabilir fonksiyon)
# ============================================================
TOOL_REGISTRY = {
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
    },
    "mock_alan_kapat": {
        "func": mock_alan_kapat,
        "description": "Belirtilen bölgeyi geçici olarak erişime kapatır.",
        "name_tr": "🚧 Alanı Kapat"
    },
    "mock_kamera_yonlendir": {
        "func": mock_kamera_yonlendir,
        "description": "En yakın sahadaki kamerayı belirtilen hedef bölgeye yönlendirir.",
        "name_tr": "🎥 Kamerayı Yönlendir"
    },
    "mock_vardiya_amirine_bildir": {
        "func": mock_vardiya_amirine_bildir,
        "description": "Vardiya amirine öncelikli bir mesaj iletir.",
        "name_tr": "👨‍✈️ Vardiya Amirine Bildir"
    },
    "mock_kkd_ihlali_raporla": {
        "func": mock_kkd_ihlali_raporla,
        "description": "Kişisel koruyucu donanım (KKD) ihlalini raporlar.",
        "name_tr": "⛑️ KKD İhlali Raporla"
    },
    "mock_gecmis_sorgula": {
        "func": mock_gecmis_sorgula,
        "description": "Bölge bazlı geçmiş olay kayıtlarını sorgular, tekrar eden örüntüleri tespit eder.",
        "name_tr": "🗂️ Geçmişi Sorgula"
    },
}

# ============================================================
# OPENAI-FORMAT TOOL ŞEMALARI (gerçek function calling için)
# ============================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "mock_saglik_ekibi_cagir",
            "description": "Yaralanma, düşme veya hareketsiz kişi tespit edildiğinde sağlık ekibini olay yerine çağırır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detay": {"type": "string", "description": "Durumun kısa açıklaması (ör. 'Forklift altında kalan işçi')."},
                    "konum": {"type": "string", "description": "Olayın gerçekleştiği saha/bölge konumu (ör. 'Depo B, Hat 3')."},
                    "aciliyet": {"type": "string", "enum": ["dusuk", "orta", "yuksek", "kritik"], "description": "Durumun aciliyet seviyesi."}
                },
                "required": ["detay", "konum", "aciliyet"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_guvenlik_alert_ver",
            "description": "Güvenlik ihlali, tehlikeli bölgeye yaklaşma veya riskli bir durumda güvenlik birimine bildirim gönderir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detay": {"type": "string", "description": "Güvenlik ihlalinin veya tehlikenin kısa açıklaması."},
                    "seviye": {"type": "string", "enum": ["bilgi", "uyari", "alarm"], "description": "Bildirimin önem seviyesi."}
                },
                "required": ["detay", "seviye"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_olay_kaydi_olustur",
            "description": "Tespit edilen bir kaza, olay veya kural ihlali için resmi bir olay kaydı oluşturur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detay": {"type": "string", "description": "Olayın kısa açıklaması."},
                    "olay_tipi": {
                        "type": "string",
                        "enum": ["kaza", "ekipman_arizasi", "kkd_ihlali", "yetkisiz_giris", "diger"],
                        "description": "Olayın kategorisi."
                    }
                },
                "required": ["detay", "olay_tipi"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_alan_kapat",
            "description": "Tehlike tespit edilen bir bölgeyi belirli bir süreliğine erişime kapatır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bolge": {"type": "string", "description": "Kapatılacak bölgenin adı/tanımı (ör. 'Depo B, Hat 3')."},
                    "tahmini_sure_dk": {"type": "integer", "description": "Bölgenin kaç dakika kapalı kalacağının tahmini süresi."}
                },
                "required": ["bolge", "tahmini_sure_dk"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_kamera_yonlendir",
            "description": "Sahadaki bir güvenlik kamerasını belirtilen hedef bölgeye yönlendirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hedef_bolge": {"type": "string", "description": "Kameranın yönlendirileceği hedef bölge."}
                },
                "required": ["hedef_bolge"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_vardiya_amirine_bildir",
            "description": "Vardiya amirine öncelikli bir metin mesajı iletir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mesaj": {"type": "string", "description": "Vardiya amirine iletilecek mesaj metni."},
                    "oncelik": {"type": "string", "enum": ["normal", "yuksek", "acil"], "description": "Mesajın öncelik derecesi."}
                },
                "required": ["mesaj", "oncelik"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_kkd_ihlali_raporla",
            "description": "Kişisel koruyucu donanım (KKD) ihlali tespit edilen kişi sayısını ve ihlal tipini raporlar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kisi_sayisi": {"type": "integer", "description": "İhlalin tespit edildiği kişi sayısı."},
                    "ihlal_tipi": {
                        "type": "string",
                        "enum": ["baretsiz", "yeleksiz", "eldivensiz", "coklu"],
                        "description": "Tespit edilen KKD ihlalinin türü."
                    }
                },
                "required": ["kisi_sayisi", "ihlal_tipi"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_gecmis_sorgula",
            "description": "Belirtilen bölgedeki geçmiş olay kayıtlarını sorgular. Tekrar eden bir ihlal/olay tipinden şüphelenildiğinde, örüntü olup olmadığını kontrol etmek için kullanılır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bolge": {"type": "string", "description": "Sorgulanacak bölge/konum adı."},
                    "gun_sayisi": {"type": "integer", "description": "Kaç günlük geçmişe bakılacağı (belirtilmezse 7)."},
                    "olay_tipi": {
                        "type": "string",
                        "enum": config.OLAY_TIPLERI,
                        "description": "Sadece belirli bir olay tipine bakmak için (opsiyonel)."
                    }
                },
                "required": ["bolge"]
            }
        }
    },
]

_SCHEMA_BY_NAME = {schema["function"]["name"]: schema for schema in TOOLS}

def get_tools_schema():
    """core.agent tarafından TOOLS listesini içeriklerini bilmeden almak için kullanılır."""
    return TOOLS

# ============================================================
# ARAÇ ÇALIŞTIRICI (ReAct döngüsünün kullanacağı dispatcher)
# ============================================================
TOOL_CALL_LOG = []

def _validate_arguments(schema, arguments):
    """Argümanları şemaya göre doğrular. Geçerliyse None, değilse hata mesajı döner."""
    if not isinstance(arguments, dict):
        return f"Argümanlar bir JSON nesnesi (obje) olmalı, alınan tür: {type(arguments).__name__}"

    properties = schema["function"]["parameters"].get("properties", {})
    required = schema["function"]["parameters"].get("required", [])

    missing = [p for p in required if arguments.get(p) in (None, "")]
    if missing:
        return f"Zorunlu parametre(ler) eksik: {', '.join(missing)}."

    for param_name, value in arguments.items():
        spec = properties.get(param_name)
        if spec is None:
            continue
        expected_type = spec.get("type")
        if expected_type == "integer" and not isinstance(value, int):
            return f"'{param_name}' parametresi tam sayı (integer) olmalı, alınan: {value!r} ({type(value).__name__})."
        if expected_type == "string" and not isinstance(value, str):
            return f"'{param_name}' parametresi metin (string) olmalı, alınan: {value!r} ({type(value).__name__})."
        enum_values = spec.get("enum")
        if enum_values and value not in enum_values:
            return f"'{param_name}' parametresi şu değerlerden biri olmalı: {', '.join(enum_values)}. Alınan: {value!r}."

    return None

def execute_tool(name, arguments=None):
    """
    Model tarafından tetiklenen bir tool_call'ı çalıştırır.
    - Bilinmeyen araç adı ya da hatalı/eksik argüman durumunda asla exception
      fırlatmaz, modelin tekrar deneyebilmesi için açıklayıcı bir hata dict'i döner.
    - Her çağrıyı (araç adı + argümanlar + sonuç) TOOL_CALL_LOG'a kaydeder.
    - Streamlit'e bağımlı değildir; headless (örn. core/benchmark.py) çalışır.
    """
    arguments = arguments if isinstance(arguments, dict) else (arguments or {})
    schema = _SCHEMA_BY_NAME.get(name)

    if schema is None:
        result = {
            "status": "error",
            "error": f"Bilinmeyen araç: '{name}'. Kullanılabilir araçlar: {', '.join(_SCHEMA_BY_NAME.keys())}"
        }
        TOOL_CALL_LOG.append({"tool": name, "arguments": arguments, "result": result, "ts": datetime.now().strftime('%H:%M:%S')})
        return result

    validation_error = _validate_arguments(schema, arguments)
    if validation_error is not None:
        result = {"status": "error", "error": validation_error}
        TOOL_CALL_LOG.append({"tool": name, "arguments": arguments, "result": result, "ts": datetime.now().strftime('%H:%M:%S')})
        return result

    func = TOOL_REGISTRY[name]["func"]
    try:
        result = func(**arguments)
    except Exception as e:
        result = {"status": "error", "error": f"'{name}' çalıştırılırken beklenmeyen hata: {e}"}

    TOOL_CALL_LOG.append({"tool": name, "arguments": arguments, "result": result, "ts": datetime.now().strftime('%H:%M:%S')})
    return result
