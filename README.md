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

| 13 | **AtomSpor / Selçukspor / beIN MAX 2 listede yoktu** — Atom'un panel sayfası Actions'tan Cloudflare'e takılıyor, Selçuk'un seed adresleri yalnızca "giriş" sayfası; ayrıca `.m3u8` içermeyen **çözücü** adresler (`workers.dev/?ID=kanal` → 302 → m3u8) doğrulayıcı tarafından "sayfa" sanılıp eleniyordu | Repo içinde **`seeds.m3u`** (bilinen kalıcı adresler; her koşuda diğerleri gibi doğrulanır), AtomSpor için **worker çözücü yedeği**, Selçuk için giriş sayfasından asıl siteye geçiş; doğrulayıcı artık çözücü adresleri indirip gerçekten HLS dönüyorsa kabul ediyor ve segmentleri **yönlendirme sonrası** adrese göre çözüyor. Oynatıcı/proxy de aynı adresleri HLS sayar |

## Kategori düzeni (temiz + sıralı liste)

Liste artık kaynak sitenin grup adını (`NETSPOR`, `TR ULUSAL-UHD`, `ATOM SPOR`)
değil, **kanalın kendi kategorisini** taşır. Kategoriler sabit bir öncelik
sırasıyla yazılır — **beIN Sports her zaman ilk kategoridir**:

| # | Kategori | İçerik |
|---|----------|--------|
| 1 | `BEIN SPORTS` | beIN Sports 1-5, Max 1-2, Haber, 4K |
| 2 | `S SPORT` | S Sport 1-2, S Sport Plus |
| 3 | `TİVİBU SPOR` | Tivibu Spor 1-4 |
| 4 | `TRT SPOR` | TRT Spor, TRT Spor Yıldız, TRT 1 |
| 5 | `TABİİ SPOR` | Tabii Spor 1-7 |
| 6 | `DİĞER SPOR KANALLARI` | Smart Spor, Eurosport, A Spor, FB TV, GS TV ... |
| 7 | `CANLI MAÇLAR` | maç yayınları (saate göre sıralı) |

Aynı kanal birden fazla sitede bulunduğunda tek kartta birleştirilir; en hızlı
doğrulanmış kaynak birincil olur, diğerleri **yedek** olarak arkasına yazılır.
Yani "beIN Sports 1" kartı açılmazsa Atom → Selçuk → Netspor sırayla denenir.

**Spor dışı temizlik:** topluluk listeleri çocuk/haber/ulusal kanalları da
taşıdığı için liste kirleniyordu. `core.filter_publishable()` bu kayıtları
(grup adı + kanal adına bakarak) doğrulama öncesinde eler; maç yayınları ve
spor kanalları her zaman korunur.

### Sabit tohum listesi (`seeds.m3u`)

Otomatik keşfin kaçırdığı ama bilinen adresler için repo kökünde `seeds.m3u`
tutulur. Bot bunu her koşuda **bir kaynak gibi** okur: girdiler doğrudan
listeye yazılmaz, diğer kaynaklarla aynı doğrulamadan (playlist + segment)
geçer; ölü olanlar düşer. İçindeki `checklist` sunucuları ayrıca
Andro/Netspor sunucu keşfine ipucu olur.

Yeni bir adres eklemek için:

```
#EXTINF:-1 group-title="ATOM SPOR",beIN Sports Max 2
#EXTVLCOPT:http-referrer=https://www.atomsportv514.top
https://tv.atomspor.workers.dev/?ID=bein-sports-max-2
```

Kurallar: yalnızca `.m3u8` **veya m3u8'e yönlenen** adres (sayfa linki değil);
Referer gerekiyorsa `#EXTVLCOPT:http-referrer=` satırı. Dosya yolu `SEEDS_FILE`
ortam değişkeniyle değiştirilebilir.

### Topluluk listeleri

`sources.py` varsayılan olarak şu listeleri okur (env ile değiştirilebilir):

```
COMMUNITY_M3U="https://.../TURK_TV.m3u_plus,https://.../Kral-Sport.m3u_plus" python main.py
```

Bu listeler checklist yayın sunucularının (andro.XYZ/checklist/...) en güncel
adreslerini taşır; bot hem bunları kanal olarak doğrulayıp listesine ekler hem
de **checklist sunucu keşfine ipucu** olarak kullanır.

### Yeni nesil paneller (AtomSpor / Selçukspor)

Bu iki aile artık numaralı kimlikler yerine **slug** kullanıyor
(`/matches?id=bein-sports-1`, `/izle/bein-sports-max-1`) ve yayını sayfa
yüklendikten sonra JS ile getiriyor. Toplayıcılar bu yüzden üç katmanlı:

1. **Kanal keşfi** — ana sayfadaki bağlantılar taranır; slug'ı kanonik bir
   kanala çevrilebilenler (`bein-sports-1` → beIN Sports 1) kanal, çevrilemeyen
   maç sayfaları (`aek-atina-lask-linz`) elenir.
2. **Sayfa tarama** — kanal sayfası, iframe'leri ve harici `<script>` dosyaları
   `extract_m3u8()` ile taranır.
3. **Çözücü (resolver) adayları** — panelin JS'inde geçen `*.workers.dev`
   adresleri ile bilinen çözücü (`ATOM_WORKER`) `?ID=<slug>` ile denenir.
   Bunlar `302 → gerçek m3u8` döndürür; doğrulama katmanı HLS dönmeyenleri
   eler, yani panel Cloudflare'e takılsa bile kanal listede kalır.

Selçukspor ayrıca eski nesil `uxsyplayer` yolunu da dener (hâlâ yayın veren
sunucular var), böylece iki panel nesli aynı anda desteklenir.

Domain tamamen değişirse `FAMILIES["atom"]` / `FAMILIES["selcuk"]` içindeki
`seeds` listesine yeni adresi ekleyin; **tohum adresler numara taramasından
önce** denendiği için tek satırlık güncelleme yeterli olur.

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
