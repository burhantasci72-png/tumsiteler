#!/usr/bin/env python3
"""
Kaynak toplayicilar.

Her toplayici `List[StreamInfo]` dondurur ve ASLA istisna sizdirmaz.
Hepsi core.py'deki ortak HTTP/kesif katmanini kullanir.

Onemli tasarim kurali: bir toplayici yalnizca gercek `.m3u8` adresi
uretmelidir. Sayfa linki (event.html?id=..., /channel?id=...) uretmek
oynaticinin calismamasina yol acar; bu yuzden bu tur kaynaklarda once
sayfa gezilip m3u8 cikarilir.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Callable, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from core import (
    Settings,
    StreamInfo,
    extract_m3u8,
    find_m3u8_in_text,
    first_match,
    get_text,
    http_get,
    run_parallel,
)

LOGO_DEFAULT = ""


def _log(message: str) -> None:
    print(f"    {message}", flush=True)


# =============================================================================
# DOMAIN KESFI
# =============================================================================

def probe_domain(
    url: str, must_contain: Optional[Tuple[str, ...]] = None
) -> Optional[str]:
    """Domain canli mi? Istege bagli olarak icerik imzasi da aranir."""
    response = http_get(url, timeout=(4, 6))
    if response is None or response.status_code != 200:
        return None
    if must_contain:
        body = response.text.lower()
        if not any(token.lower() in body for token in must_contain):
            return None
    return url


def find_domain(
    pattern: str,
    indexes,
    must_contain: Optional[Tuple[str, ...]] = None,
    fallback: Optional[str] = None,
    label: str = "",
) -> Optional[str]:
    """
    `pattern` icindeki {} yerine indexleri koyarak ilk calisan domaini bulur.

    Paralel tarama yapar ve ilk basarili sonucta durur.
    """
    def check(index) -> Optional[str]:
        return probe_domain(pattern.format(index), must_contain)

    found = first_match(
        check,
        list(indexes),
        Settings.DOMAIN_PROBE_WORKERS,
        budget_seconds=Settings.SOURCE_BUDGET,
    )
    if found:
        _log(f"-> {label or pattern}: aktif domain {found}")
        return found.rstrip("/")

    if fallback and probe_domain(fallback, must_contain):
        _log(f"-> {label or pattern}: yedek domain {fallback}")
        return fallback.rstrip("/")

    _log(f"-> {label or pattern}: aktif domain bulunamadi")
    return None


def resolve_pages(
    entries: List[Tuple[str, str]],
    group: str,
    source: str,
    referrer: str,
    logo: str = "",
) -> List[StreamInfo]:
    """
    (sayfa_url, kanal_adi) listesini gezip m3u8 cikarir.

    Sadece m3u8 bulunanlar dondurulur - sayfa linki yayin degildir.
    """
    def work(entry: Tuple[str, str]) -> Optional[StreamInfo]:
        page_url, name = entry
        m3u8 = extract_m3u8(page_url, referrer=referrer)
        if not m3u8:
            return None
        return StreamInfo(
            name=name,
            url=m3u8,
            group=group,
            logo=logo,
            referrer=referrer,
            source=source,
        )

    return run_parallel(work, entries, Settings.SCRAPE_WORKERS)


# =============================================================================
# 1. XSPORT
# =============================================================================

XSPORT_IDS = [
    "xbeinsports-1", "xbeinsports-2", "xbeinsports-3", "xbeinsports-4",
    "xbeinsports-5", "xbeinsportsmax-1", "xbeinsportsmax-2",
    "xtivibuspor-1", "xtivibuspor-2", "xtivibuspor-3", "xtivibuspor-4",
    "xssport", "xssport2", "xtabiispor1", "xtabiispor2", "xtabiispor3",
    "xtabiispor4", "xtabiispor5", "xtabiispor6", "xtabiispor7",
]


def fetch_xsport() -> List[StreamInfo]:
    """XSport: aktif domaini bulur, oynatici sayfasindan baseStreamUrl ceker."""
    domain = find_domain(
        "https://www.xsportv{}.xyz/",
        range(56, 220),
        must_contain=("data-url", "xsport", "bein"),
        label="XSport",
    )
    if not domain:
        return []

    html = get_text(domain)
    if not html:
        return []

    logo = "https://i.hizliresim.com/b6xqz10.jpg"

    def work(channel_id: str) -> Optional[StreamInfo]:
        match = re.search(rf'data-url="([^"]*id={re.escape(channel_id)}[^"]*)"', html)
        if not match:
            return None
        player_url = urllib.parse.urljoin(domain, match.group(1))
        page = get_text(player_url, referrer=domain)
        if not page:
            return None

        base = re.search(r"this\.baseStreamUrl\s*=\s*['\"]([^'\"]+)", page)
        if base:
            stream_url = f"{base.group(1).rstrip('/')}/{channel_id}/playlist.m3u8"
        else:
            stream_url = find_m3u8_in_text(page, player_url)
        if not stream_url:
            return None

        name = channel_id.lstrip("x").replace("-", " ")
        return StreamInfo(
            name=name,
            url=stream_url,
            group="XSPORT",
            logo=logo,
            referrer=domain,
            source="xsport",
        )

    return run_parallel(work, XSPORT_IDS, Settings.SCRAPE_WORKERS)


# =============================================================================
# 2. TARAFTARIUM (sabit worker kanallari + canli maclar)
# =============================================================================

TARAFTARIUM_WORKER = "https://deathless.pantonum1.workers.dev"

TARAFTARIUM_IDS = [
    ("taraftarium", "beIN Sports 1"), ("b2", "beIN Sports 2"),
    ("b3", "beIN Sports 3"), ("b4", "beIN Sports 4"), ("b5", "beIN Sports 5"),
    ("bm1", "beIN Sports Max 1"), ("bm2", "beIN Sports Max 2"),
    ("ss", "S Sport 1"), ("ss2", "S Sport 2"),
    ("smarts", "Smart Spor 1"), ("sms2", "Smart Spor 2"),
    ("t1", "Tivibu Spor 1"), ("t2", "Tivibu Spor 2"),
    ("t3", "Tivibu Spor 3"), ("t4", "Tivibu Spor 4"),
    ("eu1", "Eurosport 1"), ("eu2", "Eurosport 2"),
    ("trtspor", "TRT Spor"), ("trtspor2", "TRT Spor Yıldız"),
    ("as", "A Spor"), ("atv", "ATV"), ("tv8", "TV 8"), ("tv85", "TV 8.5"),
    ("ex1", "Tabii Spor 1"), ("ex2", "Tabii Spor 2"),
    ("ex3", "Tabii Spor 3"), ("ex4", "Tabii Spor 4"),
]


def fetch_taraftarium_static() -> List[StreamInfo]:
    """Taraftarium worker uzerindeki sabit kanallar."""
    return [
        StreamInfo(
            name=name,
            url=f"{TARAFTARIUM_WORKER}/{slug}.m3u8",
            group="TARAFTARIUM",
            referrer=TARAFTARIUM_WORKER,
            source="taraftarium",
        )
        for slug, name in TARAFTARIUM_IDS
    ]


def fetch_taraftarium_live() -> List[StreamInfo]:
    """Taraftarium24 canli mac yayinlari."""
    domain = find_domain(
        "https://taraftarium24bet{}.net",
        [""] + list(range(1, 40)),
        must_contain=("/izle/",),
        label="Taraftarium24",
    )
    if not domain:
        return []

    html = get_text(domain)
    if not html:
        return []

    template = (
        "https://hls.freepalastne.workers.dev/"
        "https://corestream.ronaldovurdu.help//hls/{slug}.m3u8"
    )

    soup = BeautifulSoup(html, "html.parser")
    results: List[StreamInfo] = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/izle/" not in href:
            continue
        slug = href.split("/izle/")[-1].strip("/")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        title = anchor.get_text(strip=True) or slug.replace("-", " ")
        results.append(
            StreamInfo(
                name=title,
                url=template.format(slug=slug),
                group="TARAFTARIUM24",
                referrer=domain,
                source="taraftarium24",
            )
        )

    return results


# =============================================================================
# 3. SELCUKSPOR
# =============================================================================

SELCUK_IDS = [
    ("selcukbeinsports1", "beIN Sports 1"), ("selcukbeinsports2", "beIN Sports 2"),
    ("selcukbeinsports3", "beIN Sports 3"), ("selcukbeinsports4", "beIN Sports 4"),
    ("selcukbeinsports5", "beIN Sports 5"),
    ("selcukbeinsportsmax1", "beIN Sports Max 1"),
    ("selcukbeinsportsmax2", "beIN Sports Max 2"),
    ("selcukssport", "S Sport 1"), ("selcukssport2", "S Sport 2"),
    ("selcuktivibuspor1", "Tivibu Spor 1"), ("selcuktivibuspor2", "Tivibu Spor 2"),
    ("selcuksmartspor", "Smart Spor 1"), ("selcukaspor", "A Spor"),
    ("selcukeurosport1", "Eurosport 1"),
]


def fetch_selcukspor() -> List[StreamInfo]:
    """Selcukspor / Sporcafe."""
    domain = find_domain(
        "https://www.sporcafe{}.xyz/",
        range(6, 180),
        must_contain=("uxsyplayer",),
        label="Selçukspor",
    )
    if not domain:
        return []

    html = get_text(domain)
    if not html:
        return []

    match = re.search(r"https?://(main\.uxsyplayer[0-9a-zA-Z\-]*\.[a-z]+)", html)
    if not match:
        _log("-> Selçukspor: oynatici sunucusu bulunamadi")
        return []
    server = f"https://{match.group(1)}"

    def work(entry: Tuple[str, str]) -> Optional[StreamInfo]:
        channel_id, name = entry
        page = get_text(f"{server}/index.php?id={channel_id}", referrer=domain)
        if not page:
            return None
        base = re.search(r"this\.adsBaseUrl\s*=\s*['\"]([^'\"]+)", page)
        if base:
            url = f"{base.group(1).rstrip('/')}/{channel_id}/playlist.m3u8"
        else:
            url = find_m3u8_in_text(page, server)
        if not url:
            return None
        return StreamInfo(
            name=name,
            url=url,
            group="SELÇUKSPOR",
            referrer=domain,
            source="selcukspor",
        )

    return run_parallel(work, SELCUK_IDS, Settings.SCRAPE_WORKERS)


# =============================================================================
# 4. ANDRO PANEL
# =============================================================================

ANDRO_IDS = [
    ("androstreamlivebs1", "beIN Sports 1"), ("androstreamlivebs2", "beIN Sports 2"),
    ("androstreamlivebs3", "beIN Sports 3"), ("androstreamlivebs4", "beIN Sports 4"),
    ("androstreamlivebs5", "beIN Sports 5"),
    ("androstreamlivebsm1", "beIN Sports Max 1"),
    ("androstreamlivebsm2", "beIN Sports Max 2"),
    ("androstreamlivess1", "S Sport 1"), ("androstreamlivess2", "S Sport 2"),
    ("androstreamlivets1", "Tivibu Spor 1"), ("androstreamlivets2", "Tivibu Spor 2"),
    ("androstreamlivets3", "Tivibu Spor 3"), ("androstreamlivets4", "Tivibu Spor 4"),
    ("androstreamlivesm1", "Smart Spor 1"), ("androstreamlivesm2", "Smart Spor 2"),
    ("androstreamlivees1", "Eurosport 1"), ("androstreamlivees2", "Eurosport 2"),
    ("androstreamlivetb1", "Tabii Spor 1"), ("androstreamlivetb2", "Tabii Spor 2"),
    ("androstreamliveexn1", "Exxen"),
]

ANDRO_REFERER = "https://taraftariumizle.org/"


def _andro_servers(html: str) -> List[str]:
    """Sayfa icindeki baseUrls dizisini cikarir."""
    match = re.search(r"baseUrls\s*=\s*\[(.*?)\]", html, re.DOTALL)
    if not match:
        return []
    raw = match.group(1).replace('"', "").replace("'", "")
    servers = {
        part.strip().rstrip("/")
        for part in raw.split(",")
        if part.strip().startswith("http")
    }
    return sorted(servers)


def _andro_url(server: str, channel_id: str) -> str:
    if "checklist" in server:
        return f"{server}/{channel_id}.m3u8"
    return f"{server}/checklist/{channel_id}.m3u8"


def fetch_andro() -> List[StreamInfo]:
    """Andro Panel: amp sayfasi -> iframe -> baseUrls sunucu listesi."""
    html = get_text("https://taraftariumizle.org")
    if not html:
        _log("-> Andro: ana sayfa alinamadi")
        return []

    servers: List[str] = _andro_servers(html)

    if not servers:
        soup = BeautifulSoup(html, "html.parser")
        amp = soup.find("link", rel="amphtml")
        if amp and amp.get("href"):
            amp_html = get_text(amp["href"])
            if amp_html:
                servers = _andro_servers(amp_html)
                if not servers:
                    frame = re.search(
                        r'\[src\]="appState\.currentIframe".*?src="(https?://[^"]+)"',
                        amp_html,
                        re.DOTALL,
                    )
                    if frame:
                        inner = get_text(frame.group(1), referrer=amp["href"])
                        if inner:
                            servers = _andro_servers(inner)

    if not servers:
        _log("-> Andro: sunucu listesi bulunamadi")
        return []

    # Hangi sunucular gercekten yayin veriyor?
    def probe(server: str) -> Optional[str]:
        response = http_get(
            _andro_url(server, "androstreamlivebs1"),
            referrer=ANDRO_REFERER,
            timeout=(4, 7),
            stream=True,
        )
        if response is None:
            return None
        try:
            if response.status_code != 200:
                return None
            head = response.raw.read(256, decode_content=True) or b""
        except Exception:
            return None
        finally:
            response.close()
        return server if b"#EXT" in head else None

    active = run_parallel(probe, servers, Settings.SCRAPE_WORKERS)
    if not active:
        _log(f"-> Andro: {len(servers)} sunucudan hicbiri yanit vermedi")
        return []

    _log(f"-> Andro: {len(active)}/{len(servers)} sunucu aktif")

    results: List[StreamInfo] = []
    for server in active:
        for channel_id, name in ANDRO_IDS:
            results.append(
                StreamInfo(
                    name=name,
                    url=_andro_url(server, channel_id),
                    group="ANDRO SPOR",
                    referrer=ANDRO_REFERER,
                    source="andro",
                )
            )
    return results


# =============================================================================
# 5. NETSPOR
# =============================================================================

def fetch_netspor() -> List[StreamInfo]:
    """Netspor: kanal ve canli mac listesi."""
    domain = find_domain(
        "https://netsporco{}.xyz",
        ["amp"] + [f"amp{i}" for i in range(1, 20)],
        must_contain=("androstreamlive", "option", "data-id"),
        label="Netspor",
    )
    if not domain:
        return []

    html = get_text(domain)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    servers = _andro_servers(html) or ["https://andro.evrenesoglu59.lat/checklist"]
    server = servers[0]

    results: List[StreamInfo] = []
    seen = set()

    for tag in soup.find_all(True):
        stream_id = tag.get("option") or tag.get("data-id")
        if not isinstance(stream_id, str):
            continue
        if not stream_id.startswith(("andro", "net")):
            continue

        title = tag.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        title = re.sub(r"\s+", " ", title)

        key = (stream_id, title)
        if key in seen:
            continue
        seen.add(key)

        results.append(
            StreamInfo(
                name=title,
                url=_andro_url(server, stream_id),
                group="NETSPOR",
                referrer=ANDRO_REFERER,
                source="netspor",
            )
        )

    _log(f"-> Netspor: {len(results)} kayit")
    return results


# =============================================================================
# 6. ATOM SPOR
# =============================================================================

ATOM_IDS = [
    ("bein-sports-1", "beIN Sports 1"), ("bein-sports-2", "beIN Sports 2"),
    ("bein-sports-3", "beIN Sports 3"), ("bein-sports-4", "beIN Sports 4"),
    ("bein-sports-5", "beIN Sports 5"),
    ("s-sport", "S Sport 1"), ("s-sport-2", "S Sport 2"),
    ("ssport-plus", "S Sport Plus"),
    ("tivibu-spor-1", "Tivibu Spor 1"), ("tivibu-spor-2", "Tivibu Spor 2"),
    ("tivibu-spor-3", "Tivibu Spor 3"),
    ("smart-spor", "Smart Spor 1"), ("tv-8-5", "TV 8.5"),
    ("bein-sports-haber", "beIN Sports Haber"),
]


def fetch_atom() -> List[StreamInfo]:
    """AtomSpor: kanal sayfalarindan m3u8 cikarir."""
    domain = find_domain(
        "https://atomsportv{}.top",
        range(495, 560),
        must_contain=("kanal", "atom"),
        fallback="https://atomsportv501.top",
        label="AtomSpor",
    )
    if not domain:
        return []

    entries = [(f"{domain}/kanal/{slug}", name) for slug, name in ATOM_IDS]
    return resolve_pages(
        entries,
        group="ATOM SPOR",
        source="atom",
        referrer=domain,
        logo="https://i.hizliresim.com/gm50rk9b.jpg",
    )


# =============================================================================
# 7-10. PANEL TABANLI SITELER (Mahsun / Pasizle / Inadina / Kulisbet)
# =============================================================================

PANEL_CHANNELS = [
    ("zirve", "beIN Sports 1"), ("b2", "beIN Sports 2"), ("b3", "beIN Sports 3"),
    ("b4", "beIN Sports 4"), ("b5", "beIN Sports 5"),
    ("bm1", "beIN Sports Max 1"), ("bm2", "beIN Sports Max 2"),
    ("ss", "S Sport 1"), ("ss2", "S Sport 2"),
    ("smarts", "Smart Spor 1"), ("sms2", "Smart Spor 2"),
    ("t1", "Tivibu Spor 1"), ("t2", "Tivibu Spor 2"),
    ("t3", "Tivibu Spor 3"), ("t4", "Tivibu Spor 4"),
    ("trtspor", "TRT Spor"), ("trtspor2", "TRT Spor Yıldız"),
    ("trt1", "TRT 1"), ("as", "A Spor"), ("atv", "ATV"),
    ("tv8", "TV 8"), ("tv85", "TV 8.5"),
    ("eu1", "Eurosport 1"), ("eu2", "Eurosport 2"),
    ("ex1", "Tabii Spor 1"), ("ex2", "Tabii Spor 2"),
    ("ex3", "Tabii Spor 3"), ("ex4", "Tabii Spor 4"),
]

MAHSUN_CHANNELS = [
    ("androstreamlivebs1", "beIN Sports 1"), ("androstreamlivebs2", "beIN Sports 2"),
    ("androstreamlivebs3", "beIN Sports 3"), ("androstreamlivebs4", "beIN Sports 4"),
    ("androstreamlivemax1", "beIN Sports Max 1"),
    ("androstreamlivemax2", "beIN Sports Max 2"),
    ("androstreamlivesport", "S Sport 1"), ("androstreamlivesport2", "S Sport 2"),
    ("androstreamliveaspor", "A Spor"), ("androstreamliveasmart", "Smart Spor 1"),
    ("androstreamlivetivibu1", "Tivibu Spor 1"),
    ("androstreamlivetivibu2", "Tivibu Spor 2"),
    ("androstreamlivetivibu3", "Tivibu Spor 3"),
    ("androstreamlivetivibu4", "Tivibu Spor 4"),
    ("androstreamlivetrtsport", "TRT Spor"),
    ("androstreamlivetrtsport2", "TRT Spor Yıldız"),
    ("androstreamliveeurosport1", "Eurosport 1"),
    ("androstreamliveeurosport2", "Eurosport 2"),
]


def _fetch_panel(
    label: str,
    pattern: str,
    indexes,
    page_template: str,
    channels: List[Tuple[str, str]],
    group: str,
    source: str,
    must_contain: Optional[Tuple[str, ...]] = None,
    fallback: Optional[str] = None,
) -> List[StreamInfo]:
    """
    Panel tipi siteler icin ortak toplayici.

    ONEMLI: eski surum burada sayfa linkini dogrudan m3u dosyasina yaziyordu;
    bu linkler yayin olmadigi icin hicbir oynaticida calismiyordu. Artik her
    sayfa geziliyor ve yalnizca gercek m3u8 adresi kaydediliyor.
    """
    domain = find_domain(
        pattern, indexes, must_contain=must_contain, fallback=fallback, label=label
    )
    if not domain:
        return []

    entries = [
        (page_template.format(domain=domain, id=channel_id), name)
        for channel_id, name in channels
    ]
    results = resolve_pages(entries, group=group, source=source, referrer=domain)
    _log(f"-> {label}: {len(results)}/{len(entries)} kanalda m3u8 bulundu")
    return results


def fetch_mahsun() -> List[StreamInfo]:
    return _fetch_panel(
        "Mahsun Sports",
        "https://mahsunsports{}.xyz",
        range(70, 160),
        "{domain}/event.html?id={id}",
        MAHSUN_CHANNELS,
        group="MAHSUN SPOR",
        source="mahsun",
        must_contain=("event.html", "androstreamlive"),
    )


def fetch_pasizle() -> List[StreamInfo]:
    return _fetch_panel(
        "Paşizle",
        "https://pasizle{}.com",
        range(800, 920),
        "{domain}/ch.html?id={id}",
        PANEL_CHANNELS,
        group="PAŞİZLE",
        source="pasizle",
        must_contain=("ch.html", "kanal", "spor"),
    )


def fetch_inadina() -> List[StreamInfo]:
    """
    Inadina TV.

    HATA DUZELTMESI: eski surumde tum kanallara ayni ana sayfa adresi
    veriliyordu (kanal id'si hic kullanilmiyordu), yani 31 kayit da aynidir.
    """
    return _fetch_panel(
        "İnadına TV",
        "https://royaltv{}.com",
        range(1, 120),
        "{domain}/ch.html?id={id}",
        PANEL_CHANNELS,
        group="İNADINA TV",
        source="inadina",
        must_contain=("kanal", "spor", "izle"),
    )


def fetch_kulisbet() -> List[StreamInfo]:
    return _fetch_panel(
        "Kulisbet",
        "https://kulistvnew{}.com",
        range(1, 60),
        "{domain}/channel?id={id}",
        PANEL_CHANNELS,
        group="KULISBET",
        source="kulisbet",
        must_contain=("channel", "spor", "mac"),
    )


# =============================================================================
# KAYIT
# =============================================================================

COLLECTORS: List[Tuple[str, Callable[[], List[StreamInfo]]]] = [
    ("XSport", fetch_xsport),
    ("Taraftarium (sabit)", fetch_taraftarium_static),
    ("Taraftarium24 (canlı)", fetch_taraftarium_live),
    ("Selçukspor", fetch_selcukspor),
    ("Andro Panel", fetch_andro),
    ("Netspor", fetch_netspor),
    ("AtomSpor", fetch_atom),
    ("Mahsun Sports", fetch_mahsun),
    ("Paşizle", fetch_pasizle),
    ("İnadına TV", fetch_inadina),
    ("Kulisbet", fetch_kulisbet),
]
