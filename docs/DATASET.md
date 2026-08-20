# Veri Setleri ve Model Eğitim Bilgileri

Bu dosya, algı hattında (`core/detection.py`) kullanılan YOLO modellerinin eğitildiği veri setlerini, eğitim parametrelerini ve elde edilen metrikleri belgeler — şartname kapsamındaki tekrar üretilebilirlik gerekliliği için birincil kaynaktır.

---

## SH17 (KKD tespiti — 17 sınıf)

**Model dosyası:** `model/sh17.pt`
**Sınıflar (17):** person, head, face, glasses, face-mask, face-guard, ear, ear-mufs, hands, gloves, foot, shoes, safety-vest, tool, helmet, medical-suit, safety-suit

Bu model harici olarak (SH17 veri seti üzerinde eğitilmiş, hazır ağırlık olarak) temin edildi; bu projede yeniden eğitilmedi. Kendi eğitim parametreleri/metrikleri elimizde olduğunda bu bölüm güncellenecek.

---

## Forklift (tek sınıf: forklift)

**Model dosyası:** `model/forklift.pt`
**Sınıf:** `forklift` (tek sınıf)

### Veri seti
- **Kaynak:** Roboflow — [`forklift-detection-koqxi`](https://universe.roboflow.com/) veri seti, **v2**
- **Lisans:** CC BY 4.0 — atıf gereklidir, orijinal veri seti sahibine ve Roboflow'a atıfta bulunulmalıdır

### Eğitim parametreleri
| Parametre | Değer |
|---|---|
| Mimari | YOLOv8n |
| Epoch | 30 |
| Görüntü boyutu (imgsz) | 640 |
| Batch size | 32 |

### Sonuçlar
| Metrik | Değer |
|---|---|
| mAP50 | 0.991 |
| mAP50-95 | 0.861 |
| Precision | 0.995 |
| Recall | 0.971 |
| Çıkarım hızı | 1.4 ms (SH17 modeli: 15.7 ms — ek maliyet ihmal edilebilir) |

### Algı hattına entegrasyon
`core/detection.py` içindeki `detect_frame()`, `config.YOLO_MODEL_PATHS` ve `config.YOLO_MODEL_CONF` üzerinden bu modeli `sh17` ile birlikte çalıştırır. Forklift modelinin yüksek precision'ı (0.995) nedeniyle güven eşiği diğer sınıflara göre daha yüksek tutuldu: `FORKLIFT_CONF_THRESHOLD = 0.40` (bkz. `config.py`, `.env` ile override edilebilir).

---

## Not: Ağırlık dosyaları

`model/` klasöründeki tüm `.pt` dosyaları `.gitignore` ile hariç tutulur — ağırlıklar repoya girmez, sadece bu dosyadaki eğitim bilgisi ve `config.py`'deki yol/eşik tanımları versiyonlanır. Modeli yeniden üretmek için yukarıdaki veri seti + parametrelerle eğitim tekrarlanmalıdır.
