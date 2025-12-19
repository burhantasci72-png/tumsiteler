import requests
import re
import datetime
from bs4 import BeautifulSoup

# --- AYARLAR ---
OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

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
                    results.append({"name": name, "url": f"{m.group(1)}{cid}.m3u8", "group": "TRGOALS", "ref": f"{domain}/", "logo": "https://i.ibb.co/gFyFDdDN/trgoals.jpg"})
            except: continue
    return results

def fetch_sporcafe():
    print("[*] Sporcafe taranıyor...")
    results = []
    start_url = "https://www.sporcafe-4a2fb1f79d.xyz/"
    try:
        res = requests.get(start_url, headers=HEADERS, timeout=10)
        m_domain = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', res.text)
        if m_domain:
            s_domain = f"https://{m_domain.group(1)}"
            cids = [{"id":"sbeinsports-1","n":"BEIN 1"},{"id":"sbeinsports-2","n":"BEIN 2"},{"id":"sssport","n":"S SPORT"},{"id":"stivibuspor-1","n":"TIVIBU 1"}]
            for c in cids:
                r = requests.get(f"{s_domain}/index.php?id={c['id']}", headers={**HEADERS, "Referer": start_url}, timeout=5)
                base = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', r.text)
                if base:
                    results.append({"name": c['n'], "url": f"{base.group(1)}{c['id']}/playlist.m3u8", "group": "SELÇUKSPOR / CAFE", "ref": start_url, "logo": ""})
    except: pass
    return results

def main():
    all_streams = []
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_trgoals())
    all_streams.extend(fetch_sporcafe())
    
    content = "#EXTM3U\n"
    content += f"# Birlesik Liste Guncelleme: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    for s in all_streams:
        logo = f' tvg-logo="{s["logo"]}"' if s["logo"] else ""
        content += f'#EXTINF:-1 group-title="{s["group"]}"{logo},{s["name"]}\n'
        content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'{s["url"]}\n'
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    main()
