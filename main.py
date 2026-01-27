import requests
import re
import datetime
import urllib3
import os
from bs4 import BeautifulSoup

# --- AYARLAR ---
# GitHub ortamında direkt ana dizine kaydeder
OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

WORKING_BS1_URL = "https://andro.adece12.sbs/checklist/receptestt.m3u8"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. ATOM SPOR ---
def fetch_atom_spor():
    print("[*] AtomSpor (VIP) ekleniyor...")
    results = []
    base_url = "https://hlssssss.volepartigo.workers.dev/https://corestream.ronaldovurdu.help//hls/"
    channels = [
        ("Bein Sports 1", "bein-sports-1"), ("Bein Sports 2", "bein-sports-2"),
        ("Bein Sports 3", "bein-sports-3"), ("Bein Sports 4", "bein-sports-4"),
        ("Bein Sports 5", "bein-sports-5"), ("S Sport 1", "s-sport"),
        ("S Sport 2", "s-sport-2"), ("S Sport Plus", "ssport-plus"),
        ("Tivibu Spor 1", "tivibu-spor-1"), ("Smart Spor", "smart-spor"),
        ("TV 8.5", "tv-8-5"), ("Bein Sports Haber", "bein-sports-haber")
    ]
    for name, cid in channels:
        results.append({"name": f"ATOM - {name}", "url": f"{base_url}{cid}.m3u8", "group": "ATOM SPOR (VIP)", "logo": "", "ref": "https://atomsportv485.top/"})
    return results

# --- 2. VAVOO ---
def fetch_vavoo():
    print("[*] Vavoo ekleniyor...")
    results = []
    proxy_base = "https://yildiziptv-turktv.hf.space/proxy/hls/manifest.m3u8?d=https://vavoo.to/vavoo-iptv/play/"
    vavoo_channels = [
        {"n": "beIN SPORTS 1 HD", "id": "257621689779b8fed9899e"},
        {"n": "beIN SPORTS 2 FHD", "id": "3694662475b76c08f52108"},
        {"n": "beIN SPORTS 3 FHD", "id": "34101675603c7aea8fa6b1"},
        {"n": "beIN SPORTS 4 FHD", "id": "293826835381972adead05"},
        {"n": "beIN SPORTS 5 FHD", "id": "400031560107e5581e3624"}
    ]
    for ch in vavoo_channels:
        results.append({"name": f"VAVOO - {ch['n']}", "url": f"{proxy_base}{ch['id']}", "group": "VAVOO SPOR", "logo": "", "ref": ""})
    return results

# --- 3. NETSPOR ---
def fetch_netspor():
    print("[*] Netspor taranıyor...")
    results = []
    source_url = "https://netspor-amp.xyz/"
    stream_base = "https://andro.adece12.sbs/checklist/" 
    try:
        res = requests.get(source_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for div in soup.find_all('div', class_='mac', option=True):
            sid = div.get('option')
            t_div = div.find('div', class_='match-takimlar')
            if not sid or not t_div: continue
            title = t_div.get_text(strip=True)
            final_url = WORKING_BS1_URL if sid == "androstreamlivebs1" else f"{stream_base}{sid}.m3u8"
            results.append({"name": f"NET - {title}", "url": final_url, "group": "NETSPOR CANLI", "ref": source_url, "logo": ""})
    except: pass
    return results

# --- 4. TRGOALS ---
def fetch_trgoals():
    print("[*] Trgoals ekleniyor...")
    results = []
    worker_url = "https://muddy-morning-480c.burhantasci72.workers.dev/?url="
    target_domain = "https://pq4.d72577a9dd0ec4.sbs/"
    trg_channels = {"yayin1": "BEIN SPORTS 1 HD", "yayinb2": "BEIN SPORTS 2 HD", "yayinss": "S SPORT 1"}
    for cid, name in trg_channels.items():
        results.append({"name": f"TRG - {name}", "url": f"{worker_url}{target_domain}{cid}.m3u8", "group": "TRGOALS TV", "ref": "", "logo": ""})
    return results

# --- 5. INAT TV ---
def fetch_inat_tv():
    print("[*] INAT TV ekleniyor...")
    results = []
    base_worker = "https://rough-inadinatv.burhantasci72.workers.dev"
    channels = [("701", "INAT - beIN SPORTS 1"), ("702", "INAT - beIN SPORTS 2"), ("705", "INAT - S SPORT 1")]
    for cid, cname in channels:
        results.append({"name": cname, "url": f"{base_worker}/{cid}.m3u8", "group": "INAT TV (WORKER)", "logo": "", "ref": ""})
    return results

# --- 6. ANDRO PANEL ---
def fetch_andro_nodes():
    print("[*] Andro-Panel taranıyor...")
    results = []
    PROXY = "https://proxy.freecdn.workers.dev/?url="
    START = "https://taraftariumizle.org"
    channels = [("androstreamlivebs1", 'TR:beIN Sport 1 HD'), ("androstreamlivebs2", 'TR:beIN Sport 2 HD')]
    
    try:
        r = requests.get(PROXY + START, headers=HEADERS, verify=False, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            lnk = soup.find('link', rel='amphtml')
            if lnk:
                r2 = requests.get(PROXY + lnk.get('href'), headers=HEADERS, verify=False, timeout=10)
                m = re.search(r'\[src\]="appState\.currentIframe".*?src="(https?://[^"]+)"', r2.text, re.DOTALL)
                if m:
                    ifr_url = m.group(1)
                    r3 = requests.get(PROXY + ifr_url, headers={'Referer': lnk.get('href')}, verify=False, timeout=10)
                    bm = re.search(r'baseUrls\s*=\s*\[(.*?)\]', r3.text, re.DOTALL)
                    if bm:
                        srvs = [x.strip().replace("'", "").replace('"', "") for x in bm.group(1).split(',')]
                        server = [s for s in srvs if s.startswith("http")][0] # İlk sunucuyu al
                        for cid, cname in channels:
                            furl = f"{server}/checklist/{cid}.m3u8"
                            results.append({"name": f"ANDRO - {cname}", "url": furl, "group": "ANDRO SPOR", "logo": "", "ref": ifr_url})
    except: pass
    return results

# --- 7. TARAFTARIUM (WORKER) ---
def fetch_taraftarium_extra():
    print("[*] Taraftarium (Worker) taranıyor...")
    results = []
    # Cloudflare engeline takılmamak için birden fazla domain deniyoruz
    base_urls = ["https://taraftarium24bet.net", "https://taraftarium24.pro"]
    stream_template = "https://hls.freepalastne.workers.dev/https://corestream.ronaldovurdu.help//hls/{slug}.m3u8"
    
    found_any = False
    for base_url in base_urls:
        if found_any: break
        try:
            r = requests.get(base_url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, "html.parser")
                links = soup.find_all("a", href=True)
                for link in links:
                    if "/izle/" in link['href']:
                        slug = link['href'].split("/izle/")[-1].strip("/")
                        if slug:
                            name = slug.replace("-", " ").upper()
                            results.append({
                                "name": f"TRF - {name}", 
                                "url": stream_template.format(slug=slug), 
                                "group": "TARAFTARIUM", 
                                "logo": "", 
                                "ref": ""
                            })
                if results: found_any = True
        except: pass
    return results

# --- ANA ÇALIŞTIRICI ---
def main():
    all_streams = []
    
    # Tüm fonksiyonları güvenli şekilde çağır (biri hata verirse diğerleri çalışsın)
    funcs = [fetch_atom_spor, fetch_vavoo, fetch_netspor, fetch_trgoals, fetch_inat_tv, fetch_andro_nodes, fetch_taraftarium_extra]
    
    for func in funcs:
        try:
            all_streams.extend(func())
        except Exception as e:
            print(f"Hata ({func.__name__}): {e}")

    content = "#EXTM3U\n"
    content += f"# Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    
    for s in all_streams:
        content += f'#EXTINF:-1 group-title="{s["group"]}",{s["name"]}\n'
        if s.get("ref"): content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n'
        content += f'{s["url"]}\n'

    # Dosyayı kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"\n[BASARILI] Toplam {len(all_streams)} kanal bulundu ve '{OUTPUT_FILE}' dosyasina kaydedildi.")

if __name__ == "__main__":
    main()
