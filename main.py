import requests
import re
import datetime
from bs4 import BeautifulSoup

# --- AYARLAR ---
OUTPUT_FILE = "Canli_Spor_Hepsi.m3u"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

def fetch_netspor():
    print("\n--- [SİTE: NETSPOR TAM TARAMA] ---")
    channels_list = []
    matches_list = []
    source_url = "https://netspor-amp.xyz/"
    stream_base = "https://andro.6441255.xyz/checklist/" # Senin kullandığın stream sunucusu
    
    try:
        res = requests.get(source_url, headers=HEADERS, timeout=15)
        res.encoding = 'utf-8' # Karakter sorunu için zorunlu
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. CANLI TV KANALLARI (Bein, Tivibu vb.)
        # HTML'deki id="kontrolPanelKanallar" kısmına bakıyoruz
        ch_section = soup.find('section', id='kontrolPanelKanallar')
        if ch_section:
            for div in ch_section.find_all('div', class_='mac', option=True):
                sid = div.get('option')
                t_div = div.find('div', class_='match-takimlar')
                if sid and t_div:
                    name = t_div.get_text(strip=True)
                    channels_list.append({
                        "name": name,
                        "url": f"{stream_base}{sid}.m3u8",
                        "group": "CANLI TV KANALLARI",
                        "ref": source_url, "logo": ""
                    })
            print(f"[OK] Netspor: {len(channels_list)} sabit kanal bulundu.")

        # 2. GÜNÜN MAÇLARI (Futbol, Basketbol, Tenis, Voleybol)
        # HTML'deki id="kontrolPanel" kısmındaki tüm maçları topluyoruz
        match_section = soup.find('div', id='kontrolPanel')
        if match_section:
            # Tüm kategori-blok'ları gez (canlı, futbol, basketbol...)
            all_match_divs = match_section.find_all('div', class_='mac', option=True)
            for div in all_match_divs:
                sid = div.get('option')
                t_div = div.find('div', class_='match-takimlar')
                if sid and t_div:
                    # Takımlar
                    teams = t_div.get_text(strip=True).replace("CANLI", "").strip()
                    # Alt bilgi (Saat | Lig)
                    alt = div.find('div', class_='match-alt')
                    info = alt.get_text(" | ", strip=True) if alt else ""
                    
                    # Eğer maç zaten listede yoksa ekle (tekrarları önlemek için)
                    match_name = f"{teams} ({info})"
                    if not any(m['url'] == f"{stream_base}{sid}.m3u8" for m in matches_list):
                        matches_list.append({
                            "name": match_name,
                            "url": f"{stream_base}{sid}.m3u8",
                            "group": "Günün Maçları",
                            "ref": source_url, "logo": ""
                        })
            print(f"[OK] Netspor: {len(matches_list)} güncel maç bulundu.")

        return channels_list + list(reversed(matches_list)), "BAŞARILI"
    except Exception as e:
        print(f"[!] Netspor Hatası: {e}")
        return [], f"HATA: {str(e)}"

def fetch_trgoals():
    # ... (Önceki Trgoals kodun aynı kalabilir, buraya sadece özet ekliyorum)
    results = []
    # (Buradaki mantık aynı kalsın, Trgoals fonksiyonunu olduğu gibi koruyabilirsin)
    return results, "ATLANDI (Hız için)" 

def fetch_selcuk_sporcafe():
    # ... (Önceki Selçukspor kodun aynı kalabilir)
    return [], "ATLANDI (Hız için)"

def main():
    all_streams = []
    
    # Sadece Netspor'u tam kapasite çalıştıralım (İstersen diğerlerini buraya ekle)
    netspor_res, msg = fetch_netspor()
    all_streams.extend(netspor_res)
    
    if not all_streams:
        print("\n[!] Hiçbir veri çekilemedi.")
        return

    # M3U Dosyası Oluşturma
    # UTF-8-SIG kullanarak hem Windows hem Mobil cihazlarda Türkçe karakterleri garanti ediyoruz.
    content = "#EXTM3U\n"
    content += f"# Son Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    
    for s in all_streams:
        content += f'#EXTINF:-1 group-title="{s["group"]}",{s["name"]}\n'
        content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
        content += f'{s["url"]}\n'

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(content)
    print(f"\n[OK] İşlem tamamlandı. '{OUTPUT_FILE}' hazır.")

if __name__ == "__main__":
    main()
