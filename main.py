#!/usr/bin/env python3
"""
Canlı Spor Kanalları - M3U Liste Oluşturucu

Bu modül, çeşitli spor yayın platformlarından kanal bilgilerini toplayarak
M3U formatında bir çıktı dosyası oluşturur.

Kapsanan Platformlar:
    - XSport
    - Taraftarium (Özel ve 24)
    - Selçukspor
    - Andro Panel
    - Netspor
    - Atom Spor
"""

import requests
import re
import datetime
import urllib3
import urllib.parse
import base64
import concurrent.futures
from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Set
from dataclasses import dataclass


# =============================================================================
# YAPILANDIRMA VE SABİTLER
# =============================================================================

@dataclass
class StreamInfo:
    """Yayın bilgilerini tutan veri sınıfı."""
    name: str
    url: str
    group: str
    logo: str = ""
    referrer: str = ""


class Config:
    """Uygulama yapılandırması."""
    M3U_OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    HEADERS = {"User-Agent": USER_AGENT}
    REQUEST_TIMEOUT = 10
    PROXY_URL = "https://proxy.freecdn.workers.dev/?url="
    
    # Çalışan sunucu URL'leri
    WORKING_BS1_URL = "https://andro.evrenesoglu59.lat/checklist/receptestt.m3u8"
    STREAM_BASE_URL = "https://andro.evrenesoglu59.lat/checklist/"


# SSL uyarılarını devre dışı bırak
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def extract_m3u8_from_page(url: str, referrer: Optional[str] = None) -> Optional[str]:
    """
    Verilen sayfa URL'sinden M3U8 yayın linkini çıkarır.
    
    Args:
        url: Taranacak sayfa URL'si
        referrer: Referer başlığı için opsiyonel URL
        
    Returns:
        Bulunan M3U8 URL'si veya None
    """
    try:
        headers = Config.HEADERS.copy()
        if referrer:
            headers["Referer"] = referrer
            
        response = requests.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
        
        def find_m3u8(text: str, base_url: str) -> Optional[str]:
            """Metin içerisinden M3U8 linki bulur."""
            # Direkt M3U8 linki
            match = re.search(r'(https?://[^\s\'">]+\.m3u8[^\s\'">]*)', text)
            if match:
                return match.group(1)
            
            # Relatif M3U8 linki
            rel_match = re.search(r'[\'"](/[^\s\'">]+\.m3u8[^\s\'">]*)[\'"]', text)
            if rel_match:
                parsed = urllib.parse.urlparse(base_url)
                domain = f'{parsed.scheme}://{parsed.netloc}'
                return domain + rel_match.group(1)
            
            # URL encoded M3U8
            encoded_match = re.search(r'(https%3A%2F%2F[^\s\'">]+%2Em3u8[^\s\'">]*)', text)
            if encoded_match:
                return urllib.parse.unquote(encoded_match.group(1))
            
            # Base64 encoded
            for b64_match in re.findall(r'atob\([\'"]([A-Za-z0-9+/=]+)[\'"]\)', text):
                try:
                    decoded = base64.b64decode(b64_match).decode('utf-8')
                    dec_match = re.search(r'(https?://[^\s\'">]+\.m3u8[^\s\'">]*)', decoded)
                    if dec_match:
                        return dec_match.group(1)
                except Exception:
                    pass
            
            # Uzun Base64 string'leri
            for b64_match in re.findall(r'[\'"]([A-Za-z0-9+/=]{40,})[\'"]', text):
                try:
                    decoded = base64.b64decode(b64_match).decode('utf-8')
                    if '.m3u8' in decoded:
                        dec_match = re.search(r'(https?://[^\s\'">]+\.m3u8[^\s\'">]*)', decoded)
                        if dec_match:
                            return dec_match.group(1)
                except Exception:
                    pass
            
            return None
        
        # Ana içerikte ara
        found_url = find_m3u8(response.text, url)
        if found_url:
            return found_url
        
        # Iframe'lerde ara
        iframes = re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', response.text)
        for iframe_src in iframes:
            try:
                iframe_headers = {**Config.HEADERS, "Referer": url}
                iframe_response = requests.get(iframe_src, headers=iframe_headers, timeout=Config.REQUEST_TIMEOUT)
                found_in_iframe = find_m3u8(iframe_response.text, iframe_src)
                if found_in_iframe:
                    return found_in_iframe
                
                # İç içe iframe'ler
                sub_iframes = re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', iframe_response.text)
                for sub_iframe in sub_iframes:
                    try:
                        sub_headers = {**Config.HEADERS, "Referer": iframe_src}
                        sub_response = requests.get(sub_iframe, headers=sub_headers, timeout=Config.REQUEST_TIMEOUT)
                        found_sub = find_m3u8(sub_response.text, sub_iframe)
                        if found_sub:
                            return found_sub
                    except Exception:
                        continue
            except Exception:
                continue
                
    except Exception:
        pass
    
    return None


def create_stream_info(name: str, url: str, group: str, 
                       logo: str = "", referrer: str = "") -> StreamInfo:
    """StreamInfo objesi oluşturur."""
    return StreamInfo(name=name, url=url, group=group, logo=logo, referrer=referrer)


# =============================================================================
# KANAL TOPLAYICI FONKSİYONLAR
# =============================================================================

def fetch_xsport() -> List[StreamInfo]:
    """XSport platformundan kanal bilgilerini toplar."""
    print("[*] XSport taranıyor...")
    results: List[StreamInfo] = []
    base_pattern = "https://www.xsportv{}.xyz/"
    logo = "https://i.hizliresim.com/b6xqz10.jpg"
    
    channel_ids = [
        "xbeinsports-1", "xbeinsports-2", "xbeinsports-3", "xbeinsports-4", "xbeinsports-5",
        "xbeinsportsmax-1", "xbeinsportsmax-2", "xtivibuspor-1", "xtivibuspor-2",
        "xtivibuspor-3", "xtivibuspor-4", "xssport", "xssport2", "xtabiispor1",
        "xtabiispor2", "xtabiispor3", "xtabiispor4", "xtabiispor5", "xtabiispor6", "xtabiispor7"
    ]

    def check_domain(index: int) -> Optional[str]:
        """Domain'in aktif olup olmadığını kontrol eder."""
        url = base_pattern.format(index)
        try:
            response = requests.get(url, headers=Config.HEADERS, timeout=5)
            if response.status_code == 200:
                return url
        except Exception:
            pass
        return None

    def find_active_domain() -> Optional[str]:
        """Aktif domain'i bulur."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check_domain, i) for i in range(56, 1000)]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    return result
        return None

    active_domain = find_active_domain()
    
    if active_domain:
        try:
            response = requests.get(active_domain, headers=Config.HEADERS)
            for channel_id in channel_ids:
                pattern = rf'data-url="(.*?id={channel_id}.*?)"'
                match = re.search(pattern, response.text)
                if match:
                    player_link = match.group(1)
                    try:
                        res = requests.get(player_link, headers=Config.HEADERS, timeout=5)
                        base_match = re.search(r"this\.baseStreamUrl\s*=\s*'(.*?)'", res.text)
                        if base_match:
                            base_url = base_match.group(1)
                            final_url = f"{base_url}{channel_id}/playlist.m3u8"
                            
                            # Kanal adını formatla
                            name = channel_id.replace("x", "").replace("-", " ").upper()
                            if "BEIN" in name:
                                name = name.replace("BEIN", "BEIN SPORTS")
                            
                            results.append(create_stream_info(
                                name=f"XSP - {name}",
                                url=final_url,
                                group="XSPORTV",
                                logo=logo,
                                referrer=active_domain
                            ))
                    except Exception:
                        pass
        except Exception:
            pass
    
    return results


def fetch_taraftarium_ozel() -> List[StreamInfo]:
    """Taraftarium özel kanal linklerini ekler."""
    print("[*] Taraftarium (Özel) kanalları ekleniyor...")
    results: List[StreamInfo] = []
    
    channels = [
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
        results.append(create_stream_info(
            name=name,
            url=url,
            group="TARAFTARIUM"
        ))
    
    return results


def fetch_taraftarium() -> List[StreamInfo]:
    """Taraftarium24'ten canlı maç yayınlarını toplar."""
    print("[*] Taraftarium24 (Canlı Maçlar) taranıyor...")
    results: List[StreamInfo] = []
    base_url = "https://taraftarium24bet.net"
    stream_template = "https://hls.freepalastne.workers.dev/https://corestream.ronaldovurdu.help//hls/{slug}.m3u8"
    
    try:
        response = requests.get(base_url, headers=Config.HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            links = soup.find_all("a", href=True)
            found_slugs: Set[str] = set()
            
            for link in links:
                href = link.get('href', '')
                if "/izle/" in href:
                    slug = href.split("/izle/")[-1].strip("/")
                    if slug and slug not in found_slugs:
                        found_slugs.add(slug)
                        name = slug.replace("-", " ").upper()
                        results.append(create_stream_info(
                            name=f"TRF - {name}",
                            url=stream_template.format(slug=slug),
                            group="TARAFTARIUM24",
                            referrer=base_url
                        ))
    except Exception:
        pass
    
    return results


def fetch_selcuk_sporcafe() -> List[StreamInfo]:
    """Selçukspor/Sporcafe platformundan kanal bilgilerini toplar."""
    print("[*] Selçukspor taranıyor...")
    results: List[StreamInfo] = []
    
    selcuk_channels = [
        {"id": "selcukbeinsports1", "n": "BEIN SPORTS 1"},
        {"id": "selcukbeinsports2", "n": "BEIN SPORTS 2"},
        {"id": "selcukbeinsports3", "n": "BEIN SPORTS 3"},
        {"id": "selcukbeinsports4", "n": "BEIN SPORTS 4"},
        {"id": "selcukbeinsports5", "n": "BEIN SPORTS 5"},
        {"id": "selcukbeinsportsmax1", "n": "BEIN MAX 1"},
        {"id": "selcukbeinsportsmax2", "n": "BEIN MAX 2"},
        {"id": "selcukssport", "n": "S SPORT 1"},
        {"id": "selcukssport2", "n": "S SPORT 2"},
        {"id": "selcuktivibuspor1", "n": "TIVIBU 1"},
        {"id": "selcuktivibuspor2", "n": "TIVIBU 2"},
        {"id": "selcuksmartspor", "n": "SMART SPOR 1"},
        {"id": "selcukaspor", "n": "A SPOR"},
        {"id": "selcukeurosport1", "n": "EUROSPORT 1"}
    ]
    
    referer: Optional[str] = None
    html: Optional[str] = None
    
    # Aktif domain'i bul
    for i in range(6, 150):
        url = f"https://www.sporcafe{i}.xyz/"
        try:
            res = requests.get(url, headers=Config.HEADERS, timeout=1)
            if "uxsyplayer" in res.text:
                referer, html = url, res.text
                break
        except Exception:
            continue
    
    if html and referer:
        domain_match = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', html)
        if domain_match:
            server_domain = f"https://{domain_match.group(1)}"
            for channel in selcuk_channels:
                try:
                    headers = {**Config.HEADERS, "Referer": referer}
                    response = requests.get(f"{server_domain}/index.php?id={channel['id']}", 
                                          headers=headers, timeout=5)
                    base_match = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', response.text)
                    if base_match:
                        results.append(create_stream_info(
                            name=f"SL - {channel['n']}",
                            url=f"{base_match.group(1)}{channel['id']}/playlist.m3u8",
                            group="SELÇUKSPOR HD",
                            referrer=referer
                        ))
                except Exception:
                    continue
    
    return results


def fetch_andro_nodes() -> List[StreamInfo]:
    """Andro Panel'den kanal bilgilerini toplar."""
    print("[*] Andro-Panel taranıyor...")
    results: List[StreamInfo] = []
    
    start_url = "https://taraftariumizle.org"
    channels = [
        ("androstreamlivebiraz1", 'TR:beIN Sport 1 HD'),
        ("androstreamlivebs1", 'TR:beIN Sport 1 HD'),
        ("androstreamlivebs2", 'TR:beIN Sport 2 HD'),
        ("androstreamlivebs3", 'TR:beIN Sport 3 HD'),
        ("androstreamlivebs4", 'TR:beIN Sport 4 HD'),
        ("androstreamlivebs5", 'TR:beIN Sport 5 HD'),
        ("androstreamlivebsm1", 'TR:beIN Sport Max 1 HD'),
        ("androstreamlivebsm2", 'TR:beIN Sport Max 2 HD'),
        ("androstreamlivess1", 'TR:S Sport 1 HD'),
        ("androstreamlivess2", 'TR:S Sport 2 HD'),
        ("androstreamlivets", 'TR:Tivibu Sport HD'),
        ("androstreamlivets1", 'TR:Tivibu Sport 1 HD'),
        ("androstreamlivets2", 'TR:Tivibu Sport 2 HD'),
        ("androstreamlivets3", 'TR:Tivibu Sport 3 HD'),
        ("androstreamlivets4", 'TR:Tivibu Sport 4 HD'),
        ("androstreamlivesm1", 'TR:Smart Sport 1 HD'),
        ("androstreamlivesm2", 'TR:Smart Sport 2 HD'),
        ("androstreamlivees1", 'TR:Euro Sport 1 HD'),
        ("androstreamlivees2", 'TR:Euro Sport 2 HD'),
        ("androstreamlivetb", 'TR:Tabii HD'),
        ("androstreamlivetb1", 'TR:Tabii 1 HD'),
        ("androstreamlivetb2", 'TR:Tabii 2 HD'),
        ("androstreamliveexn", 'TR:Exxen HD'),
        ("androstreamliveexn1", 'TR:Exxen 1 HD'),
    ]
    
    def get_source(url: str, referrer: Optional[str] = None) -> Optional[str]:
        """Proxy üzerinden kaynak kodunu alır."""
        try:
            headers = Config.HEADERS.copy()
            if referrer:
                headers['Referer'] = referrer
            response = requests.get(Config.PROXY_URL + url, headers=headers, verify=False, timeout=20)
            return response.text if response.status_code == 200 else None
        except Exception:
            return None
    
    try:
        html1 = get_source(start_url)
        if html1:
            soup = BeautifulSoup(html1, 'html.parser')
            amp_link = soup.find('link', rel='amphtml')
            if amp_link:
                amp_url = amp_link.get('href')
                html2 = get_source(amp_url)
                if html2:
                    match = re.search(r'\[src\]="appState\.currentIframe".*?src="(https?://[^"]+)"', html2, re.DOTALL)
                    if match:
                        iframe_url = match.group(1)
                        html3 = get_source(iframe_url, referrer=amp_url)
                        if html3:
                            base_urls_match = re.search(r'baseUrls\s*=\s*\[(.*?)\]', html3, re.DOTALL)
                            if base_urls_match:
                                urls_raw = base_urls_match.group(1).replace('"', '').replace("'", "").replace("\n", "").replace("\r", "")
                                servers = [x.strip() for x in urls_raw.split(',') if x.strip().startswith("http")]
                                servers = list(set(servers))
                                
                                # Aktif sunucuları bul
                                active_servers = []
                                test_id = "androstreamlivebs1"
                                for server in servers:
                                    server = server.rstrip('/')
                                    test_url = f"{server}/{test_id}.m3u8" if "checklist" in server else f"{server}/checklist/{test_id}.m3u8"
                                    test_url = test_url.replace("checklist//", "checklist/")
                                    try:
                                        test_response = requests.get(Config.PROXY_URL + test_url, headers=Config.HEADERS, verify=False, timeout=5)
                                        if test_response.status_code == 200:
                                            active_servers.append(server)
                                    except Exception:
                                        pass
                                
                                # Kanal listesini oluştur
                                for server in active_servers:
                                    for channel_id, channel_name in channels:
                                        final_url = f"{server}/{channel_id}.m3u8" if "checklist" in server else f"{server}/checklist/{channel_id}.m3u8"
                                        final_url = final_url.replace("checklist//", "checklist/")
                                        results.append(create_stream_info(
                                            name=f"ANDRO - {channel_name}",
                                            url=final_url,
                                            group="ANDRO SPOR",
                                            logo="https://hizliresim.com/gm50rk9",
                                            referrer="https://taraftariumizle.org/"
                                        ))
        
        print(f"[OK] Andro-Panel: {len(results)} kanal eklendi.")
    except Exception as e:
        print(f"[!] Andro-Panel hatası: {e}")
    
    return results


def fetch_netspor() -> List[StreamInfo]:
    """Netspor platformundan kanal bilgilerini toplar (3 katmanlı güvenlik)."""
    print("[*] Netspor taranıyor...")
    results: List[StreamInfo] = []
    base_domain = "https://netsporcoamp.xyz"
    stream_base = Config.STREAM_BASE_URL
    
    try:
        response = requests.get(base_domain, headers=Config.HEADERS, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # KATMAN 1: Doğrudan ID'leri bul
        for tag in soup.find_all(True):
            stream_id = tag.get('option') or tag.get('data-id')
            if stream_id and isinstance(stream_id, str) and (stream_id.startswith('andro') or stream_id.startswith('net')):
                title = tag.get_text(strip=True)
                if not title:
                    title_div = tag.find('div', class_=re.compile(r'takim|match|title'))
                    if title_div:
                        title = title_div.get_text(strip=True)
                
                if title and len(title) > 2:
                    title = re.sub(r'\s+', ' ', title).strip()
                    final_url = Config.WORKING_BS1_URL if stream_id == "androstreamlivebs1" else f"{stream_base}{stream_id}.m3u8"
                    group = "NETSPOR CANLI MAÇLAR" if " - " in title else "NETSPOR KANALLARI"
                    results.append(create_stream_info(
                        name=f"NET - {title}",
                        url=final_url,
                        group=group,
                        referrer="https://taraftariumizle.org/"
                    ))
        
        # KATMAN 2: Linkleri takip et
        if not results:
            items_to_fetch = []
            seen_links: Set[str] = set()
            
            for anchor in soup.find_all('a', href=True):
                href = anchor.get('href', '')
                if any(skip in href.lower() for skip in ['whatsapp', 't.me', 'twitter', 'instagram', '#', 'apk']):
                    continue
                title = anchor.get_text(strip=True)
                if title and len(title) > 2 and not any(skip in title.lower() for skip in ['uygulama', 'telegram', 'iletişim']):
                    link = href if href.startswith('http') else f"{base_domain.rstrip('/')}/{href.lstrip('/')}"
                    if link not in seen_links:
                        seen_links.add(link)
                        items_to_fetch.append({"title": title, "link": link})
                        
            def process_item(item: Dict) -> Optional[StreamInfo]:
                m3u8_url = extract_m3u8_from_page(item["link"], referrer=base_domain)
                if m3u8_url:
                    keywords = ["BEIN", "SPOR", "TV", "EURO", "SMART"]
                    group = "NETSPOR KANALLARI" if any(k in item["title"].upper() for k in keywords) else "NETSPOR CANLI MAÇLAR"
                    return create_stream_info(
                        name=f"NET - {item['title']}",
                        url=m3u8_url,
                        group=group,
                        referrer="https://taraftariumizle.org/"
                    )
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(process_item, item) for item in items_to_fetch]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        results.append(result)

        # KATMAN 3: Yedek sabit liste
        if not results:
            fallback_channels = [
                ("BeIN Sports 1", "androstreamlivebs1"),
                ("BeIN Sports 2", "androstreamlivebs2"),
                ("BeIN Sports 3", "androstreamlivebs3"),
                ("BeIN Sports 4", "androstreamlivebs4"),
                ("BeIN Sports 5", "androstreamlivebs5"),
                ("BeIN Sports Max 1", "androstreamlivebsm1"),
                ("BeIN Sports Max 2", "androstreamlivebsm2"),
                ("S Sport 1", "androstreamlivess1"),
                ("S Sport 2", "androstreamlivess2"),
                ("Tivibu Spor 1", "androstreamlivets1"),
                ("Tivibu Spor 2", "androstreamlivets2"),
                ("Tivibu Spor 3", "androstreamlivets3"),
                ("Smart Spor 1", "androstreamlivesm1"),
                ("Smart Spor 2", "androstreamlivesm2"),
                ("Exxen Spor 1", "androstreamliveexn1"),
                ("TRT Spor", "androstreamlivetrts"),
                ("A Spor", "androstreamliveaspor"),
                ("Euro Sport 1", "androstreamlivees1")
            ]
            for channel_name, channel_id in fallback_channels:
                final_url = Config.WORKING_BS1_URL if channel_id == "androstreamlivebs1" else f"{stream_base}{channel_id}.m3u8"
                results.append(create_stream_info(
                    name=f"NET - {channel_name}",
                    url=final_url,
                    group="NETSPOR KANALLARI (YEDEK)",
                    referrer="https://taraftariumizle.org/"
                ))
                
    except Exception as e:
        print(f"[!] Netspor hatası: {e}")
        
    return results


def fetch_atom_spor() -> List[StreamInfo]:
    """AtomSpor platformundan kanal bilgilerini toplar."""
    print("[*] AtomSpor taranıyor...")
    results: List[StreamInfo] = []
    base_domain = "https://atomsportv501.top"
    atom_logo = "https://hizliresim.com/gm50rk9b"
    
    channels = [
        ("Bein Sports 1", "bein-sports-1"),
        ("Bein Sports 2", "bein-sports-2"),
        ("Bein Sports 3", "bein-sports-3"),
        ("Bein Sports 4", "bein-sports-4"),
        ("Bein Sports 5", "bein-sports-5"),
        ("S Sport 1", "s-sport"),
        ("S Sport 2", "s-sport-2"),
        ("S Sport Plus", "ssport-plus"),
        ("Tivibu Spor 1", "tivibu-spor-1"),
        ("Tivibu Spor 2", "tivibu-spor-2"),
        ("Tivibu Spor 3", "tivibu-spor-3"),
        ("Smart Spor", "smart-spor"),
        ("TV 8.5", "tv-8-5"),
        ("Bein Sports Haber", "bein-sports-haber")
    ]

    def fetch_single(item: tuple) -> StreamInfo:
        """Tek bir kanal için yayın linki bul."""
        name, channel_id = item
        m3u8_url = extract_m3u8_from_page(f"{base_domain}/kanal/{channel_id}")
        if not m3u8_url:
            m3u8_url = f"https://tv.atomspor.workers.dev/?ID={channel_id}"
        return create_stream_info(
            name=f"ATOM - {name}",
            url=m3u8_url,
            group="ATOM SPOR (VIP)",
            logo=atom_logo,
            referrer=base_domain
        )
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single, channel) for channel in channels]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            
    # Kanalları sırala
    order_map = {f"ATOM - {ch[0]}": i for i, ch in enumerate(channels)}
    results.sort(key=lambda x: order_map.get(x.name, 999))
    
    return results


def fetch_kulis_tv() -> List[StreamInfo]:
    """Kulis TV platformundan canlı maç ve kanal bilgilerini toplar."""
    print("[*] Kulis TV taranıyor...")
    results: List[StreamInfo] = []
    
    # Aktif domain'i bul
    base_pattern = "https://kulistvnew{}.com/"
    
    def check_domain(index: int) -> Optional[str]:
        """Domain'in aktif olup olmadığını kontrol eder."""
        url = base_pattern.format(index)
        try:
            response = requests.get(url, headers=Config.HEADERS, timeout=5)
            if response.status_code == 200 and ("maç" in response.text.lower() or "canlı" in response.text.lower()):
                return url
        except Exception:
            pass
        return None
    
    def find_active_domain() -> Optional[str]:
        """Aktif domain'i bulur."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check_domain, i) for i in range(1, 50)]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    return result
        return None
    
    active_domain = find_active_domain()
    
    if active_domain:
        print(f"    -> Aktif Kulis TV domaini: {active_domain}")
        try:
            main_response = requests.get(active_domain, headers=Config.HEADERS, timeout=10)
            
            # data-reality.com URL'ini bul
            data_url_match = re.search(r"fetch\(['\"]([^'\"]*matches\.php)['\"]", main_response.text)
            if data_url_match:
                data_url = data_url_match.group(1)
                
                # Maç verilerini çek
                data_response = requests.get(data_url, headers=Config.HEADERS, timeout=10)
                soup = BeautifulSoup(data_response.content, "html.parser")
                
                matches = soup.find_all("a", class_=re.compile(r"single-match"))
                
                for match in matches:
                    href = match.get("href", "")
                    if not href:
                        continue
                    
                    # Match ID'yi çıkar
                    match_id = ""
                    if "id=" in href:
                        match_id = href.split("id=")[-1].split("&")[0]
                    
                    # Takım/etkinlik adını bul
                    teams_div = match.find("div", class_="teams")
                    home_team = ""
                    away_team = ""
                    if teams_div:
                        home = teams_div.find("div", class_="home")
                        away = teams_div.find("div", class_="away")
                        if home:
                            home_team = home.get_text(strip=True)
                        if away:
                            away_team = away.get_text(strip=True)
                    
                    # Tarih ve saat
                    event_div = match.find("div", class_="event")
                    event_time = event_div.get_text(strip=True) if event_div else ""
                    
                    date_div = match.find("div", class_="date")
                    date_text = date_div.get_text(strip=True) if date_div else ""
                    
                    # Lig/turnuva bilgisi
                    match_type = match.get("data-matchtype", "Diğer")
                    
                    # Başlık oluştur
                    if home_team and away_team:
                        title = f"{home_team} - {away_team}"
                    elif home_team:
                        title = home_team
                    else:
                        title = f"Maç {match_id}" if match_id else "Canlı Yayın"
                    
                    # Stream URL'i oluştur (channel?id=XXX formatında)
                    if match_id:
                        stream_url = f"{active_domain}channel?id={match_id}"
                        
                        # Grup adı belirle
                        is_live = "Program" not in date_text and event_time and event_time != ""
                        group_name = "KULIS CANLI" if is_live else f"KULIS MAÇLAR - {match_type}"
                        
                        results.append(create_stream_info(
                            name=f"KULIS - {title}",
                            url=stream_url,
                            group=group_name,
                            referrer=active_domain
                        ))
                    
        except Exception as e:
            print(f"    -> Hata: {e}")
    
    return results


def fetch_mahsun_sports() -> List[StreamInfo]:
    """Mahsun Sports platformundan canlı maç ve kanal bilgilerini toplar."""
    print("[*] Mahsun Sports taranıyor...")
    results: List[StreamInfo] = []
    
    # Aktif domain'i bul
    base_pattern = "https://mahsunsports{}.xyz/"
    
    def check_domain(index: int) -> Optional[str]:
        """Domain'in aktif olup olmadığını kontrol eder."""
        url = base_pattern.format(index)
        try:
            response = requests.get(url, headers=Config.HEADERS, timeout=5)
            if response.status_code == 200 and "script" in response.text:
                return url
        except Exception:
            pass
        return None
    
    def find_active_domain() -> Optional[str]:
        """Aktif domain'i bulur."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check_domain, i) for i in range(70, 150)]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    return result
        return None
    
    active_domain = find_active_domain()
    
    if active_domain:
        print(f"    -> Aktif Mahsun Sports domaini: {active_domain}")
        try:
            # Script dosyasını çek (genellikle script4.js veya benzeri)
            script_url = None
            main_response = requests.get(active_domain, headers=Config.HEADERS, timeout=10)
            
            # Script dosyasını bul - "script" kelimesi içeren ve clappr/jquery olmayan dosyalar
            script_matches = re.findall(r'<script[^>]+src=["\']([^"\']*\.js)["\']', main_response.text)
            for script in script_matches:
                if 'script' in script.lower() and 'clappr' not in script.lower() and 'jquery' not in script.lower():
                    # email-decode.min.js gibi cloudflare scriptlerini atla
                    if 'cloudflare' in script.lower() or 'email-decode' in script.lower():
                        continue
                    script_url = script if script.startswith('http') else active_domain + script.lstrip('/')
                    break
            
            if not script_url:
                # Varsayılan script yolu
                script_url = active_domain + "script4.js"
            
            script_response = requests.get(script_url, headers=Config.HEADERS, timeout=10)
            script_content = script_response.text
            
            # Gelişmiş pattern - tüm maç objelerini yakalamak için
            # { "tarih": "...", "time": "...", "league": "...", "title": "...", "url": "...", ... }
            # veya { "time": "...", "league": "...", "title": "...", "url": "...", "id": "...", ... }
            
            # Önce tüm süslü parantez bloklarını bul
            block_pattern = r'\{[^{}]*"title"[^{}]*"url"[^{}]*\}'
            matches = re.findall(block_pattern, script_content, re.DOTALL)
            
            for match in matches:
                try:
                    # Alanları çıkar
                    title_match = re.search(r'"title":\s*"([^"]+)"', match)
                    league_match = re.search(r'"league":\s*"([^"]+)"', match)
                    url_match = re.search(r'"url":\s*"([^"]+)"', match)
                    live_match = re.search(r'"live":\s*(true|false)', match)
                    id_match = re.search(r'"id":\s*"([^"]+)"', match)
                    
                    if title_match and url_match:
                        title = title_match.group(1).strip()
                        league = league_match.group(1).strip() if league_match else "Diğer"
                        url = url_match.group(1).strip()
                        is_live = live_match and live_match.group(1) == 'true'
                        
                        # Stream ID'yi URL'den çıkar
                        stream_id = ""
                        if "id=" in url:
                            # URL formatı: event.html?id=androstreamlivech19893294 veya /event.html?id=xxx
                            stream_id = url.split("id=")[-1].strip()
                        elif id_match:
                            stream_id = id_match.group(1).strip()
                        
                        if stream_id:
                            # Yayın URL'sini oluştur - event.html?formatında
                            stream_url = f"{active_domain}event.html?id={stream_id}"
                            
                            # Grup adını belirle (CANLI ise ayrı, değilse lig bazlı)
                            if is_live or "CANLI" in title.upper() or "LIVE" in title.upper():
                                group_name = "MAHSUN CANLI"
                            else:
                                group_name = f"MAHSUN MAÇLAR - {league}"
                            
                            results.append(create_stream_info(
                                name=f"MAHSUN - {title}",
                                url=stream_url,
                                group=group_name,
                                logo="",
                                referrer=active_domain
                            ))
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"[!] Mahsun Sports hatası: {e}")
    
    return results


# =============================================================================
# M3U DOSYA OLUŞTURUCU
# =============================================================================

def generate_m3u_content(streams: List[StreamInfo]) -> str:
    """Stream listesinden M3U içeriği oluşturur."""
    content = "#EXTM3U\n"
    content += f"# Son Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    
    for stream in streams:
        logo_attr = f' tvg-logo="{stream.logo}"' if stream.logo else ""
        content += f'#EXTINF:-1 group-title="{stream.group}"{logo_attr},{stream.name}\n'
        
        # VLC ve Web Player için standart etiketler
        if stream.referrer:
            content += f'#EXTVLCOPT:http-referrer={stream.referrer}\n'
            content += f'#EXTVLCOPT:http-origin={stream.referrer}\n'
        content += f'#EXTVLCOPT:http-user-agent={Config.USER_AGENT}\n'
        
        content += f'{stream.url}\n'
    
    return content


# =============================================================================
# ANA ÇALIŞTIRICI
# =============================================================================

def main():
    """Ana fonksiyon - tüm kaynakları tarar ve M3U dosyası oluşturur."""
    all_streams: List[StreamInfo] = []
    
    print("--- SPOR LİSTESİ OLUŞTURUCU BAŞLATILDI ---")
    
    # İstenilen sıralama: Atom, Mahsun, Kulis TV, Netspor, Andro, Selçukspor, Taraftarium, XSport
    all_streams.extend(fetch_atom_spor())
    all_streams.extend(fetch_mahsun_sports())
    all_streams.extend(fetch_kulis_tv())
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_andro_nodes())
    all_streams.extend(fetch_selcuk_sporcafe())
    all_streams.extend(fetch_taraftarium())
    all_streams.extend(fetch_taraftarium_ozel())
    all_streams.extend(fetch_xsport())
    
    if not all_streams:
        print("Hiçbir kanal bulunamadı!")
        return
    
    # M3U dosyasını oluştur
    content = generate_m3u_content(all_streams)
    
    with open(Config.M3U_OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(content)
    
    print(f"\n[OK] M3U listesi oluşturuldu -> {Config.M3U_OUTPUT_FILE}")
    print(f"Toplam {len(all_streams)} kanal eklendi.")


if __name__ == "__main__":
    main()
