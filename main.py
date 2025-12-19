import requests
import re
import datetime
from bs4 import BeautifulSoup

# --- GENEL AYARLAR ---
OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# --- 1. NETSPOR: KANALLAR (Düz) VE GÜNÜN MAÇLARI (Ters) ---
def fetch_netspor():
    print("[*] Netspor taranıyor...")
    channels_list = []
    matches_list = []
    
    source_url = "https://netspor-amp.xyz/"
    stream_base = "https://andro.6441255.xyz/checklist/"
    
    try:
        res = requests.get(source_url, headers=HEADERS, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # A) Önce Sabit Kanalları Çek (BeIN Sports 1, 2, 3... sırasıyla)
        channel_container = soup.find('div', id='kontrolPanelKanallar')
        if channel_container:
            for div in channel_container.find_all('div', class_='mac', option=True):
                sid = div['option']
                title = div.find('div', class_='match-takimlar').get_text(strip=True)
                channels_list.append({
                    "name": title,
                    "url": f"{stream_base}{sid}.m3u8",
                    "group": "CANLI TV KANALLARI",
                    "ref": source_url,
                    "logo": ""
                })

        # B) Sonra Günün Maçlarını Çek (Kendi içinde ters çevirerek)
        match_container = soup.find('div', id='kontrolPanel')
        if match_container:
            for div in match_container.find_all('div', class_='mac', option=True):
                sid = div['option']
                title = div.find('div', class_='match-takimlar').get_text(strip=True)
                # Saat ve Lig bilgisini al
                alt_info = div.find('div', class_='match-alt').get_text(" | ", strip=True) if div.find('div', class_='match-alt') else ""
                
                matches_list.append({
                    "name": f"{title} ({alt_info})",
                    "url": f"{stream_base}{sid}.m3u8",
                    "group": "Günün Maçları",
                    "ref": source_url,
                    "logo": ""
                })
                
    except Exception as e:
        print(f"Netspor hatası: {e}")
    
    # ÖNEMLİ: Kanallar 1,2,3... diye gider, Maçlar güncel olsun diye kendi içinde ters çevrilir.
    return channels_list + list(reversed(matches_list))

# --- 2. TRGOALS FONKSİYONU ---
def fetch_trgoals():
    print("[*] Trgoals taranıyor...")
    results = []
    base_prefix = "https://trgoals"
    domain = None
    for i in range(1485, 2150):
        test = f"{base_prefix}{i}.xyz"
        try:
            if requests.head(test, timeout=1).status_code == 200:
                domain = test; break
        except: continue
    
    if domain:
        # BeIN kanallarını burada da sırasıyla çekiyoruz
        cids = {"yayin1":"BEIN 1","yayinb2":"BEIN 2","yayinb3":"BEIN 3","yayinb4":"BEIN 4","yayinb5":"BEIN 5","yayinss":"S SPORT","yayint1":"TIVIBU 1"}
        for cid, name in cids.items():
            try:
                r = requests.get(f"{domain}/channel.html?id={cid}", headers=HEADERS, timeout=5)
                m = re.search(r'const baseurl = "(.*?)"', r.text)
                if m:
                    results.append({
                        "name": f"TRG - {name}", 
                        "url": f"{m.group(1)}{cid}.m3u8", 
                        "group": "TRGOALS TV", 
                        "ref": f"{domain}/", 
                        "logo": "https://i.ibb.co/gFyFDdDN/trgoals.jpg"
                    })
            except: continue
    return results

# --- 3. SELÇUKSPOR / SPORCAFE FONKSİYONU ---
def fetch_selcuk_sporcafe():
    print("[*] Selçukspor / Sporcafe taranıyor...")
    results = []
    selcuk_channels = [
        {"id": "selcukbeinsports1", "name": "BeIN Sports 1", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/5rhmw31628798883.png"},
        {"id": "selcukbeinsports2", "name": "BeIN Sports 2", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/7uv6x71628799003.png"},
        {"id": "selcukbeinsports3", "name": "BeIN Sports 3", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/u3117i1628798857.png"},
        {"id": "selcukbeinsports4", "name": "BeIN Sports 4", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/2ktmcp1628798841.png"},
        {"id": "selcukbeinsports5", "name": "BeIN Sports 5", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/BeIn_Sports_5_US.png"},
        {"id": "selcuktivibuspor1", "name": "Tivibu Spor 1", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/qadnsi1642604437.png"},
        {"id": "selcukssport", "name": "S Sport 1", "logo": "https://itv224226.tmp.tivibu.com.tr:6430/images/poster/20230302923239.png"}
    ]

    working_html, referer = None, None
    for i in range(6, 130):
        url = f"https://www.sporcafe{i}.xyz/"
        try:
            res = requests.get(url, headers=HEADERS, timeout=1)
            if res.status_code == 200 and "uxsyplayer" in res.text:
                working_html, referer = res.text, url
                break
        except: continue
    
    if working_html:
        s_match = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', working_html)
        if s_match:
            stream_domain = f"https://{s_match.group(1)}"
            for ch in selcuk_channels:
                try:
                    r = requests.get(f"{stream_domain}/index.php?id={ch['id']}", headers={**HEADERS, "Referer": referer}, timeout=5)
                    base = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', r.text)
                    if base:
                        results.append({
                            "name": f"SL - {ch['name']}", 
                            "url": f"{base.group(1)}{ch['id']}/playlist.m3u8", 
                            "group": "SELÇUKSPOR HD", 
                            "ref": referer, 
                            "logo": ch['logo']
                        })
                except: continue
    return results

# --- ANA ÇALIŞTIRICI ---
def main():
    all_streams = []
    
    # Önce ana kanallar gelsin (BeIN Sports 1, 2, 3...)
    # fetch_netspor artık kanalları en başa alacak şekilde ayarlandı
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_trgoals())
    all_streams.extend(fetch_selcuk_sporcafe())
    
    if not all_streams:
        print("Hata: Yayın bulunamadı.")
        return

    content = "#EXTM3U\n"
    content += f"# Birlesik Spor Paketi - Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    
    for s in all_streams:
        logo = f' tvg-logo="{s["logo"]}"' if s["logo"] else ""
        content += f'#EXTINF:-1 group-title="{s["group"]}"{logo},{s["name"]}\n'
        content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'{s["url"]}\n'

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[BASARILI] Sıralama düzeltildi, {len(all_streams)} kanal kaydedildi.")

if __name__ == "__main__":
    main()
