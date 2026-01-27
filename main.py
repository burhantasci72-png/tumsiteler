import requests
import re
import datetime
import urllib3
import json
from bs4 import BeautifulSoup

# --- AYARLAR ---
M3U_OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HTML_OUTPUT_FILE = "index.html"
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

# --- 2. VAVOO ---
def fetch_vavoo():
    print("[*] Vavoo kanalları ekleniyor...")
    results = []
    proxy_base = "https://yildiziptv-turktv.hf.space/proxy/hls/manifest.m3u8?d=https://vavoo.to/vavoo-iptv/play/"
    vavoo_channels = [
        {"n": "beIN SPORTS Haber", "id": "398999553310ffc0558467", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-haber-hd.png"},
        {"n": "beIN SPORTS 1 HD", "id": "257621689779b8fed9899e", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-hd-1-1.png"},
        {"n": "beIN SPORTS 2 FHD", "id": "3694662475b76c08f52108", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-hd-2-1.png"},
        {"n": "beIN SPORTS 3 FHD", "id": "34101675603c7aea8fa6b1", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-hd-3-1.png"},
        {"n": "beIN SPORTS 4 FHD", "id": "293826835381972adead05", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-hd-4.png"},
        {"n": "beIN SPORTS 5 FHD", "id": "400031560107e5581e3624", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-hd-5.png"},
        {"n": "beIN SPORTS MAX 1", "id": "2832430535849b88f81e2d", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-max-1-hd.png"},
        {"n": "beIN SPORTS MAX 2", "id": "34079362426e8ca1ffedf7", "img": "https://www.digiturkburada.com.tr/kanal3/bein-sports-max-2-hd.png"}
    ]
    for ch in vavoo_channels:
        results.append({"name": f"VAVOO - {ch['n']}", "url": f"{proxy_base}{ch['id']}", "group": "VAVOO SPOR (STABIL)", "logo": ch['img'], "ref": ""})
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

# --- 4. TRGOALS (GÜNCELLENDİ: REFERER EKLENDİ) ---
def fetch_trgoals():
    print("[*] Trgoals kanalları ekleniyor...")
    results = []
    worker_url = "https://muddy-morning-480c.burhantasci72.workers.dev/?url="
    target_domain = "https://pq4.d72577a9dd0ec4.sbs/"
    
    # İSTENEN REFERER ADRESİ
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
            "ref": trg_referer, # ARTIK REFERER VAR
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

# ==========================================
#      2. BÖLÜM: HTML OLUŞTURUCU (YENİ)
# ==========================================

def generate_html_player(streams):
    print("[*] TV Box Uyumlu HTML Arayüz oluşturuluyor...")
    
    # Veriyi JSON formatına çevir (HTML içine gömmek için)
    streams_json = json.dumps(streams)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Canlı Spor TV - Web Player</title>
    <!-- HLS.js Player -->
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        :root {{ --bg: #121212; --card-bg: #1e1e1e; --accent: #e50914; --focus: #ffffff; --text: #eee; }}
        body {{ margin: 0; padding: 0; background-color: var(--bg); color: var(--text); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; overflow: hidden; }}
        
        /* Layout */
        #app {{ display: flex; flex-direction: column; height: 100vh; }}
        
        /* Top Navigation (Categories) */
        #nav-container {{ padding: 10px 0; background: #000; box-shadow: 0 2px 10px rgba(0,0,0,0.5); z-index: 10; }}
        #categories {{ display: flex; overflow-x: auto; gap: 10px; padding: 0 20px; scroll-behavior: smooth; -webkit-overflow-scrolling: touch; scrollbar-width: none; }}
        #categories::-webkit-scrollbar {{ display: none; }}
        .cat-btn {{ 
            background: #333; color: #aaa; border: none; padding: 10px 20px; border-radius: 20px; white-space: nowrap; cursor: pointer; font-size: 14px; transition: all 0.2s; flex-shrink: 0;
        }}
        .cat-btn.active {{ background: var(--accent); color: white; font-weight: bold; transform: scale(1.05); }}
        .cat-btn:focus {{ outline: 3px solid var(--focus); box-shadow: 0 0 10px var(--focus); }}

        /* Main Content */
        #main-content {{ flex: 1; position: relative; overflow: hidden; }}
        #channels-container {{ height: 100%; overflow-y: auto; padding: 20px; box-sizing: border-box; }}
        
        .channel-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; padding-bottom: 50px;
        }}

        /* Channel Card */
        .card {{ 
            background: var(--card-bg); border-radius: 8px; padding: 10px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; display: flex; flex-direction: column; align-items: center; text-align: center; height: 140px; position: relative;
        }}
        .card img {{ width: 50px; height: 50px; object-fit: contain; margin-bottom: 10px; }}
        .card .title {{ font-size: 13px; font-weight: 500; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
        .card:hover {{ background: #2a2a2a; }}
        /* TV Focus State */
        .card:focus {{ 
            outline: 4px solid var(--focus); transform: scale(1.05); z-index: 2; background: #333; box-shadow: 0 0 15px rgba(255,255,255,0.3);
        }}

        /* Player Modal */
        #player-modal {{ 
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: black; z-index: 100; display: none; flex-direction: column; justify-content: center; align-items: center; 
        }}
        video {{ width: 100%; height: 100%; max-height: 100vh; }}
        #close-btn {{ 
            position: absolute; top: 20px; right: 20px; background: rgba(0,0,0,0.7); color: white; border: 2px solid white; padding: 10px 20px; cursor: pointer; z-index: 101; font-weight: bold; border-radius: 5px; 
        }}
        #close-btn:focus {{ background: var(--accent); outline: 3px solid white; }}

        /* Info Message */
        .info {{ position: absolute; bottom: 10px; left: 0; width: 100%; text-align: center; color: #555; font-size: 12px; pointer-events: none; }}

    </style>
</head>
<body>

    <div id="app">
        <!-- Categories -->
        <div id="nav-container">
            <div id="categories">
                <button class="cat-btn active" onclick="filterChannels('ALL')" data-cat="ALL">Tümü</button>
            </div>
        </div>

        <!-- Channel List -->
        <div id="main-content">
            <div id="channels-container">
                <div id="grid" class="channel-grid"></div>
            </div>
            <div class="info">TV Box: Kumanda OK tuşu ile açın. Mobilde: Sağa/Sola kaydırarak kategori değiştirin.</div>
        </div>
    </div>

    <!-- Video Player Overlay -->
    <div id="player-modal">
        <button id="close-btn" onclick="closePlayer()">KAPAT (BACK)</button>
        <video id="video" controls autoplay></video>
    </div>

    <script>
        // Python'dan gelen veri
        const allStreams = {streams_json};
        
        // Grupları (Kategorileri) çıkar
        const groups = [...new Set(allStreams.map(s => s.group))].sort();
        const categoriesDiv = document.getElementById('categories');
        const gridDiv = document.getElementById('grid');
        let currentCategory = 'ALL';
        let currentStreams = [];

        // Kategorileri oluştur
        groups.forEach(g => {{
            const btn = document.createElement('button');
            btn.className = 'cat-btn';
            btn.innerText = g;
            btn.onclick = () => filterChannels(g);
            btn.dataset.cat = g;
            categoriesDiv.appendChild(btn);
        }});

        // Kanal Filtreleme
        function filterChannels(category) {{
            currentCategory = category;
            
            // Buton aktifliği
            document.querySelectorAll('.cat-btn').forEach(b => {{
                b.classList.toggle('active', b.dataset.cat === category);
            }});

            // Grid temizle
            gridDiv.innerHTML = '';
            
            // Veriyi filtrele
            currentStreams = category === 'ALL' ? allStreams : allStreams.filter(s => s.group === category);
            
            // Kartları oluştur
            currentStreams.forEach((s, index) => {{
                const card = document.createElement('div');
                card.className = 'card';
                card.tabIndex = 0; // Odaklanabilir yap (TV için)
                card.onclick = () => playStream(s.url);
                card.dataset.index = index; // Navigasyon için
                
                // Logo varsa kullan yoksa varsayılan
                const logo = s.logo || 'https://cdn-icons-png.flaticon.com/512/3503/3503683.png';
                
                card.innerHTML = `
                    <img src="${{logo}}" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3503/3503683.png'">
                    <div class="title">${{s.name}}</div>
                `;
                
                // Enter tuşu ile oynat (TV Box)
                card.addEventListener('keydown', (e) => {{
                    if (e.key === 'Enter') playStream(s.url);
                }});

                gridDiv.appendChild(card);
            }});
            
            // Scrollu başa al
            document.getElementById('channels-container').scrollTop = 0;
        }}

        // İlk yükleme
        filterChannels('ALL');

        // --- PLAYER FONKSİYONLARI ---
        const modal = document.getElementById('player-modal');
        const video = document.getElementById('video');
        let hls = null;

        function playStream(url) {{
            modal.style.display = 'flex';
            document.getElementById('close-btn').focus(); // Focus'u kapat butonuna ver

            if (Hls.isSupported()) {{
                if (hls) hls.destroy();
                hls = new Hls();
                hls.loadSource(url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
            }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                video.src = url;
                video.addEventListener('loadedmetadata', () => video.play());
            }}
        }}

        function closePlayer() {{
            modal.style.display = 'none';
            video.pause();
            if(hls) hls.destroy();
            // Focus'u son aktif karta döndür (İsteğe bağlı, şimdilik grid'e dön)
            const firstCard = document.querySelector('.card');
            if(firstCard) firstCard.focus();
        }}

        // --- TV BOX NAVİGASYON (SPATIAL NAVIGATION) ---
        // Yön tuşları ile odak yönetimi
        document.addEventListener('keydown', function(e) {{
            // Back tuşları (Tizen, WebOS, Standart)
            if (e.key === 'Backspace' || e.key === 'Escape' || e.keyCode === 10009 || e.keyCode === 461) {{
                if(modal.style.display === 'flex') {{
                    closePlayer();
                }}
            }}

            const focusable = Array.from(document.querySelectorAll('.cat-btn, .card, #close-btn'));
            const current = document.activeElement;
            const currentIndex = focusable.indexOf(current);

            // Eğer hiç odak yoksa ilkine odakla
            if (currentIndex === -1 && focusable.length > 0) {{
                focusable[0].focus();
                return;
            }}
            
            // Basit yukarı/aşağı/sağ/sol mantığı (Grid ve Liste arası geçiş için)
            // Not: Tarayıcı varsayılan olarak yön tuşlarını yönetir ama bazen manuel müdahale gerekir.
            // Bu basit scriptte varsayılan tarayıcı davranışı (tabindex) çoğunlukla yeterlidir.
            // Ancak Kategoriden Gride geçişi kolaylaştıralım:
            
            if (e.key === 'ArrowDown' && current.classList.contains('cat-btn')) {{
                e.preventDefault();
                const firstCard = document.querySelector('.card');
                if (firstCard) firstCard.focus();
            }}
            
            if (e.key === 'ArrowUp' && current.classList.contains('card')) {{
                // Eğer en üst sıradaysa kategoriye çık
                const gridRect = gridDiv.getBoundingClientRect();
                const cardRect = current.getBoundingClientRect();
                if (cardRect.top - gridRect.top < 100) {{
                     e.preventDefault();
                     document.querySelector('.cat-btn.active').focus();
                }}
            }}
        }});

        // --- MOBİL İÇİN SWIPE (SAĞA/SOLA KAYDIRARAK KATEGORİ DEĞİŞTİRME) ---
        let touchStartX = 0;
        let touchEndX = 0;
        const contentDiv = document.getElementById('main-content');

        contentDiv.addEventListener('touchstart', e => {{
            touchStartX = e.changedTouches[0].screenX;
        }});

        contentDiv.addEventListener('touchend', e => {{
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        }});

        function handleSwipe() {{
            const threshold = 100; // Algılama hassasiyeti
            if (touchEndX < touchStartX - threshold) {{
                // Sola Kaydır -> Sonraki Kategori
                changeCategory(1);
            }}
            if (touchEndX > touchStartX + threshold) {{
                // Sağa Kaydır -> Önceki Kategori
                changeCategory(-1);
            }}
        }}

        function changeCategory(direction) {{
            const cats = ['ALL', ...groups];
            let idx = cats.indexOf(currentCategory);
            
            if (idx === -1) idx = 0;
            let newIdx = idx + direction;
            
            if (newIdx < 0) newIdx = cats.length - 1;
            if (newIdx >= cats.length) newIdx = 0;
            
            const newCat = cats[newIdx];
            filterChannels(newCat);
            
            // Kategori butonunu görünür yap (Scroll et)
            const activeBtn = document.querySelector(`.cat-btn[data-cat="${{newCat}}"]`);
            if(activeBtn) {{
                activeBtn.scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
            }}
        }}

    </script>
</body>
</html>
    """
    
    with open(HTML_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] HTML Player oluşturuldu: {HTML_OUTPUT_FILE}")


# ==========================================
#      3. BÖLÜM: ANA ÇALIŞTIRICI
# ==========================================

def main():
    all_streams = []
    print("--- SPOR LİSTESİ OLUŞTURUCU BAŞLATILDI ---")
    
    # Tüm kaynakları çek
    all_streams.extend(fetch_atom_spor())
    all_streams.extend(fetch_vavoo())
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_trgoals()) 
    all_streams.extend(fetch_inadina_tv())
    all_streams.extend(fetch_taraftarium())
    all_streams.extend(fetch_selcuk_sporcafe())
    all_streams.extend(fetch_andro_nodes())
    
    if not all_streams: 
        print("Hicbir kanal bulunamadi!")
        return

    # 1. M3U Dosyasını Oluştur
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

    # 2. HTML Player Dosyasını Oluştur
    generate_html_player(all_streams)

if __name__ == "__main__":
    main()
