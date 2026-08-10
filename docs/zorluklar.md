# Karşılaşılan Zorluklar ve Çözümler

Bu dosya, geliştirme sürecinde karşılaşılan teknik zorlukları ve bunlara getirilen çözümleri sıcağı sıcağına kaydeder — şartname Bölüm 6'nın istediği "karşılaşılan zorluklar ve bu zorluklara getirilen çözümler" dokümantasyon kalemi için birincil kaynak.

---

## 2026-08-10 — Türkçe'nin eklemeli yapısı, anahtar kelime eşleşmesini kırıyor

**Problem:** Hafıza katmanının (`core/memory.py`) olay sınıflandırması, event açıklamalarında basit anahtar kelime aramasıyla (`"dengesini kaybet" in metin`) `olay_tipi` tahmin ediyordu. Test sırasında "İşçilerden biri dengesini kaybedip yere düştü" cümlesi `"diger"` olarak sınıflandı — oysa açıkça bir düşme (`dusme`) olayıydı.

**Kök neden:** Türkçe eklemeli bir dil; fiil kökü aynı kalırken çekim ekiyle birlikte yüzey formu değişiyor (`kaybet-mek` → `kaybed-ip`, `kaybet-ti`, `kaybed-erek`). Anahtar kelimem tam çekimli bir ifadeydi (`"dengesini kaybet"`), metindeki çekimli hal (`"kaybedip"`) bunun alt dizesi değildi. İngilizce gibi eklemeli olmayan bir dilde bu sınıf hata neredeyse hiç görülmez — substring eşleşmesi orada çoğu zaman yeterlidir.

**Çözüm (kısa vadeli):** Anahtar kelimeleri tam ifadeler yerine kısa köklere indirdim (`"dengesini kaybet"` → ayrı ayrı `"kaybet"` + `"kaybed"`, `"yere düş"` → `"düş"`). Bu, ünsüz yumuşaması (t→d) gibi yaygın çekim kalıplarını da kapsıyor.

**Asıl çözüm (uygulandı):** Kök-kelime yaklaşımı yine de kırılgan — Türkçe'nin tüm çekim uzayını anahtar kelime listesiyle kapsamak mümkün değil. Gerçek çözüm sınıflandırmayı modele devretmekti: ReAct sistem promptu artık final JSON'daki her `event` nesnesi için modelin doğrudan `olay_tipi` üretmesini ve `config.OLAY_TIPLERI`'den seçim yapmasını istiyor. Model olayı zaten anlamsal olarak yorumlamış durumda; anahtar kelime eşleşmesi artık sadece modelin bu alanı doldurmadığı nadir durumlar için bir fallback.

**Neden önemli:** Bu, İngilizce merkezli basit string/regex eşleştirme kalıplarının Türkçe'de neden genellikle yetersiz kaldığının somut, tekrar üretilebilir bir örneği — Türkçe Doğal Dil İşleme bağlamında karşılaşılan gerçek bir dil-özgü problem ve buna verilen bilinçli mühendislik cevabı.

---

## 2026-08-10 — Ajan yeni aracı çağırmıyor: kod değil, prompt sorunu

**Problem:** 8. araç (`mock_gecmis_sorgula`, hafıza sorgulama) eklendikten sonra ajan, KKD ihlali içeren bir test senaryosunda 8 farklı aracı sırayla çağırdı ama hafızayı hiç sorgulamadı — kabul kriteri karşılanmadı.

**Kök neden:** Sistem promptundaki tetikleyici soyuttu: "tekrar eden bir ihlal tipinden şüphelendiğinde sorgula." Model, aynı videoda art arda gelen iki KKD ihlalini (baretsiz + yeleksiz) zaten "tekrar" olarak görüp bunun sistemdeki kalıcı geçmişe (farklı videolar/analizler arası) değil, bu videonun kendi içine işaret ettiğini varsaymış olabilir — "geçmiş" kelimesi promptta yeterince netleştirilmemişti.

**Çözüm:** İki değişiklik yapıldı: (1) "Geçmiş kayıtlar bu videodan DEĞİL, sistemde saklı önceki analizlerden gelir; bu videonun kendi içinde tekrar 'geçmiş örüntü' sayılmaz" diye açıkça ayrıştırıldı, (2) soyut "şüphelenirsen" tetikleyicisi yerine somut, olay-tipi bazlı bir kural kondu: `config.OLAY_TIPLERI`'deki kategorilerden birine giren bir olay tespit edildiğinde, ilgili diğer araçları çağırmadan ÖNCE hafıza sorgulanacak. Değişiklik sonrası aynı test senaryosu aracı doğru şekilde tetikledi (`mock_gecmis_sorgula(bolge="Yükleme Rampası", olay_tipi="dusme")`) ve sonucu final özete taşıdı.

**Neden önemli:** Kodun kendisi (dispatcher, şema, dedup guard) baştan doğru çalışıyordu — sorun hiç exception ya da mantık hatası değildi, salt model davranışıydı. Bu, "agent, tools, memory, prompt engineering" bileşenlerinin gerçekten birbirine bağımlı olduğunun ve prompt engineering'in kod kadar test edilmesi/iterasyonlanması gereken bir bileşen olduğunun somut kanıtı.
