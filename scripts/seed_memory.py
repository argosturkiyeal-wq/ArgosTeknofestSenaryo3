import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import core.memory as memory

# (bolge, olay_tipi, gun_once, siddet, aciklama)
KAYITLAR = [
    ("Yükleme Rampası", "kkd_ihlali", 1, "orta", "Personel baretsiz malzeme taşırken görüldü"),
    ("Yükleme Rampası", "kkd_ihlali", 3, "orta", "İki işçi yeleksiz çalışıyor"),
    ("Yükleme Rampası", "kkd_ihlali", 6, "yuksek", "Baretsiz personel forklift güzergahında"),
    ("Yükleme Rampası", "kkd_ihlali", 11, "orta", "Baretsiz çalışma tespit edildi"),
    ("Yükleme Rampası", "kkd_ihlali", 14, "orta", "Eldivensiz malzeme taşıma"),
    ("Yükleme Rampası", "dusme", 2, "yuksek", "Personel rampadan kayarak düştü"),
    ("Yükleme Rampası", "arac_kazasi", 5, "kritik", "Forklift rampa kenarına çarptı"),
    ("Depo B Hat 3", "arac_kazasi", 1, "yuksek", "Forklift raf sistemine çarptı"),
    ("Depo B Hat 3", "arac_kazasi", 12, "orta", "Forklift ile personel arasında yakın temas"),
    ("Depo B Hat 3", "tehlikeli_yakinlik", 2, "orta", "Personel forklift güzergahına çok yaklaştı"),
    ("Depo B Hat 3", "tehlikeli_yakinlik", 4, "dusuk", "Yaya ve forklift aynı koridoru paylaştı"),
    ("Depo B Hat 3", "kkd_ihlali", 3, "dusuk", "Eldivensiz malzeme kontrolü"),
    ("Ana Giriş Kapısı", "yetkisiz_giris", 0, "yuksek", "Kimliksiz kişi turnikeden geçmeye çalıştı"),
    ("Ana Giriş Kapısı", "yetkisiz_giris", 6, "orta", "Refakatsiz ziyaretçi tespit edildi"),
    ("Ana Giriş Kapısı", "yetkisiz_giris", 13, "orta", "Kartsız giriş denemesi"),
    ("Ana Giriş Kapısı", "bolge_ihlali", 4, "dusuk", "Ziyaretçi yetkisiz alana yöneldi"),
    ("Ana Giriş Kapısı", "bolge_ihlali", 9, "dusuk", "Araç yanlış girişten sahaya yöneldi"),
    ("Saha Otoparkı", "personel_toplanmasi", 1, "dusuk", "Mola sırasında kalabalık oluştu"),
    ("Saha Otoparkı", "personel_toplanmasi", 8, "dusuk", "Vardiya değişiminde yoğunluk"),
    ("Saha Otoparkı", "diger", 3, "dusuk", "Park alanında sızıntı şüphesi"),
    ("Saha Otoparkı", "diger", 10, "dusuk", "Aydınlatma arızası bildirildi"),
    ("Depo A Hat 1", "kkd_ihlali", 0, "orta", "Yeleksiz personel görüldü"),
    ("Depo A Hat 1", "dusme", 7, "yuksek", "Merdivenden düşme riski"),
    ("Depo A Hat 1", "arac_kazasi", 15, "orta", "Transpalet çarpışması"),
    ("Soğuk Hava Deposu", "kkd_ihlali", 2, "orta", "Uygun ekipman olmadan girişim"),
    ("Soğuk Hava Deposu", "tehlikeli_yakinlik", 5, "dusuk", "Araç ve personel yakın çalıştı"),
    ("Soğuk Hava Deposu", "diger", 9, "dusuk", "Kapı sensör arızası"),
]


def main():
    memory.init_db()

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.execute("DELETE FROM events")
    conn.commit()
    conn.close()
    print(f"Mevcut kayıtlar temizlendi. {len(KAYITLAR)} sahte kayıt yazılıyor...\n")

    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    for idx, (bolge, olay_tipi, gun_once, siddet, aciklama) in enumerate(KAYITLAR, start=1):
        olusturma_tarihi = simdi - timedelta(days=gun_once, hours=idx % 5)
        event = {"time": "00:00", "event": aciklama, "olay_tipi": olay_tipi, "siddet": siddet}
        memory.kaydet_olaylar(f"seed_{idx:03d}", [event], bolge=bolge, olusturma_tarihi=olusturma_tarihi)

    print("Yazma tamamlandı.\n")

    # Doğrulama — tarihlerin gerçekten dağılmış olduğunu (hepsi bugüne düşmediğini) göster
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    satirlar = conn.execute(
        "SELECT bolge, olay_tipi, date(created_at) as tarih FROM events ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    print("--- DOĞRULAMA: bolge | olay_tipi | tarih ---")
    for s in satirlar:
        print(f"  {s['tarih']}  |  {s['bolge']:<22}  |  {s['olay_tipi']}")
    print(f"\nToplam {len(satirlar)} kayıt.\n")

    print("--- ÖRÜNTÜ TESTİ (Yükleme Rampası, gun_sayisi=7 vs 30) ---")
    print(" gun_sayisi=7 :", memory.ozet_cikar(memory.sorgula(bolge="Yükleme Rampası", gun_sayisi=7)))
    print(" gun_sayisi=30:", memory.ozet_cikar(memory.sorgula(bolge="Yükleme Rampası", gun_sayisi=30)))


if __name__ == "__main__":
    main()
