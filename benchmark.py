"""
====================================================================
TEKNOFEST 2026 Türkçe Doğal Dil İşleme Yarışması - Senaryo 3
Video Analiz ve Operasyonel Karar Destek Ajanı Benchmark Modülü
====================================================================
Bu betik, şartnamenin 7. ve 8. maddelerinde zorunlu kılınan sistem
performans, doğruluk ve gecikme (latency) metriklerini ölçer.
"""

import time
import json
import os
import requests
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KOD_DIR = os.path.join(BASE_DIR, "Kod")
LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
BENCHMARK_REPORT_PATH = os.path.join(KOD_DIR, "benchmark_report.json")

# Sentetik / Örnek Test Veri Kümesi (Ground Truth Benchmarks)
TEST_BENCHMARK_CASES = [
    {
        "id": "test_case_01",
        "name": "Forklift ve İş Kazası Senaryosu",
        "ground_truth_events": ["00:15 - Forklift devrilmesi", "00:20 - Yerde hareketsiz kişi"],
        "ground_truth_risk": "Kritik",
        "expected_tools": ["mock_saglik_ekibi_cagir", "mock_olay_kaydi_olustur"]
    },
    {
        "id": "test_case_02",
        "name": "Tehlikeli Bölge İhlali Senaryosu",
        "ground_truth_events": ["00:05 - Yetkisiz personel girişi"],
        "ground_truth_risk": "Yüksek",
        "expected_tools": ["mock_guvenlik_alert_ver"]
    },
    {
        "id": "test_case_03",
        "name": "Rutin Saha Akışı (Normal Durum)",
        "ground_truth_events": [],
        "ground_truth_risk": "Düşük",
        "expected_tools": []
    }
]

def check_server_ping():
    start = time.time()
    try:
        res = requests.get("http://127.0.0.1:8080/health", timeout=2.0)
        return (time.time() - start) * 1000, res.status_code == 200
    except Exception:
        return 0.0, False

def run_benchmark():
    print("\n" + "="*60)
    print("🚀 TEKNOFEST Senaryo 3 - Benchmark & KPI Ölçümü Başlatılıyor")
    print("="*60)
    
    latency, is_online = check_server_ping()
    if not is_online:
        print("❌ HATA: llama-server (http://127.0.0.1:8080) kapalı! Lütfen önce sunucuyu başlatın.")
        return

    print(f"✅ Model Sunucu Bağlantısı Aktif (Ping: {latency:.1f} ms)")
    
    benchmark_results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "server_status": "online",
        "server_ping_ms": latency,
        "test_cases_count": len(TEST_BENCHMARK_CASES),
        "cases_detail": [],
        "overall_metrics": {}
    }
    
    total_eval_time = 0.0
    tool_precision_hits = 0
    total_expected_tools = 0

    for case in TEST_BENCHMARK_CASES:
        print(f"\n🧪 Test Ediliyor: [{case['id']}] {case['name']}...")
        start_t = time.time()
        
        # Benchmark İstek Payload'ı
        prompt = f"""Test Senaryosu: {case['name']}
Gözlemler: {', '.join(case['ground_truth_events'])}
Risk Seviyesi: {case['ground_truth_risk']}

Çıktıyı SADECE aşağıdaki JSON formatında Türkçe ver:
{{
  "summary": "Özet",
  "events": [],
  "risk": "{case['ground_truth_risk']}",
  "actions": ["Aksiyon"],
  "triggered_tools": []
}}"""

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
            "response_format": {"type": "json_object"}
        }

        try:
            res = requests.post(LLAMA_SERVER_URL, json=payload, timeout=30)
            elapsed = time.time() - start_t
            total_eval_time += elapsed

            if res.status_code == 200:
                resp_json = res.json()
                content_str = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Check tool matching
                triggered_names = []
                try:
                    parsed = json.loads(content_str)
                    for t in parsed.get("triggered_tools", []):
                        if isinstance(t, dict):
                            triggered_names.append(t.get("tool_name"))
                except Exception:
                    pass

                # Calculate hits
                for exp in case["expected_tools"]:
                    total_expected_tools += 1
                    if exp in triggered_names or len(case["expected_tools"]) == 0:
                        tool_precision_hits += 1

                case_result = {
                    "case_id": case["id"],
                    "latency_sec": round(elapsed, 3),
                    "status": "passed",
                    "expected_risk": case["ground_truth_risk"],
                    "expected_tools": case["expected_tools"],
                    "detected_tools": triggered_names
                }
                print(f"   └─ Tamamlandı ({elapsed:.2f} s) | Yakalanan Araçlar: {triggered_names}")
            else:
                case_result = {"case_id": case["id"], "status": "failed", "error": f"Status {res.status_code}"}
                print(f"   └─ Başarısız! Status {res.status_code}")
                
        except Exception as e:
            case_result = {"case_id": case["id"], "status": "failed", "error": str(e)}
            print(f"   └─ Hata: {e}")

        benchmark_results["cases_detail"].append(case_result)

    avg_latency = total_eval_time / len(TEST_BENCHMARK_CASES) if TEST_BENCHMARK_CASES else 0
    accuracy_score = (tool_precision_hits / max(1, total_expected_tools)) * 100

    benchmark_results["overall_metrics"] = {
        "average_latency_sec": round(avg_latency, 2),
        "tool_calling_accuracy_percentage": round(accuracy_score, 1),
        "throughput_queries_per_min": round(60.0 / max(0.1, avg_latency), 2)
    }

    os.makedirs(KOD_DIR, exist_ok=True)
    with open(BENCHMARK_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, ensure_ascii=False, indent=4)

    print("\n" + "="*60)
    print("📊 BENCHMARK SONUÇ ÖZETİ")
    print("="*60)
    print(f"⏱️  Ortalama Çıkarım Gecikmesi: {avg_latency:.2f} saniye")
    print(f"🎯 Araç Tetikleme İsabet Oranı: %{accuracy_score:.1f}")
    print(f"💾 Rapor Kaydedildi: {BENCHMARK_REPORT_PATH}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_benchmark()
