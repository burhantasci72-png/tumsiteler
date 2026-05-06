import requests
import re
import datetime
import urllib3
import urllib.parse
import base64
import concurrent.futures
from bs4 import BeautifulSoup

# --- AYARLAR ---
M3U_OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# NETSPOR & ANDRO YENİ GÜNCEL SUNUCU ADRESİ
WORKING_BS1_URL = "https://andro.evrenesoglu59.lat/checklist/receptestt.m3u8"

# SSL Uyarılarını gizle
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
#      ORTAK AKILLI M3U8 ÇÖZÜCÜ (BOT)
# ==========================================
def extract_m3u8_from_page(url, ref=None):
    try:
        headers = HEADERS.copy()
        if ref: headers["Referer"] = ref
        res = requests.get(url, headers=headers, timeout=10)
        
        def find_m3u8(text, base_url):
            m = re.search(r'(https?://[^\s\'">]+\.m3u8[^\s\'">]*)', text)
            if m: return m.group(1)
            
            m_rel = re.search(r'[\'"](/[^\s\'">]+\.m3u8[^\s\'">]*)[\'"]', text)
            if m_rel:
                parsed_uri = urllib.parse.urlparse(base_url)
                domain = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_uri)
                return domain + m_rel.group(1)
            
            unescaped_m = re.search(r'(https%3A%2F%2F[^\s\'">]+%2Em3u8[^\s\'">]*)', text)
            if unescaped_m: return urllib.parse.unquote(unescaped_m.group(1))
            
            for b64 in re.findall(r'atob\([\'"]([A-Za-z0-9+/=]+)[\'"]\)', text):
                try:
                    decoded = base64.b64decode(b64).decode('utf-8')
                    m_dec = re.search(r'(https?://[^\s\'">]+\.m3u8[^\s\'">]*)', decoded)
                    if m_dec: return m_dec.group(1)
                except: pass
                
            for b64 in re.findall(r'[\'"]([A-Za-z0-9+/=]{40,})[\'"]', text):
                try:
                    decoded = base64.b64decode(b64).decode('utf-8')
                    if '.m3u8' in decoded:
                        m_dec = re.search(r'(https?://[^\s\'">]+\.m3u8[^\s\'">]*)', decoded)
                        if m_dec: return m_dec.group(1)
                except: pass
            return None

        found = find_m3u8(res.text, url)
        if found: return found

        iframes = re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', res.text)
        for iframe_src in iframes:
            try:
                r2 = requests.get(iframe_src, headers={**HEADERS, "Referer": url}, timeout=10)
                found = find_m3u8(r2.text, iframe_src)
                if found: return found
                
                sub_iframes = re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', r2.text)
                for sub in sub_iframes:
                    try:
                        r3 = requests.get(sub, headers={**HEADERS, "Referer": iframe_src}, timeout=10)
                        found_sub = find_m3u8(r3.text, sub)
                        if found_sub: return found_sub
                    except: continue
            except: continue
    except Exception: pass
    return None

# ==========================================
#      1. BÖLÜM: YAYINLARI TOPLAMA
# ==========================================

# --- 1. ANDRO PANEL ---
def fetch_andro_nodes():
    print("[*] Andro-Panel taranıyor...")
    results =[]
    PROXY = "https://proxy.freecdn.workers.dev/?url="
    START = "https://taraftariumizle.org"
    channels =[
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
                                srvs =[x.strip() for x in cl.split(',') if x.strip().startswith("http")]
                                srvs = list(set(srvs)) 
                                active_servers =[]
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
                                        results.append({"name": f"ANDRO - {cname}", "url": furl, "group": "ANDRO SPOR", "logo": "https://hizliresim.com/gm50rk9", "ref": "https://taraftariumizle.org/"})
        print(f"[OK] Andro-Panel: {len(results)} kanal eklendi.")
    except Exception as e: print(f"[!] Andro-Panel hatasi: {e}")
    return results

# --- 2. XSPORTV ---
def fetch_xsport():
    print("[*] XSport taranıyor...")
    results =[]
    base_pattern = "https://www.xsportv{}.xyz/"
    logo = "https://i.hizliresim.com/b6xqz10.jpg"
    
    channel_ids =[
        "xbeinsports-1", "xbeinsports-2", "xbeinsports-3", "xbeinsports-4", "xbeinsports-5",
        "xbeinsportsmax-1", "xbeinsportsmax-2", "xtivibuspor-1", "xtivibuspor-2",
        "xtivibuspor-3", "xtivibuspor-4", "xssport", "xssport2", "xtabiispor1",
        "xtabiispor2", "xtabiispor3", "xtabiispor4", "xtabiispor5", "xtabiispor6", "xtabiispor7"
    ]

    def check_domain(index):
        url = base_pattern.format(index)
        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            if response.status_code == 200: return url
        except: return None

    def find_active_domain():
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures =[executor.submit(check_domain, i) for i in range(56, 1000)]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result: return result
        return None

    active_domain = find_active_domain()
    
    if active_domain:
        try:
            response = requests.get(active_domain, headers=HEADERS)
            for cid in channel_ids:
                pattern = rf'data-url="(.*?id={cid}.*?)"'
                match = re.search(pattern, response.text)
                if match:
                    player_link = match.group(1)
                    try:
                        res = requests.get(player_link, headers=HEADERS, timeout=5)
                        base_match = re.search(r"this\.baseStreamUrl\s*=\s*'(.*?)'", res.text)
                        if base_match:
                            base = base_match.group(1)
                            final_url = f"{base}{cid}/playlist.m3u8"
                            name = cid.replace("x", "").replace("-", " ").upper()
                            if "BEIN" in name: name = name.replace("BEIN", "BEIN SPORTS")
                            results.append({"name": f"XSP - {name}", "url": final_url, "group": "XSPORTV", "logo": logo, "ref": active_domain})
                    except: pass
        except Exception as e: pass
    return results

# --- 3. NETSPOR (3 KATMANLI GÜVENLİK) ---
def fetch_netspor():
    print("[*] Netspor taranıyor...")
    results =[]
    base_domain = "https://netsporcoamp.xyz"
    stream_base = "https://andro.evrenesoglu59.lat/checklist/" 
    
    try:
        res = requests.get(base_domain, headers=HEADERS, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # KATMAN 1
        for tag in soup.find_all(True):
            sid = tag.get('option') or tag.get('data-id')
            if sid and isinstance(sid, str) and (sid.startswith('andro') or sid.startswith('net')):
                title = tag.get_text(strip=True)
                if not title:
                    t_div = tag.find('div', class_=re.compile(r'takim|match|title'))
                    if t_div: title = t_div.get_text(strip=True)
                
                if title and len(title) > 2:
                    title = re.sub(r'\s+', ' ', title).strip()
                    final_url = WORKING_BS1_URL if sid == "androstreamlivebs1" else f"{stream_base}{sid}.m3u8"
                    group = "NETSPOR CANLI MAÇLAR" if " - " in title else "NETSPOR KANALLARI"
                    results.append({"name": f"NET - {title}", "url": final_url, "group": group, "ref": "https://taraftariumizle.org/", "logo": ""})

        # KATMAN 2
        if not results:
            items_to_fetch =[]
            seen_links = set()
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(skip in href.lower() for skip in['whatsapp', 't.me', 'twitter', 'instagram', '#', 'apk']): continue
                title = a.get_text(strip=True)
                if title and len(title) > 2 and not any(skip in title.lower() for skip in['uygulama', 'telegram', 'iletişim']):
                    link = href if href.startswith('http') else f"{base_domain.rstrip('/')}/{href.lstrip('/')}"
                    if link not in seen_links:
                        seen_links.add(link)
                        items_to_fetch.append({"title": title, "link": link})
                        
            def process_item(item):
                m3u8 = extract_m3u8_from_page(item["link"], ref=base_domain)
                if m3u8:
                    group = "NETSPOR KANALLARI" if any(k in item["title"].upper() for k in["BEIN", "SPOR", "TV", "EURO", "SMART"]) else "NETSPOR CANLI MAÇLAR"
                    return {"name": f"NET - {item['title']}", "url": m3u8, "group": group, "ref": "https://taraftariumizle.org/", "logo": ""}
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures =[executor.submit(process_item, it) for it in items_to_fetch]
                for future in concurrent.futures.as_completed(futures):
                    r = future.result()
                    if r: results.append(r)

        # KATMAN 3 (YEDEK SİSTEM)
        if not results:
            netspor_sabitler =[
                ("BeIN Sports 1", "androstreamlivebs1"), ("BeIN Sports 2", "androstreamlivebs2"),
                ("BeIN Sports 3", "androstreamlivebs3"), ("BeIN Sports 4", "androstreamlivebs4"),
                ("BeIN Sports 5", "androstreamlivebs5"), ("BeIN Sports Max 1", "androstreamlivebsm1"),
                ("BeIN Sports Max 2", "androstreamlivebsm2"), ("S Sport 1", "androstreamlivess1"),
                ("S Sport 2", "androstreamlivess2"), ("Tivibu Spor 1", "androstreamlivets1"),
                ("Tivibu Spor 2", "androstreamlivets2"), ("Tivibu Spor 3", "androstreamlivets3"),
                ("Smart Spor 1", "androstreamlivesm1"), ("Smart Spor 2", "androstreamlivesm2"),
                ("Exxen Spor 1", "androstreamliveexn1"), ("TRT Spor", "androstreamlivetrts"),
                ("A Spor", "androstreamliveaspor"), ("Euro Sport 1", "androstreamlivees1")
            ]
            for c_name, c_id in netspor_sabitler:
                f_url = WORKING_BS1_URL if c_id == "androstreamlivebs1" else f"{stream_base}{c_id}.m3u8"
                results.append({"name": f"NET - {c_name}", "url": f_url, "group": "NETSPOR KANALLARI (YEDEK)", "ref": "https://taraftariumizle.org/", "logo": ""})
                
    except Exception as e:
        print(f"[!] Netspor hatası: {e}")
        
    return results

# --- 4. ATOM SPOR ---
def fetch_atom_spor():
    print("[*] AtomSpor taranıyor...")
    results =[]
    base_domain = "https://atomsportv501.top"
    atom_logo = "https://hizliresim.com/gm50rk9b"
    
    channels =[
        ("Bein Sports 1", "bein-sports-1"), ("Bein Sports 2", "bein-sports-2"),
        ("Bein Sports 3", "bein-sports-3"), ("Bein Sports 4", "bein-sports-4"),
        ("Bein Sports 5", "bein-sports-5"), ("S Sport 1", "s-sport"),
        ("S Sport 2", "s-sport-2"), ("S Sport Plus", "ssport-plus"),
        ("Tivibu Spor 1", "tivibu-spor-1"), ("Tivibu Spor 2", "tivibu-spor-2"),
        ("Tivibu Spor 3", "tivibu-spor-3"), ("Smart Spor", "smart-spor"),
        ("TV 8.5", "tv-8-5"), ("Bein Sports Haber", "bein-sports-haber")
    ]

    def fetch_single(item):
        name, cid = item
        m3u8 = extract_m3u8_from_page(f"{base_domain}/kanal/{cid}")
        if not m3u8: m3u8 = f"https://tv.atomspor.workers.dev/?ID={cid}"
        return {"name": f"ATOM - {name}", "url": m3u8, "group": "ATOM SPOR (VIP)", "logo": atom_logo, "ref": base_domain}
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures =[executor.submit(fetch_single, ch) for ch in channels]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            
    order_map = {f"ATOM - {ch[0]}": i for i, ch in enumerate(channels)}
    results.sort(key=lambda x: order_map.get(x["name"], 999))
    return results

# --- 5. TARAFTARIUM ---
def fetch_taraftarium_ozel():
    print("[*] Taraftarium (Özel) kanalları ekleniyor...")
    results =[]
    channels =[
        ("Bein Sports 1", "https://deathless.pantonum1.workers.dev/taraftarium.m3u8"),
        ("Bein Sports 2", "https://deathless.pantonum1.workers.dev/b2.m3u8"),
        ("Bein Sports 3", "https://deathless.pantonum1.workers.dev/b3.m3u8"),
        ("Bein Sports 4", "https://deathless.pantonum1.workers.dev/b4.m3u8"),
        ("Bein Sports 5", "https://deathless.pantonum1.workers.dev/b5.m3u8"),
        ("Bein Max 1", "https://deathless.pantonum1.workers.dev/bm1.m3u8"),
        ("Bein Max 2", "https://deathless.pantonum1.workers.dev/bm2.m3u8"),
        ("S Sport 1", "https://deathless.pantonum1.workers.dev/ss.m3u8"),
        ("S Sport 2", "https://deathless.pantonum1.workers.dev/ss2.m3u8"),
        ("Smart Spor 1", "https://deathless.pantonum1.workers.dev/smarts.m3u8"),
        ("Smart Spor 2", "https://deathless.pantonum1.workers.dev/sms2.m3u8"),
        ("Tivibu Spor 1", "https://deathless.pantonum1.workers.dev/t1.m3u8"),
        ("Tivibu Spor 2", "https://deathless.pantonum1.workers.dev/t2.m3u8"),
        ("Tivibu Spor 3", "https://deathless.pantonum1.workers.dev/t3.m3u8"),
        ("Tivibu Spor 4", "https://deathless.pantonum1.workers.dev/t4.m3u8"),
        ("Eurosport 1", "https://deathless.pantonum1.workers.dev/eu1.m3u8"),
        ("Eurosport 2", "https://deathless.pantonum1.workers.dev/eu2.m3u8"),
        ("B1 ydk", "http://sewv654wfcsdwfi87fwvgbngh.siauliairsavlt.pw/iptv/MVTMCC4UTAZVDT/6817/index.m3u8"),
        ("B2 ydk", "http://sewv654wfcsdwfi87fwvgbngh.siauliairsavlt.pw/iptv/MVTMCC4UTAZVDT/6818/index.m3u8"),
        ("B3 ydk", "http://sewv654wfcsdwfi87fwvgbngh.siauliairsavlt.pw/iptv/MVTMCC4UTAZVDT/6821/index.m3u8"),
        ("B4 ydk", "http://sewv654wfcsdwfi87fwvgbngh.siauliairsavlt.pw/iptv/MVTMCC4UTAZVDT/6823/index.m3u8")
    ]
    for name, url in channels:
        results.append({"name": name, "url": url, "group": "TARAFTARIUM", "logo": "", "ref": ""})
    return results

# --- 6. SPOR PAS TV (YENİ SİSTEM / İNADINA TV YERİNE) ---
def fetch_sporpastv():
    print("[*] Spor Pas TV taranıyor...")
    results =[]
    base_domain = "https://sporpastv2.live"
    
    try:
        res = requests.get(base_domain, headers=HEADERS, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        items_to_fetch =[]
        seen_links = set()
        
        # Site içindeki linkleri ayrıştır
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(skip in href.lower() for skip in['whatsapp', 't.me', 'twitter', 'instagram', '#', 'apk']): continue
            title = a.get_text(strip=True)
            if not title:
                img = a.find('img', alt=True)
                if img: title = img.get('alt', '').strip()
            
            if title and len(title) > 2:
                link = href if href.startswith('http') else f"{base_domain.rstrip('/')}/{href.lstrip('/')}"
                if link not in seen_links and base_domain in link:
                    seen_links.add(link)
                    items_to_fetch.append({"title": title, "link": link})
                    
        def process_item(item):
            m3u8 = extract_m3u8_from_page(item["link"], ref=base_domain)
            if m3u8:
                return {"name": f"SPORPAS - {item['title']}", "url": m3u8, "group": "SPOR PAS TV", "ref": base_domain, "logo": ""}
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_item, it) for it in items_to_fetch]
            for future in concurrent.futures.as_completed(futures):
                r = future.result()
                if r: results.append(r)
                
        # Eğer bot dinamik linkleri yakalayamazsa sizin verdiğiniz Özel Zirve Altyapısını listeye basar
        if not results:
            print("    [!] Dinamik link bulunamadı, Spor Pas Yedek (Zirve) Liste devrede...")
            fallback_channels =[
                ("BeIN Sports 1", "zirve"),
                ("BeIN Sports 2", "b2"),
                ("BeIN Sports 3", "b3"),
                ("BeIN Sports 4", "b4"),
                ("BeIN Sports 5", "b5"),
                ("BeIN Max 1", "max1"),
                ("BeIN Max 2", "max2"),
                ("S Sport 1", "ssport"),
                ("S Sport 2", "ssport2"),
                ("Tivibu Spor 1", "tivibu1"),
                ("Tivibu Spor 2", "tivibu2"),
                ("Tivibu Spor 3", "tivibu3"),
                ("Smart Spor", "smart"),
                ("Exxen Spor", "exxen"),
                ("TRT Spor", "trtspor"),
                ("A Spor", "aspor")
            ]
            for name, path in fallback_channels:
                results.append({
                    "name": f"SPORPAS - {name}",
                    "url": f"https://inz.zirvedesin234.cfd/{path}/mono.m3u8",
                    "group": "SPOR PAS TV (YEDEK)",
                    "ref": base_domain,
                    "logo": ""
                })
    except Exception as e:
        print(f"[!] Spor Pas TV hatası: {e}")
        
    return results

# --- 7. TARAFTARIUM24 ---
def fetch_taraftarium():
    print("[*] Taraftarium24 (Canlı Maçlar) taranıyor...")
    results =[]
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
                        results.append({"name": f"TRF - {name}", "url": stream_template.format(slug=slug), "group": "TARAFTARIUM24", "logo": "", "ref": base_url})
    except: pass
    return results

# --- 8. SELÇUKSPOR ---
def fetch_selcuk_sporcafe():
    print("[*] Selçukspor taranıyor...")
    results = []
    selcuk_channels =[
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
            if "uxsyplayer" in res.text: 
                referer, html = url, res.text
                break
        except: continue
        
    if html:
        m_dom = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', html)
        if m_dom:
            s_dom = f"https://{m_dom.group(1)}"
            for ch in selcuk_channels:
                try:
                    r = requests.get(f"{s_dom}/index.php?id={ch['id']}", headers={**HEADERS, "Referer": referer}, timeout=5)
                    base = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', r.text)
                    if base: 
                        results.append({"name": f"SL - {ch['n']}", "url": f"{base.group(1)}{ch['id']}/playlist.m3u8", "group": "SELÇUKSPOR HD", "ref": referer, "logo": ""})
                except: continue
    return results

# ==========================================
#      2. BÖLÜM: ANA ÇALIŞTIRICI
# ==========================================

def main():
    all_streams =[]
    print("--- SPOR LİSTESİ OLUŞTURUCU BAŞLATILDI ---")
    
    all_streams.extend(fetch_andro_nodes())
    all_streams.extend(fetch_xsport())
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_atom_spor())
    all_streams.extend(fetch_taraftarium_ozel())
    all_streams.extend(fetch_sporpastv())          # <-- İnadına TV yerine eklendi
    all_streams.extend(fetch_taraftarium())
    all_streams.extend(fetch_selcuk_sporcafe())
    
    if not all_streams: 
        print("Hicbir kanal bulunamadi!")
        return

    content = "#EXTM3U\n"
    content += f"# Son Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    
    for s in all_streams:
        logo_attr = f' tvg-logo="{s["logo"]}"' if s.get("logo") else ""
        content += f'#EXTINF:-1 group-title="{s["group"]}"{logo_attr},{s["name"]}\n'
        
        url = s["url"]
        ref = s.get("ref", "")
        
        # Sadece VLC Player ve Web HLS Player uyumlu, AppCreator24'ü bozmayan etiketler
        if ref: 
            content += f'#EXTVLCOPT:http-referrer={ref}\n'
            content += f'#EXTVLCOPT:http-origin={ref}\n'
        content += f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n'
        
        # Linkin sonuna AppCreator24/ExoPlayer'ı çökertecek | karakterini eklemiyoruz, saf haliyle yazdırıyoruz.
        content += f'{url}\n'

    with open(M3U_OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(content)
    print(f"\n[OK] M3U listesi olusturuldu -> {M3U_OUTPUT_FILE}")

if __name__ == "__main__":
    main()
