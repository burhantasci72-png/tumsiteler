print("--- SPOR LİSTESİ OLUŞTURUCU BAŞLATILDI ---")

# 1. ATOM SPOR (En başa ekliyoruz, çünkü en kalitelisi bu)
all_streams.extend(fetch_atom_spor())

# 2. Diğer kaynakları topla
all_streams.extend(fetch_vavoo())
all_streams.extend(fetch_netspor())
all_streams.extend(fetch_trgoals())
all_streams.extend(fetch_selcuk_sporcafe())
all_streams.extend(fetch_andro_nodes())

if not all_streams: 
    print("Hicbir kanal bulunamadi!")
    return

content = "#EXTM3U\n"
content += f"# Son Guncelleme: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
for s in all_streams:
    # Logo varsa ekle, yoksa boş bırak
    logo_attr = f' tvg-logo="{s["logo"]}"' if s.get("logo") else ""
    content += f'#EXTINF:-1 group-title="{s["group"]}"{logo_attr},{s["name"]}\n'
    
    # Referer ve User-Agent varsa VLC option olarak ekle
    if s.get("ref"): 
        content += f'#EXTVLCOPT:http-referrer={s["ref"]}\n'
    
    # Tüm linkler için User-Agent standart olsun
    content += f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n'
    content += f'#EXTHTTP:{"User-Agent"}:{HEADERS["User-Agent"]}\n'
    
    content += f'{s["url"]}\n'

with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
    f.write(content)
print(f"\n[OK] Tum siteler ve kanallar eksiksiz olarak birlestirildi -> {OUTPUT_FILE}")
