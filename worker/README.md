# HLS Proxy (Cloudflare Worker)

## Neden gerekli?

Tarayicida `fetch`/`XHR` ile `Referer`, `Origin` ve `User-Agent` basliklarini
**ayarlayamazsiniz** - bunlar "forbidden header names" listesindedir. Spor
yayin sunucularinin cogu hotlink korumasi icin tam olarak bu basliklari
kontrol eder ve eksikse `403` doner.

Ayrica bu sunucular `Access-Control-Allow-Origin` gondermedigi icin
hls.js manifesti okuyamaz.

Bu worker her iki sorunu da cozer ve m3u8 icindeki tum alt adresleri
(segment, AES anahtari, init parcasi, varyant playlist) kendi uzerinden
gececek sekilde yeniden yazar.

## Dagitim

```bash
cd worker
npx wrangler deploy
```

## Kullanim

```
https://<worker>.workers.dev/hls?url=<m3u8>&ref=<referer>&ua=<user-agent>
```

Liste uretirken:

```bash
PLAYER_PROXY=https://<worker>.workers.dev python3 main.py
```
