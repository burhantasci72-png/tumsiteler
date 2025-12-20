import requests
import re
import datetime
from bs4 import BeautifulSoup

# --- AYARLAR ---
OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# Senin verdiğin çalışan asıl link
WORKING_BS1_URL = "https://andro.adece12.sbs/checklist/receptestt.m3u8"

# --- 1. NETSPOR: AKILLI DEĞİŞTİRME MANTIKLI ---
def fetch_netspor():
    print("[*] Netspor taranıyor (Bozuk bs1 linkleri otomatik onarılıyor)...")
    results = []
    source_url = "https://netspor-amp.xyz/"
    stream_base = "https://andro.adece12.sbs/checklist/" 
    
    try:
        res = requests.get(source_url, headers=HEADERS, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for div in soup.find_all('div', class_='mac', option=True):
            sid = div.get('option')
            title_div = div.find('div', class_='match-takimlar')
            if not title_div: continue
            
            title = title_div.get_text(strip=True)
            
            # Kategori Belirleme
            if div.find_parent('div', id='kontrolPanelKanallar'):
                group = "CANLI TV KANALLARI"
            else:
                group = "Günün Maçları"
                alt = div.find('div', class_='match-alt')
                if alt: title = f"{title} ({alt.get_text(' | ', strip=True)})"

            # --- AKILLI ONARMA (Fix) ---
            # Eğer link androstreamlivebs1 ise (bozuk olan), onu receptestt ile değiştiriyoruz
            if sid == "androstreamlivebs1":
                final_url = WORKING_BS1_URL
                # İsmin yanına çalıştığını belirtmek için bir işaret koyalım (Opsiyonel)
                title = f"⭐ {title}" 
            else:
                final_url = f"{stream_base}{sid}.m3u8"
            
            results.append({
                "name": title, 
                "url": final_url, 
                "group": group, 
                "ref": source_url
            })
    except Exception as e:
        print(f"Netspor Hatası: {e}")
    return results

# --- 2. TRGOALS: TÜM KANALLAR ---
def fetch_trgoals():
    print("[*] Trgoals taranıyor...")
    results = []
    domain = None
    for i in range(1485, 2150):
        test = f"https://trgoals{i}.xyz"
        try:
            if requests.head(test, timeout=1).status_code == 200:
                domain = test; break
        except: continue
    
    if domain:
        trg_channels = {
            "yayin1":"BEIN SPORTS 1","yayinb2":"BEIN SPORTS 2","yayinb3":"BEIN SPORTS 3",
            "yayinss":"S SPORT 1","yayint1":"TIVIBU SPOR 1","yayinex1":"TABII 1"
        }
        for cid, name in trg_channels.items():
            try:
                r = requests.get(f"{domain}/channel.html?id={cid}", headers=HEADERS, timeout=5)
                m = re.search(r'const baseurl = "(.*?)"', r.text)
                if m:
                    results.append({
                        "name": f"TRG - {name}", "url": f"{m.group(1)}{cid}.m3u8",
                        "group": "TRGOALS TV", "ref": f"{domain}/"
                    })
            except: continue
    return results

# --- 3. SELÇUKSPOR: TÜM KANALLAR ---
def fetch_selcuk_sporcafe():
    print("[*] Selçukspor / Sporcafe taranıyor...")
    results = []
    selcuk_list = [
        {"id": "selcukbeinsports1", "n": "BEIN SPORTS 1"}, {"id": "selcukbeinsports2", "n": "BEIN SPORTS 2"},
        {"id": "selcukssport", "n": "S SPORT 1"}, {"id": "selcuktivibuspor1", "n": "TIVIBU SPOR 1"}
    ]
    referer, html_content = None, None
    for i in range(6, 150):
        url = f"https://www.sporcafe{i}.xyz/"
        try:
            res = requests.get(url, headers=HEADERS, timeout=1)
            if "uxsyplayer" in res.text:
                referer, html_content = url, res.text; break
        except: continue
    
    if html_content and referer:
        m_domain = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', html_content)
        if m_domain:
            s_domain = f"https://{m_domain.group(1)}"
            for ch in selcuk_list:
                try:
                    r = requests.get(f"{s_domain}/index.php?id={ch['id']}", headers={**HEADERS, "Referer": referer}, timeout=5)
                    base_m = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', r.text)
                    if base_m:
                        results.append({"name": f"SL - {ch['n']}", "url": f"{base_m.group(1)}{ch['id']}/playlist.m3u8", "group": "SELÇUKSPOR HD", "ref": referer})
                except: continue
    return results

# --- ANA ÇALIŞTIRICI ---
def main():
    all_streams = []
    all_streams.extend(fetch_netspor())
    all_streams.extend(fetch_trgoals())
    all_streams.extend(fetch_selcuk_sporcafe())
    
    if not all_streams: return

    # Dosyayı Oluştur (UTF-8-SIG Türkçe karakterler için)
    content = "#EXTM3U\n"
    content += f"# Birlesik Liste Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    for s in all_streams:
        content += f'#EXTINF:-1 group-title="{s["group"]}",{s["name"]}\n'
        content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'{s["url"]}\n'

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(content)
    print(f"\n[OK] Tum bozuk beIN 1 linkleri receptestt ile degistirildi.")

if __name__ == "__main__":
    main()
