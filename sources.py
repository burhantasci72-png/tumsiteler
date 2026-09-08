#!/usr/bin/env python3
"""
Kaynak toplayicilar.

Her toplayici `List[StreamInfo]` dondurur ve ASLA istisna sizdirmaz.
Hepsi core.py'deki ortak HTTP/kesif katmanini kullanir.

Onemli tasarim kurallari:
  1. Bir toplayici yalnizca gercek `.m3u8` adresi uretmelidir. Sayfa linki
     (event.html?id=..., /channel?id=...) uretmek oynaticinin calismamasina
     yol acar; bu yuzden bu tur kaynaklarda once sayfa gezilip m3u8 cikarilir.
  2. DOMAINLER SUREKLI DEGISIR. Bu yuzden:
       - Her ailenin "seed" (bilinen guncel) adresleri + uretilen aday
         araliklari paralel taranir,
       - Bulunan sayfadaki "GUNCEL ADRESIMIZ: ..." duyurusu takip edilir,
       - Sayfadaki aile desenine uyan diger domainler de hasat edilir,
       - Yonlenen (redirect edilen) SON adres kullanilir.
  3. Yayin sunuculari (checklist) ASLA tek bir koda gomulu adrese baglanmaz;
     sayfalardan + onceki basarili listeden (channels.json) toplanip
     canlilik testinden gecenler kullanilir.
"""

from __future__ import annotations

import json
import os
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
    read_chunk,
    run_parallel,
)

LOGO_DEFAULT = ""

# Calisma raporlari: aile -> bulunulan durum (health_report icin)
FAMILY_STATUS: Dict[str, str] = {}


def _log(message: str) -> None:
    print(f"    {message}", flush=True)


# =============================================================================
# DOMAIN KESFI (kendi kendini guncelleyen katman)
# =============================================================================

# Aile yapilandirmasi:
#   seeds    : bilinen/duyurulan guncel adresler (ilk bunlar denenir)
#   patterns : (sablon, indexler) — eski "numarali domain" aileleri
#   signature: sayfanin bu aileye ait oldugunu gosteren icerik imzalari (OR)
FAMILIES: Dict[str, Dict] = {
    "xsport": {
        "label": "XSport",
        "seeds": [],
        "patterns": [("https://www.xsportv{}.xyz/", range(56, 300))],
        "signature": ("data-url", "xsport", "bein"),
    },
    "taraftarium24": {
        "label": "Taraftarium24",
        "seeds": [
            "https://taraftarium24-gsfb.com",
            "https://taraftarium24-off12.com",
        ],
        "patterns": [
            ("https://taraftarium24bet{}.net", [""] + list(range(1, 60))),
            ("https://taraftarium24hd{}.net", list(range(1, 60))),
        ],
        "signature": ("/izle/", "canli", "maç", "mac"),
    },
    "selcuk": {
        "label": "Selçukspor",
        "seeds": [
            "https://selcuksporlive.top",
            "https://selcuksports-hd.com",
            "https://selcuksportshd.is",
            "https://selcuksportshd.su",
        ],
        "patterns": [
            ("https://www.sporcafe{}.xyz/", range(1, 220)),
            ("https://selcuksports{}.top", range(1, 260)),
        ],
        "signature": ("uxsyplayer", "selcuk", "kanal", "izle"),
    },
    "netspor": {
        "label": "Netspor",
        "seeds": ["https://netsporcoamp.xyz"],
        "patterns": [
            ("https://netsporco{}.xyz", ["amp"] + [f"amp{i}" for i in range(1, 40)]),
            ("https://netsporco{}.com", ["amp"] + [f"amp{i}" for i in range(1, 20)]),
        ],
        "signature": ("androstreamlive", "option", "data-id", "checklist"),
    },
    "atom": {
        "label": "AtomSpor",
        "seeds": [],
        "patterns": [("https://atomsportv{}.top", range(400, 720))],
        "signature": ("kanal", "atom"),
    },
    "mahsun": {
        "label": "Mahsun Sports",
        "seeds": [
            "https://mahsunsports.xyz",
            "https://tr-mahsunsports.xyz",
        ],
        "patterns": [("https://mahsunsports{}.xyz", range(1, 220))],
        "signature": ("event.html", "androstreamlive", "mahsun"),
    },
    "pasizle": {
        "label": "Paşizle",
        "seeds": [],
        "patterns": [("https://pasizle{}.com", range(700, 1000))],
        "signature": ("ch.html", "kanal", "spor"),
    },
    "inadina": {
        "label": "İnadına TV",
        "seeds": [],
        "patterns": [("https://royaltv{}.com", range(1, 220))],
        "signature": ("kanal", "spor", "izle"),
    },
    "kulisbet": {
        "label": "Kulisbet",
        "seeds": [],
        "patterns": [("https://kulistvnew{}.com", range(1, 160))],
        "signature": ("channel", "spor", "mac"),
    },
}

# "GUNCEL ADRESIMIZ: ..." duyurusu (paneller kendi yeni adreslerini boyle ilan eder)
# Hem "GÜNCEL" hem "GUNCEL" (Türkçe karakterler kaybolmus) yazimlarini kapsar.
_GUNCEL_RE = re.compile(
    r"g[üu]?ncel\s+adres[a-zıİ]*\s*[:\-]?\s*"
    r"(?:<a[^>]+href=[\"']?)?(https?://[a-z0-9.\-]+(?::\d+)?(?:/[^\s\"'<>)]*)?)",
    re.I,
)
_GUNCEL_ANCHOR_RE = re.compile(
    r"<a[^>]+href=[\"'](https?://[a-z0-9.\-][^\"']+)[\"'][^>]*>[^<]*g[üu]?ncel", re.I
)


def _family_domain_regex(family) -> re.Pattern:
    """Aile desenlerinden domain hasat regex'i uretir."""
    cfg = family if isinstance(family, dict) else FAMILIES[family]
    template = cfg["patterns"][0][0] if cfg["patterns"] else ""
    if not template:
        # Hasat deseni yok (yalnizca seed kullanan aile)
        return re.compile(r"(?!x)x")
    netloc = urllib.parse.urlparse(template).netloc
    stem = netloc.split(".")[1] if netloc.startswith("www.") else netloc.split(".")[0]
    stem = stem.split("{")[0] or cfg["label"]
    return re.compile(
        r"https?://(?:[a-z0-9\-]*\.)*" + re.escape(stem) + r"[a-z0-9\-]*\.[a-z]{2,}",
        re.I,
    )


def _harvest_family_urls(family, html: str, limit: int = 8) -> List[str]:
    """Bir metin icinde aile desenine uyan (alt domainler dahil) adresleri toplar."""
    if not html:
        return []
    regex = _family_domain_regex(family)
    found: List[str] = []
    for match in regex.finditer(html):
        url = match.group(0).rstrip(".,;\\\"')")
        if url not in found:
            found.append(url)
        if len(found) >= limit:
            break
    return found


def _guncel_address_candidates(html: str, base_url: str) -> List[str]:
    """Sayfadaki 'GUNCEL ADRES' duyurularindan aday adresler cikarir.

    Kok path'li duyurular netloc'a indirgenir; path'li olanlar (testler ve
    alt-sayfa duyurulari icin) path'iyle korunur.
    """
    if not html:
        return []
    candidates: List[str] = []
    for match in _GUNCEL_RE.findall(html):
        candidates.append(match if match.startswith("http") else f"https://{match}")
    for match in _GUNCEL_ANCHOR_RE.findall(html):
        candidates.append(match)
    cleaned: List[str] = []
    seen_keys = set()
    for url in candidates:
        url = url.rstrip("/\\\"'<>)].,;")
        parsed = urllib.parse.urlparse(
            url if url.startswith("http") else f"https://{url}"
        )
        if not parsed.netloc:
            continue
        if parsed.path and parsed.path != "/":
            final = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        else:
            final = f"{parsed.scheme}://{parsed.netloc}"
        if final not in seen_keys:
            seen_keys.add(final)
            cleaned.append(final)
    return cleaned


def probe_domain(
    url: str, must_contain: Optional[Tuple[str, ...]] = None
) -> Optional[str]:
    """Domain canli mi? Istege bagli icerik imzasi da aranir.

    BASARILI olursa YONLENEN SON adresi dondurur (eski domain yeni domaine
    yonleniyorsa artik yeni adresi kullaniriz).
    """
    response = http_get(url, timeout=(4, 7), page=True)
    if response is None or response.status_code != 200:
        return None
    final_url = getattr(response, "url", None) or url
    if must_contain:
        body = (getattr(response, "text", "") or "").lower()
        if not body:
            try:
                response.close()
            except Exception:
                pass
            return None
        if not any(token.lower() in body for token in must_contain):
            try:
                response.close()
            except Exception:
                pass
            return None
    try:
        response.close()
    except Exception:
        pass
    return final_url.rstrip("/")


def find_domain(family) -> Optional[str]:
    """Bir ailenin AKTIF ve GUNCEL domainini bulur.

    `family` ya FAMILIES icindeki bir anahtar ya da dogrudan bir
    yapilandirma sozlugu olabilir (testler icin).

    Sirasiyla: seeds -> uretilmis araliklar taranir; bulunan sayfadaki
    'GUNCEL ADRES' duyurusu takip edilir; aile domainleri de hasat edilir.
    """
    cfg = family if isinstance(family, dict) else FAMILIES[family]
    label = cfg["label"]
    status_key = family if isinstance(family, str) else label
    signature = cfg.get("signature") or None

    candidates: List[str] = list(cfg.get("seeds", []))
    for template, indexes in cfg.get("patterns", []):
        candidates.extend(template.format(index) for index in indexes)

    found = first_match(
        lambda url: probe_domain(url, signature),
        candidates,
        Settings.DOMAIN_PROBE_WORKERS,
        budget_seconds=Settings.SOURCE_BUDGET,
    )
    if not found:
        FAMILY_STATUS[status_key] = "domain-bulunamadi"
        _log(f"-> {label}: aktif domain bulunamadi")
        return None

    # 1) Bulunan sayfada "GUNCEL ADRESIMIZ" duyurusu var mi?
    html = get_text(found) or ""
    if html:
        for candidate in _guncel_address_candidates(html, found)[:3]:
            if candidate.rstrip("/") == found.rstrip("/"):
                continue
            current = probe_domain(candidate, signature)
            if current:
                _log(f"-> {label}: duyurulan guncel adres {current}")
                FAMILY_STATUS[status_key] = f"guncel-adres: {current}"
                return current

        # 2) Sayfada aile desenine uyan baska domainler var mi?
        harvested = [u for u in _harvest_family_urls(family, html)
                     if urllib.parse.urlparse(u).netloc != urllib.parse.urlparse(found).netloc]
        for candidate in harvested[:3]:
            current = probe_domain(candidate, signature)
            if current:
                _log(f"-> {label}: hasat edilen domain {current}")
                FAMILY_STATUS[status_key] = f"hasat: {current}"
                return current

    FAMILY_STATUS[status_key] = found
    _log(f"-> {label}: aktif domain {found}")
    return found.rstrip("/")


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


def _fetch_panel(family: str, page_template: str,
                 channels: List[Tuple[str, str]], group: str, source: str,
                 logo: str = "") -> List[StreamInfo]:
    """Panel tipi siteler icin ortak toplayici (domain kefi + sayfa gezme)."""
    domain = find_domain(family)
    if not domain:
        return []

    entries = [
        (page_template.format(domain=domain, id=channel_id), name)
        for channel_id, name in channels
    ]
    results = resolve_pages(entries, group=group, source=source,
                            referrer=domain, logo=logo)
    label = FAMILIES[family]["label"]
    _log(f"-> {label}: {len(results)}/{len(entries)} kanalda m3u8 bulundu")
    FAMILY_STATUS[family if isinstance(family, str) else label] = (
        f"m3u8 {len(results)}/{len(entries)} ({domain})"
    )
    return results


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
    domain = find_domain("xsport")
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
    """Taraftarium worker uzerindeki sabit kanallar.

    NOT: Bu adresteki origin zaman zaman Cloudflare tarafindan engelleniyor
    (o zaman m3u8 yerine blok sayfasi doner). Dogrulama katmani bozuk olanlari
    listeden duserek korur.
    """
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
    domain = find_domain("taraftarium24")
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

    FAMILY_STATUS["taraftarium24-mac"] = f"{len(results)} mac"
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


_SELCUK_PLAYER_RE = re.compile(
    r"https?://((?:main|player|www)\.uxsyplayer[0-9a-zA-Z\-]*\.[a-z]+)", re.I
)
_SELCUK_SITE_RE = re.compile(
    r"https?://(?:www\.)?(?:selcuksports?(?:hd)?|sporcafe|xyzsports)[a-z0-9\-]*\.[a-z]{2,}/?",
    re.I,
)


def _selcuk_player_server(html: str) -> Optional[str]:
    match = _SELCUK_PLAYER_RE.search(html or "")
    return f"https://{match.group(1)}" if match else None


def _selcuk_site_links(html: str) -> List[str]:
    """Giris sayfasindaki asil site linkleri (sira korunur, tekrarsiz)."""
    found: List[str] = []
    for match in _SELCUK_SITE_RE.finditer(html or ""):
        url = match.group(0).rstrip("/")
        if url not in found:
            found.append(url)
    return found


def fetch_selcukspor() -> List[StreamInfo]:
    """Selcukspor / Sporcafe."""
    domain = find_domain("selcuk")
    if not domain:
        return []

    html = get_text(domain)
    if not html:
        return []

    server = _selcuk_player_server(html)
    if not server:
        # Seed adresler cogunlukla "giris" sayfasidir: asil site, sayfadaki
        # ilk selcuk/sporcafe/xyzsports linkinin arkasindadir. Oraya da bak.
        for candidate in _selcuk_site_links(html)[:4]:
            inner = get_text(candidate, referrer=domain)
            if not inner:
                continue
            server = _selcuk_player_server(inner)
            if server:
                _log(f"-> Selçukspor: asil site {candidate}")
                domain = candidate.rstrip("/")
                break
    if not server:
        _log("-> Selçukspor: oynatici sunucusu bulunamadi")
        FAMILY_STATUS["selcuk"] = "oynatici-sunucusu-yok"
        return []
    FAMILY_STATUS["selcuk"] = f"{domain} | oynatici {server}"

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
# 4-5. ANDRO PANEL + NETSPOR (ayni checklist sunucu ailesi)
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

# Panel ailesinin bilinen sayfalari (ayni isletici; birbirine yonlenir)
ANDRO_PANEL_PAGES = [
    "https://taraftariumizle.org",
    "https://patronmutlusonistiyor.com",
    "https://mahsunsports.xyz",
]

_CHECKLIST_URL_RE = re.compile(
    r"https?://[a-z0-9.\-]+\.[a-z]{2,}/checklist(?:/[^\s\"'<>\\\\]*)?", re.I
)
_ANDRO_HOST_RE = re.compile(r"https?://(?:andro|net)[a-z0-9.\-]+\.[a-z]{2,}", re.I)


def _andro_servers(html: str) -> List[str]:
    """Sayfa icindeki baseUrls dizisini cikarir."""
    match = re.search(r"baseUrls\s*=\s*\[(.*?)\]", html or "", re.DOTALL)
    if not match:
        return []
    raw = match.group(1).replace('"', "").replace("'", "")
    servers = {
        part.strip().rstrip("/")
        for part in raw.split(",")
        if part.strip().startswith("http")
    }
    return sorted(servers)


def _checklist_candidates_from_text(text: str) -> List[str]:
    """Metindeki checklist sunucularini toplar (tam URL'lerden tabana indirir)."""
    bases = set()
    if not text:
        return []
    for url in _CHECKLIST_URL_RE.findall(text):
        base = url.split("/checklist", 1)[0].rstrip("/")
        bases.add(base)
    for url in _ANDRO_HOST_RE.findall(text):
        bases.add(url.rstrip("/"))
    return sorted(bases)


def _previous_list_servers() -> List[str]:
    """Onceki BASARILI listeden (channels.json) checklist sunuculari toplar.

    Sunucular sik degistigi icin son iyi listenin kendisi en guncel
    ipucu kaynagidir.
    """
    path = Settings.JSON_OUTPUT_FILE
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return []
    servers = set()
    for channel in data.get("channels", []) or []:
        for link in [channel.get("url", "")] + [
            (b.get("url", "") if isinstance(b, dict) else str(b))
            for b in channel.get("backups", []) or []
        ]:
            if "/checklist/" in (link or ""):
                servers.add(link.split("/checklist/", 1)[0])
    return sorted(servers)


def discover_checklist_servers(*htmls: str) -> List[str]:
    """Tum ipuclarindan checklist sunucu adaylarini toplar.

    Ipuclari: verilen sayfa HTML'leri + panel ailesi sayfalari + onceki liste.
    """
    candidates: List[str] = []
    seen = set()

    def add(url: str) -> None:
        url = url.rstrip("/")
        if url and url not in seen:
            seen.add(url)
            candidates.append(url)

    for html in htmls:
        for server in _andro_servers(html or ""):
            add(server)
        for base in _checklist_candidates_from_text(html or ""):
            add(base)

    for page_url in ANDRO_PANEL_PAGES:
        html = get_text(page_url)
        if not html:
            continue
        for server in _andro_servers(html):
            add(server)
        for base in _checklist_candidates_from_text(html):
            add(base)

    # Topluluk listeleri guncel checklist sunucularini tasiyabilir
    community = community_m3u_text()
    if community:
        for base in _checklist_candidates_from_text(community):
            add(base)

    # Repo icindeki sabit tohum listesi de sunucu ipucu tasir
    for base in _checklist_candidates_from_text(_seeds_text()):
        add(base)

    for server in _previous_list_servers():
        add(server)

    return candidates


def _probe_checklist(server: str, channel_id: str = "androstreamlivebs1"):
    """Checklist sunucusu gercekten yayin veriyor mu?

    Basarili olursa (sunucu, calisan user-agent) demeti dondurur.
    Checklist sunuculari cogunlukla Android/Dalvik UA bekler; once tarayici
    UA, olmazsa Dalvik denenir.
    """
    url = _andro_url(server, channel_id)
    for ua, referer in (
        (None, ANDRO_REFERER),
        (DALVIK_UA, None),
    ):
        extra = {"User-Agent": ua} if ua else None
        response = http_get(
            url,
            referrer=referer,
            timeout=(4, 7),
            stream=True,
            extra_headers=extra,
        )
        if response is None:
            continue
        try:
            if response.status_code == 200:
                head = read_chunk(response, 256)
                if b"#EXT" in head:
                    return server, (ua or None)
        finally:
            try:
                response.close()
            except Exception:
                pass
    return None


def _andro_url(server: str, channel_id: str) -> str:
    if "/checklist" in server:
        return f"{server}/{channel_id}.m3u8"
    return f"{server}/checklist/{channel_id}.m3u8"


def fetch_andro() -> List[StreamInfo]:
    """Andro Panel: panel sayfalari -> checklist sunuculari -> sabit kanallar."""
    htmls: List[str] = []
    for page_url in ANDRO_PANEL_PAGES:
        html = get_text(page_url)
        if html:
            htmls.append(html)

    servers = discover_checklist_servers(*htmls)
    if not servers:
        _log("-> Andro: sunucu listesi bulunamadi")
        FAMILY_STATUS["andro"] = "sunucu-yok"
        return []

    probes = [
        s for s in run_parallel(_probe_checklist, servers, Settings.SCRAPE_WORKERS)
        if s
    ]
    if not probes:
        _log(f"-> Andro: {len(servers)} sunucudan hicbiri yanit vermedi")
        FAMILY_STATUS["andro"] = f"{len(servers)} aday olmus"
        return []

    _log(f"-> Andro: {len(probes)}/{len(servers)} sunucu aktif: {[p[0] for p in probes][:3]}")
    FAMILY_STATUS["andro"] = f"{len(probes)}/{len(servers)} sunucu aktif"

    results: List[StreamInfo] = []
    for server, ua in probes:
        for channel_id, name in ANDRO_IDS:
            results.append(
                StreamInfo(
                    name=name,
                    url=_andro_url(server, channel_id),
                    group="ANDRO SPOR",
                    referrer=ANDRO_REFERER,
                    source="andro",
                    user_agent=ua or "",
                )
            )
    return results


# =============================================================================
# 5. NETSPOR
# =============================================================================

_NETSPOR_ID_RE = re.compile(r"\b(?:andro|net)[a-z0-9]*stream[a-z0-9]*\b", re.I)


def fetch_netspor() -> List[StreamInfo]:
    """Netspor: kanal ve canli mac listesi.

    Duzeltme: checklist sunucusu ARTIK koda gomulu degil; sayfalardan ve
    onceki basarili listeden kesfedilir, canlilik testinden gecer.
    """
    domain = find_domain("netspor")
    if not domain:
        return []

    html = get_text(domain)
    if not html:
        return []

    servers = discover_checklist_servers(html)
    if not servers:
        _log("-> Netspor: checklist sunucusu bulunamadi")
        FAMILY_STATUS["netspor"] = "sunucu-yok"
        return []

    probes = [
        s for s in run_parallel(_probe_checklist, servers, Settings.SCRAPE_WORKERS)
        if s
    ]
    if not probes:
        _log(f"-> Netspor: {len(servers)} sunucudan hicbiri canli degil")
        FAMILY_STATUS["netspor"] = f"{len(servers)} aday olmus"
        return []
    _log(f"-> Netspor: {len(probes)}/{len(servers)} sunucu aktif: {[p[0] for p in probes][:3]}")
    FAMILY_STATUS["netspor"] = f"{len(probes)}/{len(servers)} sunucu aktif"

    soup = BeautifulSoup(html, "html.parser")
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

        for server, ua in probes:
            results.append(
                StreamInfo(
                    name=title,
                    url=_andro_url(server, stream_id),
                    group="NETSPOR",
                    referrer=ANDRO_REFERER,
                    source="netspor",
                    user_agent=ua or "",
                )
            )

    # Sayfada option/data-id disinda gecen androstream id'lerini de topla
    for match in _NETSPOR_ID_RE.findall(html):
        stream_id = match.strip()
        if not stream_id.startswith(("andro", "net")) or stream_id in {
            k for pair in seen for k in pair
        }:
            continue
        seen.add((stream_id, stream_id))
        for server, ua in probes:
            results.append(
                StreamInfo(
                    name=stream_id,
                    url=_andro_url(server, stream_id),
                    group="NETSPOR",
                    referrer=ANDRO_REFERER,
                    source="netspor",
                    user_agent=ua or "",
                )
            )

    _log(f"-> Netspor: {len(results)} kayit")
    FAMILY_STATUS["netspor-kayit"] = str(len(results))
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


# AtomSpor'un kanal sayfalari yayini bu Cloudflare worker uzerinden cozer:
#   GET /?ID=<slug>  ->  302  ->  gercek m3u8
# Panel sayfasi Cloudflare'e takilsa bile worker cogunlukla ayaktadir; bu
# yuzden sayfa taramasi bos donerse worker adresleri dogrudan aday yapilir
# (dogrulama katmani gercekten HLS donmeyenleri eler).
ATOM_WORKER = os.environ.get("ATOM_WORKER", "https://tv.atomspor.workers.dev")
ATOM_LOGO = "https://i.hizliresim.com/gm50rk9b.jpg"


def _atom_worker_streams(referrer: str) -> List[StreamInfo]:
    return [
        StreamInfo(
            name=name,
            url=f"{ATOM_WORKER}/?ID={slug}",
            group="ATOM SPOR",
            logo=ATOM_LOGO,
            referrer=referrer,
            source="atom",
        )
        for slug, name in ATOM_IDS
    ]


def fetch_atom() -> List[StreamInfo]:
    """AtomSpor: kanal sayfalarindan m3u8 cikarir; olmazsa worker'a duser."""
    entries_dom = find_domain("atom")
    results: List[StreamInfo] = []
    if entries_dom:
        entries = [
            (f"{entries_dom}/kanal/{slug}", name) for slug, name in ATOM_IDS
        ]
        results = resolve_pages(
            entries,
            group="ATOM SPOR",
            source="atom",
            referrer=entries_dom,
            logo=ATOM_LOGO,
        )
        _log(f"-> AtomSpor: {len(results)}/{len(entries)} kanalda m3u8 bulundu")

    if len(results) < len(ATOM_IDS):
        found = {r.name for r in results}
        worker = [
            s for s in _atom_worker_streams(entries_dom or ATOM_WORKER)
            if s.name not in found
        ]
        results.extend(worker)
        _log(f"-> AtomSpor: {len(worker)} kanal worker cozucusu ile denenecek")
        FAMILY_STATUS["atom"] = (
            f"{FAMILY_STATUS.get('atom', entries_dom or 'domain-yok')} "
            f"| worker: {len(worker)}"
        )
    return results


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


def fetch_mahsun() -> List[StreamInfo]:
    results = _fetch_panel(
        "mahsun",
        "{domain}/event.html?id={id}",
        MAHSUN_CHANNELS,
        group="MAHSUN SPOR",
        source="mahsun",
    )
    return results


def fetch_pasizle() -> List[StreamInfo]:
    return _fetch_panel(
        "pasizle",
        "{domain}/ch.html?id={id}",
        PANEL_CHANNELS,
        group="PAŞİZLE",
        source="pasizle",
    )


def fetch_inadina() -> List[StreamInfo]:
    """
    Inadina TV.

    HATA DUZELTMESI: eski surumde tum kanallara ayni ana sayfa adresi
    veriliyordu (kanal id'si hic kullanilmiyordu), yani 31 kayit da aynidir.
    """
    return _fetch_panel(
        "inadina",
        "{domain}/ch.html?id={id}",
        PANEL_CHANNELS,
        group="İNADINA TV",
        source="inadina",
    )


def fetch_kulisbet() -> List[StreamInfo]:
    return _fetch_panel(
        "kulisbet",
        "{domain}/channel?id={id}",
        PANEL_CHANNELS,
        group="KULISBET",
        source="kulisbet",
    )



# =============================================================================
# 11. TOPLULUK LISTELERI (guncel sunucu ve UA bilgisi tasiyan curutulmus M3U'lar)
# =============================================================================

COMMUNITY_M3U_URLS = [
    url.strip()
    for url in os.environ.get(
        "COMMUNITY_M3U",
        "https://raw.githubusercontent.com/Kral-Turk/Kral-Turk-TV/main/TURK_TV.m3u_plus,"
        "https://raw.githubusercontent.com/Kral-Turk/Kral-Turk-TV/main/Kral-Sport.m3u_plus",
    ).split(",")
    if url.strip()
]

# Android/Dalvik istemcisi: checklist sunuculari cogunlukla bunu bekler
DALVIK_UA = (
    "Dalvik/2.1.0 (Linux; U; Android 13; Samsung F1833B Build/TP1A.280629.015)"
)

_EXTINF_ATTR = re.compile(r'([a-zA-Z0-9-]+)="([^"]*)"')


def _community_cache_path() -> str:
    import tempfile

    return os.path.join(tempfile.gettempdir(), "community_m3u.cache")


def community_m3u_text() -> str:
    """Topluluk M3U'larini indirir (surec boyunca tek sefer; dosya onbellekli)."""
    cache = _community_cache_path()
    if os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8", errors="ignore") as handle:
                return handle.read()
        except Exception:
            pass

    parts: List[str] = []
    for url in COMMUNITY_M3U_URLS:
        response = http_get(url, timeout=(6, 20))
        if response is None or response.status_code != 200:
            continue
        body = getattr(response, "text", "") or ""
        if "#EXTINF" in body:
            parts.append(body)
        try:
            response.close()
        except Exception:
            pass

    text = "\n".join(parts)
    if text:
        try:
            with open(cache, "w", encoding="utf-8") as handle:
                handle.write(text)
        except Exception:
            pass
    return text


def parse_m3u_entries(text: str) -> List[Dict[str, str]]:
    """M3U_PLUS metnini girdi sozluklerine ayristirir (UA/Referer dahil)."""
    entries: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("#extinf"):
            name = line.split(",", 1)[1].strip() if "," in line else ""
            current = {"name": name}
            for key, value in _EXTINF_ATTR.findall(line):
                current.setdefault(f"attr_{key.lower()}", value)
        elif low.startswith("#extvlcopt:http-user-agent=") and current is not None:
            current.setdefault("user_agent", line.split("=", 1)[1].strip())
        elif low.startswith("#extvlcopt:http-referrer=") and current is not None:
            current.setdefault("referrer", line.split("=", 1)[1].strip())
        elif low.startswith("#extvlcopt:http-origin=") and current is not None:
            current.setdefault("referrer", current.get("referrer") or line.split("=", 1)[1].strip())
        elif low.startswith("#extvlcopt") or low.startswith("#extgrp") or low.startswith("#ext-x"):
            continue
        elif low.startswith("#exthttp") and current is not None:
            blob = line.split(":", 1)[1]
            try:
                headers = json.loads(blob)
                current.setdefault("user_agent", headers.get("User-Agent", ""))
                current.setdefault("referrer", headers.get("Referer", ""))
            except Exception:
                pass
        elif line.startswith("#"):
            continue
        elif current is not None:
            if line.startswith(("http://", "https://")):
                current["url"] = line
                entries.append(current)
            current = None

    return entries


def fetch_community_m3u() -> List[StreamInfo]:
    """Topluluk listelerini okur; dogrulama katmani olulerini eler.

    Bu listeler sunucu rotasyonunu gunluk takip ettigi icin checklist
    sunucularinin en guncel kaynaklarindan biridir.
    """
    text = community_m3u_text()
    if not text:
        _log("-> Topluluk: liste alinamadi")
        FAMILY_STATUS["topluluk"] = "liste-yok"
        return []

    raw_entries = parse_m3u_entries(text)
    results: List[StreamInfo] = []
    for entry in raw_entries:
        url = entry.get("url", "")
        if not url:
            continue
        # tinyurl/redirect iceren girdileri cozerken asiri istek atma;
        # dogrudan adresler ve bilinen desenler kalsin
        results.append(
            StreamInfo(
                name=entry.get("name") or "Bilinmeyen",
                url=url,
                group=entry.get("attr_group-title") or "TOPLULUK",
                logo=entry.get("attr_tvg-logo", ""),
                referrer=entry.get("referrer", ""),
                source="topluluk",
                user_agent=entry.get("user_agent", ""),
            )
        )

    FAMILY_STATUS["topluluk"] = f"{len(results)} girdi"
    _log(f"-> Topluluk: {len(results)} girdi")
    return results


# =============================================================================
# 12. SABIT TOHUM LISTESI (repo icindeki seeds.m3u)
# =============================================================================
#
# Otomatik kesif her seyi bulamaz: bazi kaynaklar sayfa yerine dogrudan bir
# "cozucu" adres uzerinden yayin verir (orn. AtomSpor'un Cloudflare worker'i)
# ve panel sayfasi Cloudflare'e takildiginda bot bunlari kacirir. seeds.m3u
# bu tur bilinen adresleri tasir; her kosuda diger kaynaklarla AYNI dogrulama
# katmanindan gecer, yani olu girdiler listeye sizmaz.

SEEDS_FILE = os.environ.get("SEEDS_FILE", "seeds.m3u")


def _seeds_text() -> str:
    path = SEEDS_FILE
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8-sig", errors="ignore") as handle:
            return handle.read()
    except Exception:
        return ""


def fetch_seeds() -> List[StreamInfo]:
    """Repo icindeki sabit tohum listesini okur (dogrulama sonra yapilir)."""
    text = _seeds_text()
    if not text:
        FAMILY_STATUS["seeds"] = "dosya-yok"
        return []

    results: List[StreamInfo] = []
    for entry in parse_m3u_entries(text):
        url = entry.get("url", "")
        if not url:
            continue
        results.append(
            StreamInfo(
                name=entry.get("name") or "Bilinmeyen",
                url=url,
                group=entry.get("attr_group-title") or "SABIT",
                logo=entry.get("attr_tvg-logo", ""),
                referrer=entry.get("referrer", ""),
                source="seeds",
                user_agent=entry.get("user_agent", ""),
            )
        )
    FAMILY_STATUS["seeds"] = f"{len(results)} girdi"
    _log(f"-> Sabit tohum listesi: {len(results)} girdi")
    return results


# =============================================================================
# KAYIT
# =============================================================================

COLLECTORS: List[Tuple[str, Callable[[], List[StreamInfo]]]] = [
    ("Sabit tohum listesi", fetch_seeds),
    ("Topluluk listesi", fetch_community_m3u),
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
