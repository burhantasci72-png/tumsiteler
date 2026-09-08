# Canlı Spor Kanalları

Çeşitli spor yayın platformlarını tarayıp **doğrulanmış** bir M3U/JSON kanal
listesi üreten bot + web oynatıcı.

## Neden bazı kanallar çalışmıyordu?

Eski sürümdeki temel sorunlar ve çözümleri:

| # | Sorun | Çözüm |
|---|-------|-------|
| 1 | **Hiç doğrulama yoktu** — ölü linkler listeye yazılıyordu | Her yayın indirilip HLS imzası, varyant ve **ilk segment** kontrol ediliyor |
| 2 | **~110 kayıt yayın değil, web sayfasıydı** (`event.html?id=`, `/channel?id=`) — hiçbir oynatıcı açamaz | Bu siteler artık geziliyor ve yalnızca gerçek `.m3u8` kaydediliyor |
| 3 | **Tarayıcı `Referer`/`Origin`/`User-Agent` gönderemez** (forbidden headers) → hotlink korumalı yayınlar 403 | Header enjekte eden [Cloudflare Worker proxy](worker/) |
| 4 | **CORS** başlığı olmayan sunucularda hls.js manifesti okuyamıyordu | Aynı proxy permissive CORS ekliyor + m3u8 içindeki tüm alt adresleri yeniden yazıyor |
| 5 | İnadına TV'de **31 kanalın hepsine aynı URL** veriliyordu (`id` kullanılmıyordu) | Düzeltildi |
| 6 | Aynı kanal 8 kaynakta ayrı ayrı listeleniyor, biri ölünce çare yok | Kanallar birleştirilip **otomatik yedek kaynak** (failover) veriliyor |
| 7 | Bot boş liste üretse bile commit ediyordu | Az/boş sonuçta mevcut liste **korunuyor** |
| 8 | `.gitignore` markdown ``` içinde olduğu için çalışmıyordu | Düzeltildi |

## Yapı

```
main.py       Akış: topla -> normalize et -> doğrula -> birleştir -> yaz
core.py       HTTP oturumu, m3u8 keşfi, doğrulama, kanal normalizasyonu, çıktı
sources.py    Kaynak toplayıcılar (her biri izole; biri çökerse diğerleri sürer)
index.html    Web arayüzü + yerleşik HLS oynatıcı
worker/       Cloudflare Worker HLS proxy (header enjeksiyonu + CORS)
tests/        Birim + entegrasyon testleri (ağ erişimi gerektirmez)
tools/        Sahte HLS sunucusu (test altyapısı)
```

### Üretilen dosyalar

- `Canli_Spor_Hepsi.m3u` — VLC / Kodi / TiviMate için (header etiketleriyle)
- `channels.json` — web oynatıcı için; **yedek linkler** dahil
- `health_report.json` — kaynak bazlı başarı oranı ve hata nedenleri

## Oynatıcı katmanları

Web oynatıcı bir kanalı açarken sırayla dener:

1. **hls.js** (MSE) — masaüstü + Android
2. **Yerel HLS** — Safari / iOS
3. **Yedek kaynaklar** — aynı kanalın diğer sitelerdeki linkleri
4. **iframe** — m3u8 değilse veya hepsi başarısızsa

Her mantıksal kaynak için **önce proxy'li, sonra doğrudan** deneme yapılır;
yani 2 kaynaklı bir kanalda 4 deneme hakkı olur. Her yedek **kendi
`Referer`'ını** taşır (farklı siteler farklı Referer ister).

Ayrıca: ağır hata kurtarma, buffer takılma kurtarma (canlıya geri yakalama),
otomatik yeniden bağlanma, PiP ve tam ekran.

## Çalıştırma

```bash
pip install requests beautifulsoup4 urllib3
python main.py
```

### Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `VALIDATE` | `1` | Yayın doğrulamasını aç/kapa |
| `VALIDATE_SEGMENT` | `1` | Segment seviyesinde de kontrol et |
| `KEEP_UNVERIFIED` | `0` | Doğrulanamayanları da listeye yaz |
| `PLAYER_PROXY` | — | HLS proxy adresi (tarayıcı oynatma için) |
| `ONLY` | — | Sadece belirli kaynakları tara (`ONLY=netspor,andro`) |
| `VALIDATE_WORKERS` | `40` | Paralel doğrulama sayısı |

### Testler

```bash
python -m unittest discover -s tests -v
```

## Proxy kurulumu

Hotlink korumalı kanalların **tarayıcıda** açılması için proxy gerekir.
İki yolu var:

### A) Otomatik (önerilen)

Depoya iki secret ekleyin — gerisini GitHub Actions halleder:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Nereden alınır |
|--------|----------------|
| `CLOUDFLARE_API_TOKEN` | Cloudflare → My Profile → API Tokens → Create Token → **"Edit Cloudflare Workers"** şablonu |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Dashboard sağ sütun → Account ID |

Sonra **Actions → "HLS Proxy Dagit" → Run workflow**. Bu iş akışı:

1. Worker'ı Cloudflare'e dağıtır
2. `/health` ile canlı olduğunu doğrular
3. Adresi `PLAYER_PROXY` değişkenine **otomatik yazar**

Bundan sonra liste her güncellendiğinde proxy adresi `channels.json` içine
gömülür ve site onu kendiliğinden kullanır — elle ayar gerekmez.

### B) Elle

```bash
cd worker && npx wrangler deploy
```

Çıkan adresi sitedeki **kalkan simgesine** tıklayıp yapıştırın (tarayıcınıza
kaydedilir), veya `PLAYER_PROXY` değişkenine ekleyin.

### Proxy olmadan ne olur?

- **VLC / Kodi / TiviMate:** sorunsuz çalışır (M3U header etiketleri sayesinde)
- **Tarayıcı:** yalnızca hotlink koruması olmayan kanallar açılır

Oynatıcı her kaynağı **önce proxy'li, sonra doğrudan** dener; yani proxy
kapalıysa veya kotası dolduysa yayın yine de açılmaya çalışılır.
