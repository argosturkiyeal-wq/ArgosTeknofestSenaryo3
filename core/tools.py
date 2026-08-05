import json
from datetime import datetime

import streamlit as st

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
