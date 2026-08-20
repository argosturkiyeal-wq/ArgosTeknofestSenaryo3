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

> **Not (aynı gün, sonraki iterasyon):** Yukarıdaki "başarıyla tetikledi" sonucu tek bir test run'ına dayanıyordu. Kategori listesi (`olay_tipi` seçim kuralları) eklendikten sonra aynı senaryo 4 ardışık run'ın 4'ünde de aracı tetikleyemedi — bkz. aşağıdaki iki madde. Tek run'a güvenmemek gerektiğinin kendi içindeki kanıtı bu.

---

## 2026-08-10 — "Şüphelenirsen sorgula" yerine zorunlu adım sırası: 0/4 → 8/8

**Problem:** "Geçmiş örüntü kontrolü" talimatı, `olay_tipi` kategori listesi eklenip prompt uzadıktan sonra hiç tetiklenmez oldu — 4 ardışık test run'ının 4'ünde de `mock_gecmis_sorgula` çağrılmadı (model 8-9 başka aracı sırayla çağırıp hafızayı hiç sorgulamadan bitiriyordu).

**Kök neden:** Talimat KOŞULLUYDU — modelden "tekrar eden bir ihlal tipinden şüphelendiğinde" gibi bir muhakeme adımı istiyordu. Prompt kısaydı ilk denemede bu iş görmüştü, ama araya somut bir kategori listesi girip prompt uzayınca (JSON format bloğuyla yeni kategori listesi arasında sıkışan) bu koşullu/örtük kural etkisini kaybetti; model somut, listelenmiş kurallara (olay_tipi seçimi) öncelik verdi.

**Çözüm:** Koşulu kaldırıp numaralı, zorunlu bir adım sırasına çevirdim: "1. olay_tipi'ni belirle, 2. bu tiplerden biriyse DİĞER ARAÇLARI ÇAĞIRMADAN ÖNCE sorgula, 3. sonucu summary'de belirtmek ZORUNLU, 4. sonra diğer araçları çağır." Mekanik, muhakeme gerektirmeyen bir tetikleyiciye çevirmek 8 ardışık run'ın 8'inde de çalıştı.

**Neden önemli:** Somut, ölçülmüş kanıt: LLM'lere "gerektiğinde yap" tarzı örtük/koşullu talimatlar vermek — özellikle prompt büyüdükçe — güvenilir değil. "Ne zaman yapacağına sen karar ver" yerine "şu koşulda, şu sırayla yap" vermek ölçülebilir şekilde daha güvenilir (0/4 → 8/8).

---

## 2026-08-10 — Model kendi çarpıtılmış özetine göre tutarlı davranıyor (açık sorun)

**Problem:** Aynı test senaryosunda ("forklift ani manevra yaptı, işçi dengesini kaybedip yere düştü") final JSON'daki `event` metni ısrarla "Forklift altında kalan işçi" oluyor — orijinal gözlemdeki "düştü" fiili kayboluyor, sonuç olarak `olay_tipi` de `dusme` yerine `diger`e düşüyor.

**Denenen çözüm:** "event metni gözlemdeki ifadeyi yeniden yazmasın, sadece kısaltsın — somut fiilleri kaybetme" talimatı eklendi, "diger seçmeden önce ayırmayı dene" kuralı güçlendirildi. 4 run'lık testte net bir iyileşme görülmedi (1/4 doğru sınıflandı; talimat öncesi ölçümde 2/4'tü) — örneklem küçük olduğu için istatistiksel olarak kesin bir şey söylenemez, ama kesinlikle "çözüldü" de denemez.

**Gözlemlenen olası kök neden:** Sorun final JSON üretim aşamasında değil, çok daha erken — model, gözlemi İLK araç çağrısını yaparken (`mock_saglik_ekibi_cagir`'in `detay` argümanı) zaten "Forklift altında kalan işçi" diye çerçeveliyor, final JSON bu erken çerçevelemeyi tekrar ediyor. Yani **model kendi çarpıtılmış özetine göre tutarlı davranıyor — çarpıtma orijinal veriden ilk adımda kopuyor** ve final JSON talimatı bu noktaya hiç dokunmuyor.

**Durum:** Açık. Üçüncü bir iterasyon (talimatı ilk araç çağrısı aşamasına da yaymak, ya da genel bir "gözlem detaylarını her adımda koru" kuralı eklemek) planlanan ama şimdilik ertelenen bir sonraki adım.

---

## 2026-08-10 — Prompt uzunluğu ve talimat önceliği

**Gözlem:** Bugünkü iki iterasyon aynı kalıbı gösterdi: sistem promptuna yeni bir kural (kategori listesi) eklemek, ondan önce eklenmiş başka bir kuralın (geçmiş sorgulama tetikleyicisi) etkisini zayıflattı — kural hâlâ promptta duruyordu ama modelin davranışını artık yönlendirmiyordu. Sorunu çözen şey kuralı taşımak değil, onu **koşullu bir muhakeme adımından mekanik bir sıraya** çevirmekti.

**Çıkarım:** Prompt büyüdükçe bu tür "talimat aşınması" riski artacak — bugün iki kuralı (geçmiş sorgulama + olay_tipi seçimi) yerleştirebildik, ama üçüncü, dördüncü kural eklendikçe aynı sorun muhtemelen tekrar çıkacak. Bunu şimdi kalıcı olarak çözmüyoruz (örn. daha yapılandırılmış bir prompt şablonu, kuralları ayrı bir doğrulama/post-processing katmanına taşımak gibi seçenekler ileride değerlendirilebilir) — bilerek erteliyoruz, farkındalığı buraya not düşüyoruz.

**Neden önemli:** Bu, "prompt engineering" bileşeninin tek seferlik bir yazım işi değil, sürüm arttıkça yönetilmesi gereken, ölçülmesi gereken bir mühendislik yükü olduğunun somut kanıtı — jürinin ayrı bir bileşen olarak değerlendirdiği bir konuda değerli bir gözlem.


---

## 2026-08-20 — Tracker ID sürekliliği düşme anında kırılıyor, "yatay + hareketsiz" kombinasyonu kaçıyor

**Problem:** Zamansal analiz katmanı (`core/tracking.py`, N7-N10) gerçek bir "kayıp düşme" videosuyla (`adult-man-slips-and-falls-on-ice...`) test edildi. Sistem kişinin düştüğünü ve uzun süre hareketsiz kaldığını doğru tespit etti (`kisi#403 son 3.0 sn'dir hareketsiz`), ve düşüş anına yakın bir karede "yatay konumda" sinyali de üretildi. Ama tasarımın hedeflediği kritik kombinasyon — aynı kişi için **aynı anda** hem yatay hem 3sn+ hareketsiz — hiç tetiklenmedi.

**Kök neden:** Ultralytics'in yerleşik tracker'ı (ByteTrack, `persist=True`), düşme anındaki hızlı hareket ve kısmi kapanma (occlusion) nedeniyle aynı fiziksel kişiyi kaybedip yeniden algıladığında **yeni bir `track_id` atıyor**. Bu videoda aynı kişi 24 saniye içinde 5 farklı ID aldı: `kisi#5 → #79 → #368 → #403 → #422`. `is_still()` her track_id için ayrı bir geçmiş penceresi tutuyor (N7 tasarımı gereği - track'ler arası kimlik eşleştirmesi yok), yani ID her değiştiğinde 3 saniyelik hareketsizlik gözlemi sıfırdan başlıyor. "Yatay" sinyali bir ID altında (`#422`) tetiklendi, "3sn+ hareketsiz" onayı ise farklı bir ID altında (`#403`) geldi — ikisi hiçbir zaman aynı track_id + aynı an için birleşmedi.

**Neden düzeltilmedi (bilinçli tercih):** N7 talimatı açıkça "Ultralytics'in yerleşik tracker'ı yeterli, kendi IoU eşleştirmemizi yazma" diyordu. Track ID'ler arası kimlik sürekliliğini (re-identification / eski ID ile yeni ID'yi "aynı kişi" olarak birleştirme) kendi başımıza çözmek, tracker'ın üstüne ayrı bir eşleştirme katmanı yazmak anlamına gelir — kapsam dışı bırakıldı, ölçülmüş bir sınırlama olarak burada belgeleniyor.

**Neden önemli:** Bu, "ölçülebilir gözlem üret, yorumu VLM'e bırak" tasarım ilkesinin (bkz. `core/tracking.py` docstring) kendi içindeki bir gerilimi gösteriyor: ölçüm zinciri (track kimliği) kırılırsa, doğru ölçülmüş iki ayrı gözlem (yatay VE hareketsiz) birleşip anlamlı bir sinyale dönüşemiyor. Kısa vadeli hafifletme zaten kodda var: `SignalThrottle` spam'i önlüyor ve state-transition'da anında yayın yapıyor, ama ID sürekliliği sorununu çözmüyor. Kalıcı çözüm (basit bir mesafe/IoU tabanlı "track_id yeniden bağlama" katmanı ya da her track_id için ayrı ayrı üretilen sinyallerin VLM'e "muhtemelen aynı kişi" notuyla birlikte verilmesi) planlanan ama şimdilik ertelenen bir sonraki adım.
