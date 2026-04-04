import requests
import re
import datetime
import urllib3
import json
import concurrent.futures
from bs4 import BeautifulSoup

# --- AYARLAR ---
M3U_OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
WORKING_BS1_URL = "https://andro.adece12.sbs/checklist/receptestt.m3u8"

# SSL Uyarılarını gizle
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
#      1. BÖLÜM: YAYINLARI TOPLAMA
# ==========================================

# --- 1. ATOM SPOR ---
def fetch_atom_spor():
    print("[*] AtomSpor (VIP) kanalları ekleniyor...")
    results = []
    base_url = "https://hlssssss.volepartigo.workers.dev/https://corestream.ronaldovurdu.help//hls/"
    atom_logo = "https://hizliresim.com/gm50rk9b"
    
    channels = [
        ("Bein Sports 1", "bein-sports-1"), ("Bein Sports 2", "bein-sports-2"),
        ("Bein Sports 3", "bein-sports-3"), ("Bein Sports 4", "bein-sports-4"),
        ("Bein Sports 5", "bein-sports-5"), ("S Sport 1", "s-sport"),
        ("S Sport 2", "s-sport-2"), ("S Sport Plus", "ssport-plus"),
        ("Tivibu Spor 1", "tivibu-spor-1"), ("Tivibu Spor 2", "tivibu-spor-2"),
        ("Tivibu Spor 3", "tivibu-spor-3"), ("Smart Spor", "smart-spor"),
        ("TV 8.5", "tv-8-5"), ("Bein Sports Haber", "bein-sports-haber")
    ]
    
    for name, cid in channels:
        results.append({
            "name": f"ATOM - {name}",
            "url": f"{base_url}{cid}.m3u8",
            "group": "ATOM SPOR (VIP)",
            "logo": atom_logo,
            "ref": "https://atomsportv485.top/"
        })
    return results

# --- 2. ARDASPOR (VAVOO YERİNE EKLENDİ) ---
def fetch_ardaspor():
    print("[*] ArdaSpor kanalları ekleniyor...")
    results = []
    base_url = "https://black-snow-b418.hlsforeveer.workers.dev/https://corestream.ronaldovurdu.help//hls/"
    ardaspor_logo = "https://i.hizliresim.com/b6xqz10.jpg" # Varsayılan logo
    referer = "https://ardaspor10.site/"
    
    channels = [
        ("Bein Sports 1 HD", "bein-sports-1"), ("Bein Sports 2 HD", "bein-sports-2"),
        ("Bein Sports 3 HD", "bein-sports-3"), ("Bein Sports 4 HD", "bein-sports-4"),
        ("Bein Sports 5 HD", "bein-sports-5"), ("S Sport 1 HD", "s-sport"),
        ("S Sport 2 HD", "s-sport-2"), ("S Sport Plus", "ssport-plus"),
        ("Tivibu Spor 1", "tivibu-spor-1"), ("Tivibu Spor 2", "tivibu-spor-2"),
        ("Tivibu Spor 3", "tivibu-spor-3"), ("Tivibu Spor 4", "tivibu-spor-4"),
        ("Smart Spor", "smart-spor"), ("TV 8.5", "tv-8-5"),
        ("A Spor", "a-spor"), ("TRT Spor", "trt-spor"),
        ("Eurosport 1", "eurosport-1"), ("Eurosport 2", "eurosport-2"),
        ("Exxen Spor 1", "exxen-1"), ("Exxen Spor 2", "exxen-2")
    ]
    
    for name, cid in channels:
        results.append({
            "name": f"ARDA - {name}",
            "url": f"{base_url}{cid}.m3u8",
            "group": "ARDASPOR TV",
            "logo": ardaspor_logo,
            "ref": referer
        })
    return results

# --- 3. NETSPOR ---
def fetch_netspor():
    print("[*] Netspor taranıyor...")
    results = []
    source_url = "https://netspor-amp.xyz/"
    stream_base = "https://andro.adece12.sbs/checklist/" 
    try:
        res = requests.get(source_url, headers=HEADERS, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        for div in soup.find_all('div', class_='mac', option=True):
            sid = div.get('option')
            t_div = div.find('div', class_='match-takimlar')
            if not sid or not t_div: continue
            title = t_div.get_text(strip=True)
            group = "CANLI TV KANALLARI" if div.find_parent('div', id='kontrolPanelKanallar') else "Günün Maçları"
            if group == "Günün Maçları":
                alt = div.find('div', class_='match-alt')
                if alt: title = f"{title} ({alt.get_text(' | ', strip=True)})"
            final_url = WORKING_BS1_URL if sid == "androstreamlivebs1" else f"{stream_base}{sid}.m3u8"
            results.append({"name": f"NET - {title}", "url": final_url, "group": f"NETSPOR {group.upper()}", "ref": source_url, "logo": ""})
    except: pass
    return results

# --- 4. TRGOALS ---
def fetch_trgoals():
    print("[*] Trgoals kanalları ekleniyor...")
    results = []
    worker_url = "https://muddy-morning-480c.burhantasci72.workers.dev/?url="
    target_domain = "https://pq4.d72577a9dd0ec4.sbs/"
    trg_referer = "https://trgoals1517.xyz/"
    
    trg_channels = {
        "yayinzirve": "TRGOALS CANLI YAYIN (ZIRVE)",
        "yayin1": "BEIN SPORTS 1 HD",
        "yayinb2": "BEIN SPORTS 2 HD",
        "yayinb3": "BEIN SPORTS 3 HD",
        "yayinb4": "BEIN SPORTS 4 HD",
        "yayinb5": "BEIN SPORTS 5 HD",
        "yayinbm1": "BEIN SPORTS MAX 1",
        "yayinbm2": "BEIN SPORTS MAX 2",
        "yayinss": "S SPORT 1",
        "yayinss2": "S SPORT 2",
        "yayint1": "TIVIBU SPOR 1",
        "yayint2": "TIVIBU SPOR 2",
        "yayint3": "TIVIBU SPOR 3",
        "yayint4": "TIVIBU SPOR 4",
        "yayinsmarts": "SMART SPOR 1",
        "yayinsms2": "SMART SPOR 2",
        "yayintrtspor": "TRT SPOR",
        "yayinas": "A SPOR",
        "yayintv85": "TV8.5 HD",
        "yayinex1": "EXXEN 1", "yayinex2": "EXXEN 2",
        "yayinex3": "EXXEN 3", "yayinex4": "EXXEN 4"
    }
    
    logo_url = "https://i.ibb.co/gFyFDdDN/trgoals.jpg"

    for cid, name in trg_channels.items():
        full_url = f"{worker_url}{target_domain}{cid}.m3u8"
        results.append({
            "name": f"TRG - {name}",
            "url": full_url,
            "group": "TRGOALS TV (WORKER)",
            "ref": trg_referer,
            "logo": logo_url
        })
    return results

# --- 5. INADINA TV (WORKER) ---
def fetch_inadina_tv():
    print("[*] INADINA TV (Worker) kanalları ekleniyor...")
    results = []
    base_worker = "https://rough-inadinatv.burhantasci72.workers.dev"
    
    channels = [
        ("701", "INADINA - beIN SPORTS 1"), ("702", "INADINA - beIN SPORTS 2"),
        ("703", "INADINA - beIN SPORTS 3"), ("704", "INADINA - beIN SPORTS 4"),
        ("705", "INADINA - S SPORT 1"), ("730", "INADINA - S SPORT 2"),
        ("706", "INADINA - TIVIBU SPOR 1"), ("711", "INADINA - TIVIBU SPOR 2"),
        ("712", "INADINA - TIVIBU SPOR 3"), ("713", "INADINA - TIVIBU SPOR 4"),
    ]
    
    for cid, cname in channels:
        results.append({
            "name": cname,
            "url": f"{base_worker}/{cid}.m3u8",
            "group": "INADINA TV (WORKER)",
            "logo": "https://hizliresim.com/gm50rk9",
            "ref": ""
        })
    return results

# --- 6. TARAFTARIUM24 ---
def fetch_taraftarium():
    print("[*] Taraftarium24 taranıyor...")
    results = []
    base_url = "https://taraftarium24bet.net"
    stream_template = "https://hls.freepalastne.workers.dev/https://corestream.ronaldovurdu.help//hls/{slug}.m3u8"
    
    try:
        res = requests.get(base_url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            links = soup.find_all("a", href=True)
            found_slugs = set()
            for link in links:
                href = link['href']
                if "/izle/" in href:
                    slug = href.split("/izle/")[-1].strip("/")
                    if slug and slug not in found_slugs:
                        found_slugs.add(slug)
                        name = slug.replace("-", " ").upper()
                        results.append({
                            "name": f"TRF - {name}",
                            "url": stream_template.format(slug=slug),
                            "group": "TARAFTARIUM24",
                            "logo": "",
                            "ref": base_url
                        })
    except Exception as e:
        print(f"[!] Taraftarium hatası: {e}")
    return results

# --- 7. SELÇUKSPOR ---
def fetch_selcuk_sporcafe():
    print("[*] Selçukspor taranıyor...")
    results = []
    selcuk_channels = [
        {"id": "selcukbeinsports1", "n": "BEIN SPORTS 1"}, {"id": "selcukbeinsports2", "n": "BEIN SPORTS 2"},
        {"id": "selcukbeinsports3", "n": "BEIN SPORTS 3"}, {"id": "selcukbeinsports4", "n": "BEIN SPORTS 4"},
        {"id": "selcukbeinsports5", "n": "BEIN SPORTS 5"}, {"id": "selcukbeinsportsmax1", "n": "BEIN MAX 1"},
        {"id": "selcukbeinsportsmax2", "n": "BEIN MAX 2"}, {"id": "selcukssport", "n": "S SPORT 1"},
        {"id": "selcukssport2", "n": "S SPORT 2"}, {"id": "selcuktivibuspor1", "n": "TIVIBU 1"},
        {"id": "selcuktivibuspor2", "n": "TIVIBU 2"}, {"id": "selcuksmartspor", "n": "SMART SPOR 1"},
        {"id": "selcukaspor", "n": "A SPOR"}, {"id": "selcukeurosport1", "n": "EUROSPORT 1"}
    ]
    referer, html = None, None
    for i in range(6, 150):
        url = f"https://www.sporcafe{i}.xyz/"
        try:
            res = requests.get(url, headers=HEADERS, timeout=1)
            if "uxsyplayer" in res.text: referer, html = url, res.text; break
        except: continue
    if html:
        m_dom = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', html)
        if m_dom:
            s_dom = f"https://{m_dom.group(1)}"
            for ch in selcuk_channels:
                try:
                    r = requests.get(f"{s_dom}/index.php?id={ch['id']}", headers={**HEADERS, "Referer": referer}, timeout=5)
                    base = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', r.text)
                    if base: results.append({"name": f"SL - {ch['n']}", "url": f"{base.group(1)}{ch['id']}/playlist.m3u8", "group": "SELÇUKSPOR HD", "ref": referer, "logo": ""})
                except: continue
    return results

# --- 8. ANDRO PANEL ---
def fetch_andro_nodes():
    print("[*] Andro-Panel taranıyor...")
    results = []
    PROXY = "https://proxy.freecdn.workers.dev/?url="
    START = "https://taraftariumizle.org"
    channels = [
        ("androstreamlivebiraz1", 'TR:beIN Sport 1 HD'), ("androstreamlivebs1", 'TR:beIN Sport 1 HD'),
        ("androstreamlivebs2", 'TR:beIN Sport 2 HD'), ("androstreamlivebs3", 'TR:beIN Sport 3 HD'),
        ("androstreamlivebs4", 'TR:beIN Sport 4 HD'), ("androstreamlivebs5", 'TR:beIN Sport 5 HD'),
        ("androstreamlivebsm1", 'TR:beIN Sport Max 1 HD'), ("androstreamlivebsm2", 'TR:beIN Sport Max 2 HD'),
        ("androstreamlivess1", 'TR:S Sport 1 HD'), ("androstreamlivess2", 'TR:S Sport 2 HD'),
        ("androstreamlivets", 'TR:Tivibu Sport HD'), ("androstreamlivets1", 'TR:Tivibu Sport 1 HD'),
        ("androstreamlivets2", 'TR:Tivibu Sport 2 HD'), ("androstreamlivets3", 'TR:Tivibu Sport 3 HD'),
        ("androstreamlivets4", 'TR:Tivibu Sport 4 HD'), ("androstreamlivesm1", 'TR:Smart Sport 1 HD'),
        ("androstreamlivesm2", 'TR:Smart Sport 2 HD'), ("androstreamlivees1", 'TR:Euro Sport 1 HD'),
        ("androstreamlivees2", 'TR:Euro Sport 2 HD'), ("androstreamlivetb", 'TR:Tabii HD'),
        ("androstreamlivetb1", 'TR:Tabii 1 HD'), ("androstreamlivetb2", 'TR:Tabii 2 HD'),
        ("androstreamliveexn", 'TR:Exxen HD'), ("androstreamliveexn1", 'TR:Exxen 1 HD'),
    ]
    def get_src(u, ref=None):
        try:
            h = HEADERS.copy()
            if ref: h['Referer'] = ref
            r = requests.get(PROXY + u, headers=h, verify=False, timeout=20)
            return r.text if r.status_code == 200 else None
        except: return None

    try:
        h1 = get_src(START)
        if h1:
            s = BeautifulSoup(h1, 'html.parser')
            lnk = s.find('link', rel='amphtml')
            if lnk:
                amp = lnk.get('href')
                h2 = get_src(amp)
                if h2:
                    m = re.search(r'\[src\]="appState\.currentIframe".*?src="(https?://[^"]+)"', h2, re.DOTALL)
                    if m:
                        ifr = m.group(1)
                        h3 = get_src(ifr, ref=amp)
                        if h3:
                            bm = re.search(r'baseUrls\s*=\s*\[(.*?)\]', h3, re.DOTALL)
                            if bm:
                                cl = bm.group(1).replace('"', '').replace("'", "").replace("\n", "").replace("\r", "")
                                srvs = [x.strip() for x in cl.split(',') if x.strip().startswith("http")]
                                srvs = list(set(srvs)) 
                                active_servers = []
                                tid = "androstreamlivebs1" 
                                for sv in srvs:
                                    sv = sv.rstrip('/')
                                    turl = f"{sv}/{tid}.m3u8" if "checklist" in sv else f"{sv}/checklist/{tid}.m3u8"
                                    turl = turl.replace("checklist//", "checklist/")
                                    try:
                                        tr = requests.get(PROXY + turl, headers=HEADERS, verify=False, timeout=5)
                                        if tr.status_code == 200: active_servers.append(sv)
                                    except: pass
                                for srv in active_servers:
                                    for cid, cname in channels:
                                        furl = f"{srv}/{cid}.m3u8" if "checklist" in srv else f"{srv}/checklist/{cid}.m3u8"
                                        furl = furl.replace("checklist//", "checklist/")
                                        results.append({"name": f"ANDRO - {cname}", "url": furl, "group": "ANDRO SPOR (YENI)", "logo": "https://hizliresim.com/gm50rk9", "ref": ifr})
        print(f"[OK] Andro-Panel: {len(results)} kanal eklendi.")
    except Exception as e: print(f"[!] Andro-Panel hatasi: {e}")
    return results

# --- 9. XSPORTV (DEATHLESS) ---
def fetch_xsport():
    print("[*] XSport (Deathless) taranıyor...")
    results = []
    base_pattern = "https://www.xsportv{}.xyz/"
    logo = "https://i.hizliresim.com/b6xqz10.jpg"
    
    channel_ids = [
        "xbeinsports-1", "xbeinsports-2", "xbeinsports-3", "xbeinsports-4", "xbeinsports-5",
        "xbeinsportsmax-1", "xbeinsportsmax-2", "xtivibuspor-1", "xtivibuspor-2",
        "xtivibuspor-3", "xtivibuspor-4", "xssport", "xssport2", "xtabiispor1",
        "xtabiispor2", "xtabiispor3", "xtabiispor4", "xtabiispor5", "xtabiispor6", "xtabiispor7"
    ]

    def check_domain(index):
        url = base_pattern.format(index)
        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            if response.status_code == 200:
                return url
        except:
            return None

    def find_active_domain():
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check_domain, i) for i in range(56, 1000)]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    return result
        return None

    active_domain = find_active_domain()
    
    if active_domain:
        print(f"    [+] Aktif Domain bulundu: {active_domain}")
        try:
            response = requests.get(active_domain, headers=HEADERS)
            for cid in channel_ids:
                pattern = rf'data-url="(.*?id={cid}.*?)"'
                match = re.search(pattern, response.text)
                
                if match:
                    player_link = match.group(1)
                    # Player linkten akış adresini al
                    try:
                        res = requests.get(player_link, headers=HEADERS, timeout=5)
                        base_match = re.search(r"this\.baseStreamUrl\s*=\s*'(.*?)'", res.text)
                        if base_match:
                            base = base_match.group(1)
                            final_url = f"{base}{cid}/playlist.m3u8"
                            
                            # İsim formatlama
                            name = cid.replace("x", "").replace("-", " ").upper()
                            if "BEIN" in name: name = name.replace("BEIN", "BEIN SPORTS")
                            
                            results.append({
                                "name": f"XSP - {name}",
                                "url": final_url,
                                "group": "XSPORTV (DEATHLESS)",
                                "logo": logo,
                                "ref": active_domain
                            })
                    except: pass
        except Exception as e:
            print(f"[!] XSport hatası: {e}")
    else:
        print("    [!] XSport aktif domain bulunamadı.")
        
    return results

# ==========================================
#      2. BÖLÜM: ANA ÇALIŞTIRICI
# ==========================================

def main():
    all_streams = []
    print("--- SPOR LİSTESİ OLUŞTURUCU BAŞLATILDI ---")
    
    # Tüm kaynakları çek
    all_streams.extend(fetch_atom_spor())
    all_streams.extend(fetch_ardaspor()) # VAVOO YERİNE BURAYA EKLENDİ
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_trgoals()) 
    all_streams.extend(fetch_inadina_tv())
    all_streams.extend(fetch_taraftarium())
    all_streams.extend(fetch_selcuk_sporcafe())
    all_streams.extend(fetch_andro_nodes())
    all_streams.extend(fetch_xsport())
    
    if not all_streams: 
        print("Hicbir kanal bulunamadi!")
        return

    # M3U Dosyasını Oluştur
    content = "#EXTM3U\n"
    content += f"# Son Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    for s in all_streams:
        logo_attr = f' tvg-logo="{s["logo"]}"' if s.get("logo") else ""
        content += f'#EXTINF:-1 group-title="{s["group"]}"{logo_attr},{s["name"]}\n'
        if s.get("ref"): 
            content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n'
        content += f'#EXTHTTP:{"User-Agent"}:{HEADERS["User-Agent"]}\n'
        content += f'{s["url"]}\n'

    with open(M3U_OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(content)
    print(f"\n[OK] M3U listesi olusturuldu -> {M3U_OUTPUT_FILE}")

if __name__ == "__main__":
    main()
