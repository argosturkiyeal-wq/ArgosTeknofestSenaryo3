import sqlite3
import logging
from datetime import datetime, timedelta, timezone

import config

logger = logging.getLogger(__name__)

DB_PATH = str(config.DB_PATH)

_OLAY_TIPI_ANAHTAR_KELIMELER = {
    "kkd_ihlali": ["baretsiz", "yeleksiz", "eldivensiz", "kkd"],
    "dusme": ["düş", "kaybet", "kaybed"],
    "arac_kazasi": ["forklift", "araç", "çarp", "devril"],
    "tehlikeli_yakinlik": ["tehlikeli yakınlık", "yakın mesafe"],
    "bolge_ihlali": ["bölge ihlali", "sınır ihlali"],
    "yetkisiz_giris": ["yetkisiz", "izinsiz giriş"],
    "personel_toplanmasi": ["personel topla", "kalabalık"],
}

def _siniflandir(aciklama):
    metin = (aciklama or "").lower()
    for olay_tipi, kelimeler in _OLAY_TIPI_ANAHTAR_KELIMELER.items():
        if any(kelime in metin for kelime in kelimeler):
            return olay_tipi
    return "diger"

def _simdi_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _parse_created_at(deger):
    return datetime.strptime(deger, "%Y-%m-%d %H:%M:%S")

def _normalize_bolge(bolge):
    """'Yükleme Rampası' / 'yükleme rampası ' gibi yazım farklarının ayrı bölge
    olarak sayılmaması için lowercase+trim uygular. Farklı isimlendirmeleri
    (ör. 'rampa' vs 'yükleme rampası') ayırt etmez — bölge sistemi (poligon
    tabanlı) geldiğinde bu heuristik gereksizleşecek."""
    return bolge.strip().lower() if isinstance(bolge, str) and bolge.strip() else None

def init_db():
    """Idempotent — tablo/index zaten varsa hiçbir şey yapmaz."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                olay_zamani TEXT,
                olay_tipi TEXT NOT NULL,
                bolge TEXT,
                siddet TEXT,
                aciklama TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bolge_tarih ON events(bolge, created_at)")
        conn.commit()
    finally:
        conn.close()

def kaydet_olaylar(video_id, events, bolge=None, olusturma_tarihi=None):
    """
    analiz sonucundaki events listesini ({"time":..., "event":...} formatında)
    yazar. olay_tipi SADECE event'te açıkça verilmemişse aciklama metninden
    basit anahtar kelime eşleşmesiyle tahmin edilir (fallback; bulunamazsa
    "diger"). Ajan artık final JSON'da olay_tipi'ni doğrudan ürettiği için
    (bkz. REACT_SYSTEM_PROMPT) bu, pratikte nadiren devreye girer.
    Her event kendi "bolge"sini taşıyabilir, taşımıyorsa fonksiyona verilen
    bolge kullanılır. olusturma_tarihi verilmezse "şimdi" kullanılır — geçmişe
    tarihlenmiş test verisi yazmak için (bkz. scripts/seed_memory.py) verilebilir.
    """
    if not events:
        return 0

    if olusturma_tarihi is None:
        created_at = _simdi_utc().strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(olusturma_tarihi, datetime):
        created_at = olusturma_tarihi.strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_at = olusturma_tarihi

    conn = sqlite3.connect(DB_PATH)
    try:
        yazilan = 0
        for event in events:
            if not isinstance(event, dict):
                continue
            aciklama = event.get("event") or event.get("aciklama") or ""
            olay_tipi = event.get("olay_tipi") or _siniflandir(aciklama)
            event_bolge = _normalize_bolge(event.get("bolge") or bolge)
            conn.execute(
                "INSERT INTO events (video_id, olay_zamani, olay_tipi, bolge, siddet, aciklama, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (video_id, event.get("time"), olay_tipi, event_bolge, event.get("siddet"), aciklama, created_at)
            )
            yazilan += 1
        conn.commit()
        return yazilan
    finally:
        conn.close()

def sorgula(bolge=None, gun_sayisi=7, olay_tipi=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        esik = (_simdi_utc() - timedelta(days=gun_sayisi)).strftime("%Y-%m-%d %H:%M:%S")
        sorgu = "SELECT * FROM events WHERE created_at >= ?"
        parametreler = [esik]

        bolge_normalized = _normalize_bolge(bolge)
        if bolge_normalized:
            sorgu += " AND bolge = ?"
            parametreler.append(bolge_normalized)
        if olay_tipi:
            sorgu += " AND olay_tipi = ?"
            parametreler.append(olay_tipi)

        sorgu += " ORDER BY created_at DESC"
        satirlar = conn.execute(sorgu, parametreler).fetchall()
        return [dict(satir) for satir in satirlar]
    finally:
        conn.close()

def ozet_cikar(kayitlar):
    """Ham satırları değil, modele verilecek okunabilir Türkçe bir özet döndürür."""
    if not kayitlar:
        return "Belirtilen kriterlere uyan geçmiş kayıt bulunamadı."

    tip_sayaci = {}
    bolgeler = set()
    for kayit in kayitlar:
        tip = kayit.get("olay_tipi") or "diger"
        tip_sayaci[tip] = tip_sayaci.get(tip, 0) + 1
        if kayit.get("bolge"):
            bolgeler.add(kayit["bolge"])

    tip_metni = ", ".join(
        f"{sayi} {tip.replace('_', ' ')}"
        for tip, sayi in sorted(tip_sayaci.items(), key=lambda x: -x[1])
    )
    bolge_metni = f"{next(iter(bolgeler))} bölgesinde " if len(bolgeler) == 1 else ""

    tarihler = [_parse_created_at(k["created_at"]) for k in kayitlar if k.get("created_at")]
    simdi = _simdi_utc()
    ozet = f"{bolge_metni}{tip_metni} kayıtlı."

    if tarihler:
        en_eski_gun = max((simdi - min(tarihler)).days, 1)
        en_son_gun = (simdi - max(tarihler)).days
        ozet = f"Son {en_eski_gun} günde {bolge_metni}{tip_metni} kayıtlı."
        ozet += " En son olay bugün kaydedildi." if en_son_gun == 0 else f" En son olay {en_son_gun} gün önce."

    return ozet

init_db()
