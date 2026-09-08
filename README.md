# Canlı Spor Kanalları

Çeşitli spor yayın platformlarını tarayıp **doğrulanmış** bir M3U/JSON kanal
listesi üreten bot + web oynatıcı.

## Neden bazı kanallar çalışmıyordu? (Eylül 2026 denetimi)

Bu projedeki asıl düşman **domain/yayın sunucusu rotasyonu**: paneller haftada,
checklist yayın sunucuları ise saatler içinde değişiyor. Bu yüzden "liste
geliyor ama oynatmıyor" sorunları yaşanıyordu. Denetimde bulunan kök nedenler
ve kalıcı çözümler:

| # | Sorun | Çözüm |
|---|-------|-------|
| 1 | **Hiç doğrulama yoktu** — ölü linkler listeye yazılıyordu | Her yayın indirilip HLS imzası, varyant ve **ilk segment** kontrol ediliyor |
| 2 | **~110 kayıt yayın değil, web sayfasıydı** (`event.html?id=`, `/channel?id=`) | Bu siteler geziliyor, yalnızca gerçek `.m3u8` kaydediliyor |
| 3 | **Tarayıcı `Referer`/`Origin`/`User-Agent` gönderemez** → hotlink korumalı yayınlar 403 | Header enjekte eden [Cloudflare Worker proxy](worker/) |
| 4 | **CORS** başlığı olmayan sunucularda hls.js manifesti okuyamıyordu | Aynı proxy permissive CORS ekliyor + m3u8 alt adreslerini yeniden yazıyor |
| 5 | Aynı kanal 8 kaynakta ayrı ayrı listeleniyordu | Kanallar birleştirilip **otomatik yedek kaynak** (failover) veriliyor |
| 6 | **Checklist sunucusu tek koda gömülüydü** — sunucu ölünce 205 Netspor kanalı birden öldü | Sunucular artık panel sayfalarından + **son başarılı listeden (channels.json)** keşfediliyor, canlılık testi sonrası kullanılıyor |
| 7 | **Domain aralıkları bayatlıyordu** — `netsporco5.xyz` yok, `netsporcoamp23.xyz` var | `FAMILIES` tablosu: bilinen **seed** adresler + geniş numara aralıkları; ayrıca panellerin **"GÜNCEL ADRESİMİZ"** duyuruları takip ediliyor, sayfalardaki aile domainleri **hasat** ediliyor, **yönlendirilen son adres** kullanılıyor |
| 8 | **GitHub Actions'tan hiçbir site açılmıyordu** — python-requests'in TLS parmak izi bot korumasına takılıyordu | `curl_cffi` ile **Chrome parmak izi** taklidi (`IMPERSONATE=1`, kurulu değilse otomatik requests'e düşer) |
| 9 | **İş akışı bozulmayı gizliyordu** — liste üretilemese bile "success" görünüyordu | Build başarısızsa koşu artık **kırmızı** biter |
| 10 | **`channels.json` hiç commit edilmedi** — workflow gitignore'lu `health_report.json`'u `git add`'lemeye çalışıyordu | Yalnızca `Canli_Spor_Hepsi.m3u` + `channels.json` commit edilir; site boş liste gösteremez |
| 11 | Sabit worker kanallarının origin'i Cloudflare'den engellenince blok sayfası "yayın" gibi listelendi | Doğrulama katmanı HLS imzası görmeyen her şeyi eler |
| 12 | Kaynak siteler akışı artık **JS ile yüklediği** için sayfa HTML'inde m3u8 görünmüyordu | Bot harici `<script src>` dosyalarını da tarıyor; ayrıca **günlük güncellenen topluluk M3U listeleri** (`Kral-Turk` vb.) kaynak olarak ekleniyor — girdi başına User-Agent/Referer bilgisi de olduğu gibi alınıyor |

### Topluluk listeleri

`sources.py` varsayılan olarak şu listeleri okur (env ile değiştirilebilir):

```
COMMUNITY_M3U="https://.../TURK_TV.m3u_plus,https://.../Kral-Sport.m3u_plus" python main.py
```

Bu listeler checklist yayın sunucularının (andro.XYZ/checklist/...) en güncel
adreslerini taşır; bot hem bunları kanal olarak doğrulayıp listesine ekler hem
de **checklist sunucu keşfine ipucu** olarak kullanır.

## Domain bakımı (domainler değişince ne yapmalı?)

Bot çoğu değişimi kendi halleder: seed adresler panellerin "GÜNCEL ADRESİMİZ"
duyurusunu ve sayfa içi aile linklerini takip eder. Yine de kaynak tamamen
yer değiştirdiyse `sources.py` içindeki `FAMILIES` tablosunu güncelleyin:

```python
"mahsun": {
    "label": "Mahsun Sports",
    "seeds": ["https://mahsunsports.xyz"],      # <- bilinen guncel adres
    "patterns": [("https://mahsunsports{}.xyz", range(1, 220))],
    "signature": ("event.html", "androstreamlive", "mahsun"),
},
```

- `seeds`: yeni adresi öğrendiyseniz buraya ekleyin (ilk bunlar denenir).
- `signature`: sayfanın bu aileye ait olduğunu gösteren kelimeler.
- Bulunan her sayfadaki durum `health_report.json` içindeki `families`
  alanına yazılır — hangi kaynağın nerede takıldığını oradan görün.

## Yapı

```
main.py       Akış: topla -> normalize et -> doğrula -> birleştir -> yaz
core.py       HTTP oturumu (curl_cffi impersonation dahil), m3u8 keşfi,
              doğrulama, kanal normalizasyonu, çıktı
sources.py    Kaynak toplayıcılar + domain/checklist keşif katmanı (FAMILIES)
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
| `IMPERSONATE` | `1` | Chrome TLS parmak izi taklidi (curl_cffi gerekir; yoksa requests kullanılır) |

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
