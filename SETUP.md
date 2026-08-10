# Kurulum Kılavuzu — TEKNOFEST 2026 Senaryo 3

**Video Analiz ve Operasyonel Karar Destek Ajanı**

Bu proje **%100 yerel/offline** çalışır. Video analizini yapan görsel dil modeli (Qwen3-VL) sizin kendi bilgisayarınızda `llama-server` ile çalışır; hiçbir bulut servisine, hiçbir API anahtarına ihtiyaç yoktur. İnternet sadece kurulum aşamasında (programları ve model dosyalarını indirmek için) gerekir.

Bu yüzden kurulumun büyük kısmı "birkaç Python paketi kur" değil, **"kendi model sunucunuzu bilgisayarınızda ayağa kaldır"** ile ilgilidir. Sabırlı olun; ilk kurulum uzun sürer (özellikle derleme ve model indirme adımları), ama bir kez kurulunca sonrası hızlıdır.

> **Bu kılavuz kimin için?** Daha önce hiç llama.cpp derlememiş, GGUF nedir bilmeyen, "model nereden indirilir" diye takılan biri de baştan sona takılmadan bitirebilsin diye yazıldı. Her adımda ne yaptığınız ve neden yaptığınız açıklandı.

---

## Kaç adım var, ne kadar sürer?

| Adım | Ne yapılıyor | Yaklaşık süre |
|------|-------------|---------------|
| 0 | Ön gereksinimleri kurma (Python, Git, derleyici, CUDA...) | 30–60 dk |
| 1 | Projeyi indirme | 1 dk |
| 2 | Python ortamı + paketler | 5 dk |
| 3 | ffmpeg | 5 dk |
| 4 | llama.cpp'yi derleme | 20–60 dk (bilgisayara göre) |
| 5 | Model dosyalarını indirme (~6 GB) | 10–30 dk (internete göre) |
| 6 | Ayar dosyası (.env) | 5 dk |
| 7 | Model sunucusunu başlatma | 1 dk |
| 8 | Uygulamayı başlatma | 1 dk |

Toplam: makinenize ve internetinize göre **1.5–3 saat** civarı. Çoğu bekleme (indirme/derleme), aktif iş az.

---

## 0) Ön gereksinimler — önce bunları kurun

Aşağıdakiler kurulu değilse ilerleyen adımlarda "komut tanınmıyor" hatası alırsınız. Şimdi kurun ki sonra durmayın.

### 0.1 — Python 3.10 veya üstü

1. [python.org/downloads](https://www.python.org/downloads/) adresine gidin, **Download Python** butonuna basıp indirin (3.11 veya 3.12 önerilir).
2. İndirdiğiniz kurulumu açın. **Kurulumun ilk ekranında en alttaki `Add python.exe to PATH` kutusunu MUTLAKA işaretleyin.** Bunu atlarsanız `python` komutu çalışmaz.
3. `Install Now` deyin.

**Kontrol:** Yeni bir PowerShell açıp şunu yazın:
```powershell
python --version
```
`Python 3.11.x` gibi bir çıktı görmelisiniz.

> **"Python was not found; run without arguments to install from the Microsoft Store" hatası mı alıyorsunuz?** Bu, Windows'un sahte bir kısayolu araya sokmasından olur. Çözüm: `Ayarlar → Uygulamalar → Gelişmiş uygulama ayarları → Uygulama yürütme diğer adları` yolunu açın, `python.exe` ve `python3.exe` anahtarlarını **kapatın**, PowerShell'i kapatıp yeniden açın. Alternatif olarak `python` yerine `py` komutunu kullanabilirsiniz (`py --version`).

### 0.2 — Git

1. [git-scm.com/download/win](https://git-scm.com/download/win) → 64-bit installer'ı indirin.
2. Kurulumda her şeyi varsayılan bırakabilirsiniz, `Next → Next → Install`.

**Kontrol:**
```powershell
git --version
```

### 0.3 — CMake

llama.cpp'yi derlemek için gerekli.

1. [cmake.org/download](https://cmake.org/download/) → **Binary distributions** bölümünden **Windows x64 Installer** satırındaki `.msi` dosyasını indirin (örn. `cmake-x.x.x-windows-x86_64.msi`). "Source" olanları DEĞİL, "Binary" olanı alın.
2. Kurulum sırasında **`Add CMake to the system PATH for all users`** seçeneğini işaretleyin. Bunu atlarsanız `cmake` komutu tanınmaz.

**Kontrol** (PowerShell'i yeniden açtıktan sonra):
```powershell
cmake --version
```

### 0.4 — Visual Studio Build Tools (C++ derleyicisi)

llama.cpp C++ ile yazılmıştır; derlemek için Microsoft'un C++ derleyicisi gerekir. Sadece "Build Tools" kurmak yetmez, **içindeki C++ iş yükünü de seçmeniz** şarttır.

1. [visualstudio.microsoft.com/downloads](https://visualstudio.microsoft.com/downloads/) → sayfada aşağı inip **"Tools for Visual Studio"** başlığı altında **Build Tools for Visual Studio** (en güncel sürüm) → Download.
2. İndirdiğiniz installer'ı çalıştırın. Açılan **Workloads** ekranında şu kutuyu işaretleyin:
   - ☑ **Desktop development with C++**
3. Sağdaki özet panelinde varsayılan bileşenler (MSVC derleyici + Windows SDK) yeterli. `Install` deyin. İndirme büyüktür (~6–8 GB).

**Kontrol** — hangi Build Tools sürümünün kurulu olduğunu öğrenmek için:
```powershell
& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -products * -property catalog_productLineVersion
```
Çıkan sayı (ör. `17` = VS 2022, `18` = VS 2026) **4. adımda derleme komutunda lazım olacak**, not edin.

> **Zaten kurdum ama yine "could not find any instance of Visual Studio" hatası alıyorum:** Muhtemelen "Desktop development with C++" iş yükünü seçmeden kurmuşsunuz. Başlat menüsünde **Visual Studio Installer**'ı açın → kurulu ürünün yanındaki **Modify** → o kutuyu işaretleyip tekrar kurun.

### 0.5 — CUDA Toolkit (NVIDIA ekran kartınız varsa — şiddetle önerilir)

GPU olmadan model çok yavaş çalışır. NVIDIA kartınız varsa CUDA kurun.

1. Önce sürücünüzün ve GPU'nuzun durumunu görün:
   ```powershell
   nvidia-smi
   ```
   Bir tablo çıkıp GPU adını (ör. `RTX 3060`), sürücü sürümünü ve VRAM'i (ör. `6144 MiB`) gösteriyorsa sürücünüz var. **VRAM miktarını not edin — 6. ve 7. adımda ayar seçimini bu belirler.** Komut hiç çalışmıyorsa önce [NVIDIA sürücüsü](https://www.nvidia.com/Download/index.aspx) kurun.
2. [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads) → Windows → x86_64 → sürümünüz → `exe (local)` → indirip kurun (~2–3 GB). Kurulumda "Express" seçeneği yeterli.

**Kontrol** (PowerShell'i yeniden açtıktan sonra):
```powershell
nvcc --version
```

> **Önemli sıra:** CUDA'yı **Build Tools'tan SONRA** kurun. CUDA installer, Visual Studio entegrasyonunu kurulum sırasında ekler; VS önce kurulu olursa bu daha sorunsuz olur.

---

## 1) Projeyi indirme (klonlama)

Projeyi koymak istediğiniz klasöre gidin (örnekte kullanıcı klasörü altında `projects`), sonra klonlayın:

```powershell
cd $HOME
mkdir projects -Force
cd projects
git clone https://gitlab.com/argosturkiyeai/repo.git
cd repo
git checkout feature/agent
```

> `main` branch'i de güncel; ama aktif geliştirme `feature/agent` üzerinde. Yukarıdaki `git checkout feature/agent` ile o branch'e geçmiş olursunuz.

Artık proje klasörünün içindesiniz. Bundan sonraki tüm komutlar (belirtilmedikçe) bu klasörden çalıştırılır.

---

## 2) Python sanal ortamı ve paketler

Sanal ortam (venv), projenin paketlerini bilgisayarınızın geri kalanından ayrı tutar. Proje klasörünün içinde oluşturun:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Aktifleştiğinde komut satırının başında `(venv)` yazısını görürsünüz. Sonra paketleri kurun:

```powershell
pip install -r requirements.txt
```

> **`Activate.ps1 ... betik çalıştırma devre dışı` hatası mı?** PowerShell güvenlik politikası engelliyordur. Şunu bir kez çalıştırın: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` → `Y` → sonra tekrar aktive edin.

> Not: Bu venv **sadece bu proje için**. Bir sonraki adımdaki llama.cpp'nin venv ile hiçbir ilgisi yok; o ayrı bir C++ programı, ayrı klasörde derlenir.

---

## 3) ffmpeg (video işlemek için)

Video kesme ve kare çıkarma için ffmpeg gerekir.

```powershell
winget install --id Gyan.FFmpeg -e
```

Kurulumdan sonra **yeni bir PowerShell penceresi açın** (PATH değişikliği mevcut pencereye yansımaz). Kontrol:

```powershell
ffmpeg -version
```

> `winget` yoksa veya çalışmazsa: [ffmpeg.org/download.html](https://ffmpeg.org/download.html) → Windows build → indirip bir klasöre çıkarın; ya klasörün `bin` yolunu Windows PATH'ine ekleyin, ya da 6. adımdaki `.env` dosyasında `FFMPEG_BINARY` değişkenine `ffmpeg.exe`'nin tam yolunu yazın.

---

## 4) llama.cpp'yi indirme ve derleme

Bu, video modelini çalıştıracak sunucu programını (`llama-server.exe`) üretme adımıdır. **Projeden ayrı bir klasöre** kurun — projenin içine değil.

### 4.1 — İndir

```powershell
cd $HOME
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
```

Artık `C:\Users\<kullanıcı>\llama.cpp` içindesiniz.

### 4.2 — Derle

GPU'nuz (CUDA) varsa:

```powershell
cmake -B build -G "Visual Studio 18 2026" -DGGML_CUDA=ON
cmake --build build --config Release
```

> **`"Visual Studio 18 2026"` kısmını kendi sürümünüze göre yazın.** 0.4'te not ettiğiniz sayı 17 ise `"Visual Studio 17 2022"`, 18 ise `"Visual Studio 18 2026"` yazın. Emin değilseniz kurulu generator adlarını görmek için: `cmake --help` çıktısının sonundaki "Generators" listesine bakın ve VS satırını birebir kopyalayın.

GPU'nuz yoksa (sadece CPU) `-DGGML_CUDA=ON` kısmını çıkarın:
```powershell
cmake -B build -G "Visual Studio 18 2026"
cmake --build build --config Release
```

Derleme uzun sürer (20–60 dk). Ekranda `warning` satırları akması **normaldir**, sorun değil — sadece `error` görürseniz durun. CUDA'lı derlemede `mmq-instance-...`, `fattn-...` gibi dosyalarda uzun süre beklemek normaldir; **kesmeyin**, devam ediyor.

### 4.3 — Başarıyı doğrula

```powershell
Test-Path "$HOME\llama.cpp\build\bin\Release\llama-server.exe"
```
`True` dönerse derleme tamamdır. Bu dosyanın tam yolunu not edin, 7. adımda lazım.

> **Sık karşılaşılan hatalar:**
> - **`generator ... Does not match the generator used previously`** → Önceki başarısız denemeden kalan `build` klasörünü silin: `Remove-Item -Recurse -Force build` → sonra doğru `-G` ile tekrar deneyin.
> - **`CMAKE_C_COMPILER not set` / `nmake ... no such file`** → C++ derleyicisi yok veya generator belirtilmemiş. 0.4'ü tamamlayın ve `-G "Visual Studio ..."` eklediğinizden emin olun.
> - **`CUDA Toolkit not found`** → 0.5'i atlamışsınız. CUDA'yı kurun, ya da geçici olarak CPU derlemesi (`-DGGML_CUDA=ON` olmadan) yapın.

---

## 5) Model dosyalarını indirme

İki dosya gerekiyor. İkisi de **Qwen'in resmi Hugging Face reposundan** indirilir:

**Repo:** https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/tree/main

Sayfada **"Files and versions"** listesinden şu iki dosyayı, her birinin yanındaki indirme (aşağı ok) ikonuna basarak indirin:

1. **Ana model** — VRAM'inize göre birini seçin:
   - **`Qwen3VL-8B-Instruct-Q4_K_M.gguf`** (~5 GB) → **6–8 GB VRAM için bunu seçin.** Önerilen.
   - `Qwen3VL-8B-Instruct-Q8_0.gguf` (~8.7 GB) → daha yüksek kalite, ama 8 GB VRAM'e GPU'da tam sığmaz; düşük VRAM'de çok yavaş çalışır. Sadece kalite karşılaştırması için indirin.
2. **Vision (görüntü) dosyası — mmproj:**
   - **`mmproj-Qwen3VL-8B-Instruct-F16.gguf`** (~1.16 GB) → modelin görüntüyü "görmesini" sağlayan dosya. **Bu şart**, hangi kuantizasyonu seçerseniz seçin aynı mmproj dosyası kullanılır.

Her iki dosyayı da llama.cpp klasörünüzün altındaki `models` klasörüne koyun:
```powershell
# klasör yoksa:
mkdir "$HOME\llama.cpp\models" -Force
# indirdiğiniz .gguf dosyalarını buraya taşıyın
```

> **Komut satırından indirmeyi tercih ederseniz** (opsiyonel):
> ```powershell
> pip install -U huggingface_hub
> hf download Qwen/Qwen3-VL-8B-Instruct-GGUF `
>   --include "Qwen3VL-8B-Instruct-Q4_K_M.gguf" "mmproj-Qwen3VL-8B-Instruct-F16.gguf" `
>   --local-dir "$HOME\llama.cpp\models"
> ```

**Kontrol** — büyük dosyaların geldiğini görün:
```powershell
Get-ChildItem "$HOME\llama.cpp\models\*.gguf" | Where-Object {$_.Length -gt 100MB} | Select-Object Name, @{N='GB';E={[math]::Round($_.Length/1GB,2)}}
```
İki dosyanızı (ana model + mmproj) görmelisiniz.

> **Kuantizasyon (Q4 / Q8) nedir?** Modelin ağırlıklarını daha az bit ile saklayıp dosyayı küçültme işlemidir. Q8 = 8 bit (orijinale daha yakın, daha büyük, daha yavaş), Q4 = 4 bit (daha küçük, daha hızlı, kalitede küçük düşüş). 6 GB VRAM'de pratik olan Q4_K_M'dir.

---

## 6) `.env` ayar dosyası

Proje, model dosyalarınızın yerini `.env` dosyasından okur. Proje klasöründe:

```powershell
copy .env.example .env
```

`.env` dosyasını bir metin düzenleyiciyle açın ve şu iki satırı **kendi gerçek yollarınızla** doldurun:

```ini
MODEL_PATH=C:\Users\<kullanıcı>\llama.cpp\models\Qwen3VL-8B-Instruct-Q4_K_M.gguf
MMPROJ_PATH=C:\Users\<kullanıcı>\llama.cpp\models\mmproj-Qwen3VL-8B-Instruct-F16.gguf
```

`<kullanıcı>` yerine kendi Windows kullanıcı adınızı yazın. Geri kalan ayarların makul varsayılanları vardır (`config.py`'da), dokunmasanız da çalışır.

> ffmpeg'i PATH'e ekleyemediyseniz, bu dosyaya `FFMPEG_BINARY=C:\...\ffmpeg.exe` satırını da ekleyin.

---

## 7) Model sunucusunu başlatma

**Ayrı bir PowerShell penceresinde** çalıştırın; bu pencere uygulama açık olduğu sürece **açık kalmalı** (sunucu burada çalışır).

Aşağıdaki komut **6 GB VRAM (örn. RTX 3060 Laptop)** için ayarlanmış, güvenli başlangıç değerleridir:

```powershell
& "$HOME\llama.cpp\build\bin\Release\llama-server.exe" `
  -m "C:\Users\<kullanıcı>\llama.cpp\models\Qwen3VL-8B-Instruct-Q4_K_M.gguf" `
  --mmproj "C:\Users\<kullanıcı>\llama.cpp\models\mmproj-Qwen3VL-8B-Instruct-F16.gguf" `
  --host 127.0.0.1 `
  --port 8080 `
  -c 8192 `
  -ub 512 `
  -np 1 `
  -ngl 20 `
  -fa 1 `
  --jinja
```

Parametrelerin anlamı ve VRAM'e göre ayarlama:
- `-ngl 20` → modelin kaç katmanının GPU'ya yükleneceği. **VRAM'iniz yetmezse ("CUDA out of memory") bunu düşürün:** 20 → 16 → 12 → 8. Düştükçe kalan katmanlar CPU'ya kayar (yavaşlar ama çalışır). VRAM'de bol boşluk varsa artırabilirsiniz.
- `-c 8192` → bağlam (context) uzunluğu. Bellek yetmezse 8192 → 4096 yapın.
- `-ub 512`, `-np 1` → düşük VRAM için küçük tutuldu.
- **`--jinja` ZORUNLU.** Bu bayrak olmadan model araç çağırma (tool-calling) yapamaz, ReAct döngüsü sessizce bozulur. En kolay unutulan ama en kritik ayar.

Terminalde şu satırı görünce hazırdır:
```
main: server is listening on http://127.0.0.1:8080
```

**Doğrulama:** Başka bir pencerede `nvidia-smi` çalıştırın; `llama-server.exe` süreç listesinde görünmeli ve VRAM kullanımı (ör. ~5100 / 6144 MiB) modelin GPU'ya yüklendiğini gösterir. Tarayıcıda `http://127.0.0.1:8080` açılırsa sunucu ayakta demektir.

> **Q8 denemek isterseniz** (düşük VRAM'de yavaş olur): `-m` yolunu Q8 dosyasına değiştirin ve `-ngl 20` yerine `-ngl 8` (hatta daha düşük), `-c 4096` kullanın. Tüm video yerine tek kare / hızlı testle kalite karşılaştırması için mantıklıdır; canlı demo için Q4_K_M'de kalın. Q8 için sistem RAM'inizin en az 16 GB olması gerekir.

---

## 8) Uygulamayı başlatma

Sunucuyu **kapatmadan**, proje klasöründe (venv aktifken) **yeni bir PowerShell** açıp:

```powershell
cd $HOME\projects\repo
.\venv\Scripts\Activate.ps1
streamlit run ui/app.py
```

Tarayıcıda otomatik açılır (genelde `http://localhost:8501`). Sol üstte **"🟢 Model Sunucusu Aktif"** yazıyorsa her şey doğru bağlanmış demektir. Sol menüden ayarları yapıp bir video yükleyerek analizi başlatabilirsiniz.

---

## Hızlı test (video olmadan)

Video işlemeyi atlayıp doğrudan araç çağırma zincirini (ReAct döngüsü) saniyeler içinde test etmek için:

```powershell
python scripts\test_react.py
```

Hardcoded kısa bir gözlem metniyle modelin araçları nasıl zincirlediğini gösterir. Sunucu doğru kurulduysa (özellikle `--jinja` açıksa) burada araç çağrılarının çalıştığını görürsünüz — kurulumu test etmenin en hızlı yolu budur.

---

## İlk çalıştırma için ipuçları

- **Kısa videoyla başlayın** (10–20 sn). 6 GB VRAM + Q4'te kare başına birkaç saniye sürer; uzun video ilk denemede gereksiz bekletir.
- **Kare örnekleme modunu "Adaptif" seçin.** v2'nin asıl avantajı budur: durağan kareleri eleyip görsel token sayısını azaltır, hız artar.
- **Model çıktısını videoyla karşılaştırın.** Küçük/kuantize bir model bazen olmayan şey uydurabilir (hallucination). Yakaladığı ve kaçırdığı olayları not almak, TEKNOFEST hata analizi için değerli veridir.

---

## Sorun giderme (özet)

| Belirti | Sebep / Çözüm |
|---|---|
| `python was not found` | PATH'e eklenmemiş veya Store kısayolu araya giriyor → 0.1'deki nota bakın |
| `cmake ... not recognized` | CMake PATH'te değil → 0.3, kurulumda "Add to PATH" seçilmeli, PowerShell'i yeniden açın |
| `could not find any instance of Visual Studio` | C++ iş yükü kurulmamış → 0.4, "Desktop development with C++" seçin |
| `CUDA Toolkit not found` | CUDA kurulu değil → 0.5, ya da geçici olarak CPU derlemesi yapın |
| `generator ... Does not match` | Eski `build` klasörü kalmış → `Remove-Item -Recurse -Force build` sonra tekrar derleyin |
| `❌ Model Sunucusu Çevrimdışı` | `llama-server` çalışmıyor ya da `.env`'deki adres yanlış → 7. adımı kontrol edin, sunucu ayrı pencerede açık olmalı |
| `CUDA out of memory` (sunucu açılırken) | VRAM yetersiz → `-ngl` ve `-c` değerlerini düşürün |
| `FileNotFoundError: [WinError 2]` (video kesme) | ffmpeg PATH'te değil → yeni terminal, olmazsa `.env`'de `FFMPEG_BINARY` |
| Araç çağırma / ReAct çalışmıyor | `--jinja` bayrağını eklemeyi unutmuşsunuz → 7. adım |
| Türkçe karakterler bozuk (terminal testinde) | `Invoke-RestMethod` ile elle test ederken body'yi UTF-8 byte'a çevirin; uygulamayı etkilemez |
| "Model çıktısı JSON ayrıştırılamadı" | Nadiren model bozuk JSON üretir; `json_repair` çoğunu onarır, kalanı "Ham Model Çıktısı" panelinden görün |
| Uzun videoda zaman aşımı | `.env`'de `REACT_REQUEST_TIMEOUT` değerini yükseltin (varsayılan 120s) |
