import requests
import re
import datetime
from bs4 import BeautifulSoup

# --- GENEL AYARLAR ---
OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# --- 1. NETSPOR FONKSİYONU ---
def fetch_netspor():
    print("[*] Netspor taranıyor...")
    results = []
    source_url = "https://netspor-amp.xyz/"
    stream_base = "https://andro.6441255.xyz/checklist/"
    try:
        res = requests.get(source_url, headers=HEADERS, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        for div in soup.find_all('div', class_='mac', option=True):
            sid = div['option']
            title = div.find('div', class_='match-takimlar').get_text(strip=True)
            group = "NETSPOR KANALLAR" if div.find_parent('div', id='yayinlarKanallar') else "NETSPOR MACLAR"
            results.append({"name": title, "url": f"{stream_base}{sid}.m3u8", "group": group, "ref": source_url, "logo": ""})
    except: pass
    return results

# --- 2. TRGOALS FONKSİYONU ---
def fetch_trgoals():
    print("[*] Trgoals taranıyor...")
    results = []
    base_prefix = "https://trgoals"
    domain = None
    for i in range(1485, 2101):
        test = f"{base_prefix}{i}.xyz"
        try:
            if requests.head(test, timeout=1).status_code == 200:
                domain = test; break
        except: continue
    
    if domain:
        cids = {"yayin1":"BEIN 1","yayinb2":"BEIN 2","yayinb3":"BEIN 3","yayinb4":"BEIN 4","yayinb5":"BEIN 5","yayinss":"S SPORT","yayint1":"TIVIBU 1"}
        for cid, name in cids.items():
            try:
                r = requests.get(f"{domain}/channel.html?id={cid}", headers=HEADERS, timeout=5)
                m = re.search(r'const baseurl = "(.*?)"', r.text)
                if m:
                    results.append({"name": f"TRG - {name}", "url": f"{m.group(1)}{cid}.m3u8", "group": "TRGOALS", "ref": f"{domain}/", "logo": "https://i.ibb.co/gFyFDdDN/trgoals.jpg"})
            except: continue
    return results

# --- 3. SELÇUKSPOR / SPORCAFE FONKSİYONU ---
def fetch_selcuk_sporcafe():
    print("[*] Selçukspor / Sporcafe taranıyor...")
    results = []
    
    # Kanal listesi (Senin son paylaştığın liste)
    selcuk_channels = [
        {"id": "selcukbeinsports1", "name": "BeIN Sports 1", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/5rhmw31628798883.png"},
        {"id": "selcukbeinsports2", "name": "BeIN Sports 2", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/7uv6x71628799003.png"},
        {"id": "selcukbeinsports3", "name": "BeIN Sports 3", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/u3117i1628798857.png"},
        {"id": "selcukbeinsports4", "name": "BeIN Sports 4", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/2ktmcp1628798841.png"},
        {"id": "selcukbeinsports5", "name": "BeIN Sports 5", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/BeIn_Sports_5_US.png"},
        {"id": "selcukbeinsportsmax1", "name": "BeIN Sports Max 1", "logo": "https://assets.bein.com/mena/sites/3/2015/06/beIN_SPORTS_MAX1_DIGITAL_Mono.png"},
        {"id": "selcuktivibuspor1", "name": "Tivibu Spor 1", "logo": "https://r2.thesportsdb.com/images/media/channel/logo/qadnsi1642604437.png"},
        {"id": "selcukssport", "name": "S Sport 1", "logo": "https://itv224226.tmp.tivibu.com.tr:6430/images/poster/20230302923239.png"},
        {"id": "selcuksmartspor", "name": "Smart Spor 1", "logo": "https://dsmart-static-v2.ercdn.net//resize-width/1920/content/p/el/11909/Thumbnail.png"}
    ]

    working_html, referer = None, None
    for i in range(6, 100):
        url = f"https://www.sporcafe{i}.xyz/"
        try:
            res = requests.get(url, headers=HEADERS, timeout=2)
            if res.status_code == 200 and "uxsyplayer" in res.text:
                working_html, referer = res.text, url
                break
        except: continue
    
    if working_html:
        # Stream domainini bul
        s_match = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', working_html)
        if s_match:
            stream_domain = f"https://{s_match.group(1)}"
            for ch in selcuk_channels:
                try:
                    r = requests.get(f"{stream_domain}/index.php?id={ch['id']}", headers={**HEADERS, "Referer": referer}, timeout=5)
                    base = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', r.text)
                    if base:
                        results.append({
                            "name": ch['name'], 
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
    
    # Tüm kaynaklardan verileri topla
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_trgoals())
    all_streams.extend(fetch_selcuk_sporcafe())
    
    if not all_streams:
        print("Hiçbir yayın çekilemedi!")
        return

    content = "#EXTM3U\n"
    content += f"# Guncelleme: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    for s in all_streams:
        logo = f' tvg-logo="{s["logo"]}"' if s["logo"] else ""
        content += f'#EXTINF:-1 group-title="{s["group"]}"{logo},{s["name"]}\n'
        content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'{s["url"]}\n'

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[BİTTİ] Toplam {len(all_streams)} kanal kaydedildi.")

if __name__ == "__main__":
    main()
