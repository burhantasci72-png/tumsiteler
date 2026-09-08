#!/usr/bin/env python3
"""
Ortak altyapi: HTTP oturumu, m3u8 cikarma, dogrulama, kanal normalizasyonu.

Bu modul main.py tarafindan kullanilir. Amac: her kaynak toplayicinin ayni
saglam HTTP katmanini, ayni m3u8 kesif mantigini ve ayni dogrulama/tekillestirme
kurallarini paylasmasi.
"""

from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import urllib3
from requests.adapters import HTTPAdapter

try:  # urllib3 v1/v2 uyumu
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    Retry = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# =============================================================================
# YAPILANDIRMA
# =============================================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

# HTML sayfaları icin tarayıcı benzeri basliklar (Cloudflare bot skorunu dusurur)
PAGE_HEADERS = {
    **BASE_HEADERS,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Calisma zamani ayarlari (ortam degiskenleriyle gecersiz kilinabilir)."""

    CONNECT_TIMEOUT = 6
    READ_TIMEOUT = _env_int("SCRAPE_TIMEOUT", 12)

    # Kaynak tarama
    SCRAPE_WORKERS = _env_int("SCRAPE_WORKERS", 24)
    DOMAIN_PROBE_WORKERS = _env_int("DOMAIN_PROBE_WORKERS", 40)
    SOURCE_BUDGET = _env_int("SOURCE_BUDGET", 150)  # kaynak basina saniye

    # Dogrulama
    VALIDATE = _env_flag("VALIDATE", True)
    VALIDATE_WORKERS = _env_int("VALIDATE_WORKERS", 40)
    VALIDATE_TIMEOUT = _env_int("VALIDATE_TIMEOUT", 9)
    VALIDATE_SEGMENT = _env_flag("VALIDATE_SEGMENT", True)
    KEEP_UNVERIFIED = _env_flag("KEEP_UNVERIFIED", False)

    # Cikti
    M3U_OUTPUT_FILE = os.environ.get("M3U_OUTPUT", "Canli_Spor_Hepsi.m3u")
    JSON_OUTPUT_FILE = os.environ.get("JSON_OUTPUT", "channels.json")
    REPORT_FILE = os.environ.get("REPORT_OUTPUT", "health_report.json")

    # Tarayici oynatici icin header enjekte eden proxy.
    # Bos birakilirsa m3u dosyasina ham URL yazilir.
    PLAYER_PROXY = os.environ.get("PLAYER_PROXY", "").rstrip("/")


TIMEOUT: Tuple[int, int] = (Settings.CONNECT_TIMEOUT, Settings.READ_TIMEOUT)


# =============================================================================
# VERI MODELI
# =============================================================================

@dataclass
class BackupLink:
    """Bir kanalin alternatif kaynagi (kendi referrer'i ile birlikte)."""

    url: str
    referrer: str = ""
    source: str = ""
    user_agent: str = ""


@dataclass
class StreamInfo:
    """Tek bir yayin kaydi."""

    name: str
    url: str
    group: str
    logo: str = ""
    referrer: str = ""
    source: str = ""
    # Bazi yayinlar ozel User-Agent ister (orn. Dalvik/Android)
    user_agent: str = ""
    # Dogrulama sonuclari
    verified: bool = False
    status: str = "unchecked"
    latency_ms: int = 0
    # Ayni mantiksal kanalin farkli kaynaklardaki kopyalarini eslestirmek icin
    key: str = ""
    # Yedek kaynaklar (ayni kanal, baska site).
    # Her yedek kendi referrer'ini tasir: farkli siteler farkli Referer ister,
    # birincilin referrer'i kullanilirsa yedek 403 alir.
    backups: List["BackupLink"] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# HTTP KATMANI
# =============================================================================

_local = threading.local()


# --- Tarayıcı TLS parmak izi (IMPERSONATE=1 ve curl_cffi kuruluysa) ---
# python-requests'in TLS parmak izi (JA3) bot korumalarında anında yakalanir;
# curl_cffi gerçek Chrome parmak izini taklit ederek bircogundan gecer.
try:  # opsiyonel bagimlilik
    from curl_cffi import requests as _curl_requests

    _CURL_AVAILABLE = True
except Exception:  # pragma: no cover
    _curl_requests = None
    _CURL_AVAILABLE = False

IMPERSONATE_ENABLED = _env_flag("IMPERSONATE", True) and _CURL_AVAILABLE
IMPERSONATE_TARGET = os.environ.get("IMPERSONATE_TARGET", "chrome124")


class _CurlResponse:
    """curl_cffi yanitini requests benzeri arayuze saran ince kutu."""

    def __init__(self, resp):
        self._resp = resp
        self.status_code = resp.status_code
        self.url = str(resp.url)
        self.text = resp.text
        self.content = resp.content or b""
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self.raw = None  # raw akis yok; read_chunk() content kullanir

    def close(self):
        try:
            self._resp.close()
        except Exception:
            pass


def read_chunk(response, limit: int) -> bytes:
    """Yanitin ilk `limit` baytini dondurur (requests VE curl uyumlu)."""
    raw = getattr(response, "raw", None)
    if raw is not None and hasattr(raw, "read"):
        try:
            return raw.read(limit, decode_content=True) or b""
        except Exception:
            return b""
    return (getattr(response, "content", b"") or b"")[:limit]


def get_session():
    """Thread-basina yeniden kullanilan HTTP istemcisi dondurur.

    IMPERSONATE aciksa ve curl_cffi kuruluysa Chrome parmak izli istemci,
    degilse requests.Session doner. Yanit tipi degisken olabilir; cagri
    siteleri read_chunk()/status_code/text kullandigi surece fark etmez.
    """
    session = getattr(_local, "session", None)
    if session is not None:
        return session

    if IMPERSONATE_ENABLED:
        try:
            session = _curl_requests.Session(impersonate=IMPERSONATE_TARGET)
        except Exception:
            try:
                session = _curl_requests.Session(impersonate="chrome")
            except Exception:
                session = None
        if session is not None:
            _local.session = session
            return session

    session = requests.Session()
    session.headers.update(BASE_HEADERS)

    if Retry is not None:
        retry = Retry(
            total=2,
            connect=2,
            read=1,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=64, pool_maxsize=64)
    else:  # pragma: no cover
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64)

    session.mount("http://", adapter)
    session.mount("https://", adapter)
    _local.session = session
    return session


def http_get(
    url: str,
    referrer: Optional[str] = None,
    timeout: Optional[Tuple[int, int] | int] = None,
    stream: bool = False,
    extra_headers: Optional[Dict[str, str]] = None,
    page: bool = False,
) -> Optional[requests.Response]:
    """Guvenli GET. Hata durumunda None doner, asla istisna firlatmaz.

    page=True ise tarayici benzeri basliklar kullanilir (panel sayfalari icin).
    curl_cffi impersonation aktifse yanit _CurlResponse olarak doner.
    """
    base = PAGE_HEADERS if page else BASE_HEADERS
    headers = dict(base)
    if referrer:
        headers["Referer"] = referrer
        parsed = urllib.parse.urlparse(referrer)
        if parsed.scheme and parsed.netloc:
            headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
            headers.setdefault("Sec-Fetch-Site", "same-origin")
    if extra_headers:
        headers.update(extra_headers)

    timeout = timeout or TIMEOUT
    session = get_session()

    # curl_cffi yolu (Chrome TLS parmak izi)
    if IMPERSONATE_ENABLED and not isinstance(session, requests.Session):
        try:
            resp = session.get(
                url,
                headers=headers,
                timeout=float(max(timeout) if isinstance(timeout, tuple) else timeout),
                allow_redirects=True,
                verify=False,
            )
            return _CurlResponse(resp)
        except Exception:
            return None

    try:
        return session.get(
            url,
            headers=headers,
            timeout=timeout,
            verify=False,
            stream=stream,
            allow_redirects=True,
        )
    except Exception:
        return None


def get_text(url: str, referrer: Optional[str] = None) -> Optional[str]:
    """Sayfa metnini doner (200 disi ve hata -> None)."""
    response = http_get(url, referrer=referrer, page=True)
    if response is None or response.status_code != 200:
        return None
    if not getattr(response, "encoding", None) or str(
        getattr(response, "encoding", "")
    ).lower() == "iso-8859-1":
        try:
            response.encoding = response.apparent_encoding or "utf-8"
        except Exception:
            pass
    return response.text


def run_parallel(fn: Callable, items: Sequence, workers: int) -> List:
    """Basit paralel map; istisnalari yutar."""
    results: List = []
    if not items:
        return results

    def guarded(item):
        try:
            return fn(item)
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for value in pool.map(guarded, items):
            if value is not None:
                results.append(value)
    return results


def first_match(
    fn: Callable,
    items: Sequence,
    workers: int,
    budget_seconds: Optional[int] = None,
):
    """Ilk truthy sonucu doner, kalan isleri iptal eder (domain taramasi icin)."""
    if not items:
        return None

    deadline = time.time() + budget_seconds if budget_seconds else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(fn, item): item for item in items}
        try:
            for future in concurrent.futures.as_completed(
                futures, timeout=budget_seconds
            ):
                try:
                    value = future.result()
                except Exception:
                    value = None
                if value:
                    for pending in futures:
                        pending.cancel()
                    return value
                if deadline and time.time() > deadline:
                    break
        except concurrent.futures.TimeoutError:
            pass
        finally:
            for pending in futures:
                pending.cancel()
    return None


# =============================================================================
# M3U8 KESIF
# =============================================================================

_M3U8_ABS = re.compile(r'(https?://[^\s\'"<>\\]+?\.m3u8[^\s\'"<>\\]*)', re.I)
_M3U8_REL = re.compile(r'[\'"](/[^\s\'"<>]+?\.m3u8[^\s\'"<>]*)[\'"]', re.I)
_M3U8_ENCODED = re.compile(
    r'(https?%3A%2F%2F[^\s\'"<>&]+?(?:%2E|\.)m3u8(?:%3F[^\s\'"<>&]*)?)', re.I
)
_ATOB = re.compile(r'atob\(\s*[\'"]([A-Za-z0-9+/=]{8,})[\'"]\s*\)')
_B64_BLOB = re.compile(r'[\'"]([A-Za-z0-9+/=]{40,})[\'"]')
_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
_SCRIPT_SRC = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
_SOURCE_VAR = re.compile(
    r'(?:source|file|src|hlsUrl|streamUrl|playbackUrl)\s*[:=]\s*[\'"]([^\'"]+)[\'"]', re.I
)


def _b64_try(blob: str) -> Optional[str]:
    """Base64 blob'unu cozup icinde m3u8 arar."""
    try:
        padded = blob + "=" * (-len(blob) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", "ignore")
    except Exception:
        return None
    match = _M3U8_ABS.search(decoded)
    return match.group(1) if match else None


def find_m3u8_in_text(text: str, base_url: str) -> Optional[str]:
    """Bir HTML/JS metni icinden m3u8 adresini cikarmaya calisir."""
    if not text:
        return None

    match = _M3U8_ABS.search(text)
    if match:
        return match.group(1)

    match = _M3U8_REL.search(text)
    if match:
        parsed = urllib.parse.urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{match.group(1)}"

    match = _M3U8_ENCODED.search(text)
    if match:
        candidate = urllib.parse.unquote(match.group(1))
        if ".m3u8" in candidate:
            return candidate

    for blob in _ATOB.findall(text):
        found = _b64_try(blob)
        if found:
            return found

    # jwplayer/clappr benzeri degisken atamalari
    for candidate in _SOURCE_VAR.findall(text):
        if ".m3u8" in candidate.lower():
            return urllib.parse.urljoin(base_url, candidate)

    for blob in _B64_BLOB.findall(text)[:40]:
        found = _b64_try(blob)
        if found:
            return found

    return None


def extract_m3u8(
    url: str,
    referrer: Optional[str] = None,
    depth: int = 2,
    _seen: Optional[set] = None,
) -> Optional[str]:
    """
    Sayfayi (ve gerekirse ic ice iframe'leri) gezerek m3u8 adresi bulur.

    depth: takip edilecek iframe derinligi.
    """
    seen = _seen if _seen is not None else set()
    if url in seen or len(seen) > 12:
        return None
    seen.add(url)

    text = get_text(url, referrer=referrer)
    if not text:
        return None

    found = find_m3u8_in_text(text, url)
    if found:
        return found

    if depth <= 0:
        return None

    # Harici <script src> dosyalarini da tara (yeni nesil paneller yayin
    # adresini dis JS dosyasindan yukler; ana HTML'de bulunmaz).
    for raw_src in _SCRIPT_SRC.findall(text)[:4]:
        script_url = urllib.parse.urljoin(url, raw_src)
        if script_url in seen or not script_url.startswith("http"):
            continue
        seen.add(script_url)
        script_text = get_text(script_url, referrer=referrer)
        if not script_text:
            continue
        found = find_m3u8_in_text(script_text, script_url)
        if found:
            return found

    for raw_src in _IFRAME.findall(text)[:5]:
        iframe_url = urllib.parse.urljoin(url, raw_src)
        if not iframe_url.startswith("http"):
            continue
        found = extract_m3u8(iframe_url, referrer=url, depth=depth - 1, _seen=seen)
        if found:
            return found

    return None


# =============================================================================
# DOGRULAMA
# =============================================================================

_PLAYLIST_MARKERS = (b"#EXTM3U", b"#EXT-X-", b"#EXTINF")


def _looks_like_playlist(chunk: bytes) -> bool:
    return any(marker in chunk for marker in _PLAYLIST_MARKERS)


def validate_stream(stream: StreamInfo) -> StreamInfo:
    """
    Yayinin gercekten oynatilabilir olup olmadigini kontrol eder.

    1. Playlist indirilir ve HLS imzasi aranir.
    2. Master playlist ise ilk varyant takip edilir.
    3. Medya playlist'inde en az bir segment olmali; istege bagli olarak
       ilk segmentin baytlari cekilerek 403/hotlink korumasi test edilir.
    """
    url = stream.url
    if not url.lower().startswith(("http://", "https://")):
        stream.status = "bad-scheme"
        return stream

    if ".m3u8" not in url.lower():
        # Sayfa linki: yayin degil, oynatici bunu iframe ile acamaz.
        stream.status = "not-a-stream"
        return stream

    started = time.time()
    extra = {"User-Agent": stream.user_agent} if stream.user_agent else None
    response = http_get(
        url,
        referrer=stream.referrer or None,
        timeout=(Settings.CONNECT_TIMEOUT, Settings.VALIDATE_TIMEOUT),
        stream=True,
        extra_headers=extra,
    )
    if response is None:
        stream.status = "network-error"
        return stream

    try:
        if response.status_code != 200:
            stream.status = f"http-{response.status_code}"
            return stream

        try:
            body = read_chunk(response, 65536)
        except Exception:
            stream.status = "read-error"
            return stream

        if not _looks_like_playlist(body):
            stream.status = "not-hls"
            return stream

        stream.latency_ms = int((time.time() - started) * 1000)
        text = body.decode("utf-8", "ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    finally:
        response.close()

    # Master playlist -> ilk varyanti dogrula
    if "#EXT-X-STREAM-INF" in text:
        variant = next(
            (ln for ln in lines if ln and not ln.startswith("#")), None
        )
        if not variant:
            stream.status = "empty-master"
            return stream
        child = StreamInfo(
            name=stream.name,
            url=urllib.parse.urljoin(url, variant),
            group=stream.group,
            referrer=stream.referrer,
            user_agent=stream.user_agent,
        )
        child = validate_stream(child)
        stream.verified = child.verified
        stream.status = child.status if not child.verified else "ok-master"
        return stream

    segments = [ln for ln in lines if ln and not ln.startswith("#")]
    if not segments:
        stream.status = "no-segments"
        return stream

    if not Settings.VALIDATE_SEGMENT:
        stream.verified = True
        stream.status = "ok-playlist"
        return stream

    segment_url = urllib.parse.urljoin(url, segments[0])
    seg_response = http_get(
        segment_url,
        referrer=stream.referrer or None,
        timeout=(Settings.CONNECT_TIMEOUT, Settings.VALIDATE_TIMEOUT),
        stream=True,
        extra_headers=extra,
    )
    if seg_response is None:
        stream.status = "segment-error"
        return stream

    try:
        if seg_response.status_code != 200:
            stream.status = f"segment-http-{seg_response.status_code}"
            return stream
        try:
            chunk = read_chunk(seg_response, 2048)
        except Exception:
            chunk = b""
        if len(chunk) < 256:
            stream.status = "segment-empty"
            return stream
    finally:
        seg_response.close()

    stream.verified = True
    stream.status = "ok"
    return stream


def validate_all(streams: List[StreamInfo]) -> List[StreamInfo]:
    """Tum yayinlari paralel dogrular."""
    if not Settings.VALIDATE:
        for stream in streams:
            stream.status = "skipped"
            stream.verified = True
        return streams
    return run_parallel(validate_stream, streams, Settings.VALIDATE_WORKERS) or streams


# =============================================================================
# KANAL NORMALIZASYONU / TEKILLESTIRME
# =============================================================================

_NOISE = re.compile(
    r"\b(hd|fhd|uhd|4k|sd|tr|turkey|turkiye|canli|izle|yayin|full|pro|vip|"
    r"yedek|kanali|kanal)\b",
    re.I,
)
_SOURCE_PREFIX = re.compile(
    r"^\s*(xsp|trf|sl|andro|net|atom|mahsun|inadina|i̇nadina|pasizle|pa[sş]izle|"
    r"kulis|kulisbet)\s*[-:]\s*",
    re.I,
)

_TR_MAP = str.maketrans("çğıİöşüÇĞÖŞÜ", "cgiiosucgosu")

# Kanonik kanal adlari: (regex, gorunen ad, sira)
_CANON: List[Tuple[re.Pattern, str, int]] = []


def _add_canon(pattern: str, display: str) -> None:
    _CANON.append((re.compile(pattern, re.I), display, len(_CANON)))


for _i in range(1, 6):
    _add_canon(rf"\bbein\s*(?:sports?)?\s*max\s*{_i}\b", f"beIN Sports Max {_i}")
for _i in range(1, 6):
    _add_canon(rf"\bbein\s*(?:sports?)?\s*{_i}\b", f"beIN Sports {_i}")
_add_canon(r"\bbein\s*(?:sports?)?\s*haber\b", "beIN Sports Haber")
_add_canon(r"\bs\s*spor[t]?\s*(?:plus|\+)\b", "S Sport Plus")
for _i in range(1, 4):
    _add_canon(rf"\bs\s*spor[t]?\s*{_i}\b", f"S Sport {_i}")
_add_canon(r"\bs\s*spor[t]?\b", "S Sport 1")
for _i in range(1, 5):
    _add_canon(rf"\btivibu\s*spor\s*{_i}\b", f"Tivibu Spor {_i}")
_add_canon(r"\btivibu\b", "Tivibu Spor 1")
for _i in range(1, 3):
    _add_canon(rf"\bsmart\s*spor[t]?\s*{_i}\b", f"Smart Spor {_i}")
_add_canon(r"\b(?:smart|akilli)\s*spor[t]?\b", "Smart Spor 1")
for _i in range(1, 3):
    _add_canon(rf"\beuro\s*sport\s*{_i}\b", f"Eurosport {_i}")
_add_canon(r"\beuro\s*sport\b", "Eurosport 1")
for _i in range(1, 8):
    _add_canon(rf"\btabii\s*(?:spor)?\s*{_i}\b", f"Tabii Spor {_i}")
_add_canon(r"\btabii\b", "Tabii Spor")
_add_canon(r"\btrt\s*spor\s*(?:yildiz|2)\b", "TRT Spor Yıldız")
_add_canon(r"\btrt\s*spor\b", "TRT Spor")
_add_canon(r"\btrt\s*1\b", "TRT 1")
_add_canon(r"\ba\s*spor\b", "A Spor")
_add_canon(r"\batv\b", "ATV")
_add_canon(r"\btv\s*8[.,]?5\b", "TV 8.5")
_add_canon(r"\btv\s*8\b", "TV 8")
_add_canon(r"\bexxen\s*(\d)\b", "Exxen")
_add_canon(r"\bexxen\b", "Exxen")
_add_canon(r"\bsky\s*sports?\s*f1\b", "Sky Sports F1")
_add_canon(r"\bidman\s*tv\b", "İdman TV")
_add_canon(r"\bcbc\s*sport\b", "CBC Sport")
_add_canon(r"\bnba\s*tv\b", "NBA TV")
_add_canon(r"\btjk\s*tv\b", "TJK TV")
_add_canon(r"\bred\s*bull\s*tv\b", "Red Bull TV")
_add_canon(r"\bht\s*spor\b", "HT Spor")
_add_canon(r"\bfb\s*tv\b", "FB TV")
_add_canon(r"\bgs\s*tv\b", "GS TV")
_add_canon(r"\bsports?\s*tv\b", "Sports TV")
_add_canon(r"\ba2\b", "A2")


def strip_source_prefix(raw: str) -> str:
    """Sadece kaynak onekini ('NET - ', 'ATOM - ') ve 'TR:' etiketini atar."""
    name = _SOURCE_PREFIX.sub("", raw or "")
    name = name.replace("TR:", " ")
    return re.sub(r"\s+", " ", name).strip()


# "Bein Sports 1CANLI|7/24." gibi site eklentileri
_TAIL_NOISE = re.compile(r"\s*(?:CANLI|LIVE|HD)?\s*\|\s*7\s*/\s*24\.?\s*$", re.I)
_ALIASES = (
    (re.compile(r"\bspor\s*smart\b", re.I), "smart spor"),
    (re.compile(r"\bidman\s*tv\b", re.I), "idman tv"),
    (re.compile(r"^b(\d)\s*ydk$", re.I), r"bein sports \1"),
    (re.compile(r"\btabi\s+spor\b", re.I), "tabii spor"),
    (re.compile(r"\bbir\s*spor\b", re.I), "A Spor"),
)


def clean_title(raw: str) -> str:
    """Kaynak onekini ve site kuyruk gurultusunu atar."""
    name = _TAIL_NOISE.sub("", strip_source_prefix(raw))
    name = re.sub(r"\s*CANLI\s*$", "", name, flags=re.I)
    for pattern, replacement in _ALIASES:
        name = pattern.sub(replacement, name)
    return re.sub(r"\s+", " ", name).strip(" -:|")


def normalize_name(raw: str) -> str:
    """Kaynak onekini ve gurultuyu temizleyip sadelestirilmis ad dondurur."""
    name = clean_title(raw).translate(_TR_MAP)
    name = re.sub(r"[_\-]+", " ", name)
    name = _NOISE.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip(" -:|")
    return name


# "Takim A - Takim B19:45|Turnuva" gibi maç basliklarini ayristirir
_EVENT_TAIL = re.compile(r"(\d{1,2}[:.]\d{2})\s*(?:\|\s*(.*))?$")


def parse_event(raw: str) -> Optional[Dict[str, str]]:
    """
    Maç/etkinlik basligini parcalar.

    Returns: {"home","away","time","competition","title"} veya None.
    """
    text = clean_title(raw)
    if not text:
        return None

    time_str = ""
    competition = ""
    tail = _EVENT_TAIL.search(text)
    if tail:
        time_str = tail.group(1).replace(".", ":")
        competition = (tail.group(2) or "").strip()
        text = text[: tail.start()].strip()

    # Takimlari ayir: " - ", " vs ", " v "
    parts = re.split(r"\s+(?:-|–|vs\.?|v)\s+", text, maxsplit=1)
    if len(parts) != 2:
        return None

    home, away = parts[0].strip(" -:|"), parts[1].strip(" -:|")
    if not home or not away or len(home) < 2 or len(away) < 2:
        return None

    # "beIN Sports 1" gibi kanal adlari maç degildir
    if canonical_channel(raw):
        return None

    title = f"{home} - {away}"
    if time_str:
        title = f"{time_str} {title}"

    return {
        "home": home,
        "away": away,
        "time": time_str,
        "competition": competition,
        "title": title,
    }


def canonical_channel(raw: str) -> Optional[Tuple[str, str, int]]:
    """
    Kanal adini bilinen bir TV kanalina eslestirir.

    Returns: (anahtar, gorunen_ad, sira) veya None (maç/etkinlik yayini ise).
    """
    name = normalize_name(raw)
    if not name:
        return None
    for pattern, display, order in _CANON:
        if pattern.search(name):
            key = re.sub(r"[^a-z0-9]", "", display.lower())
            return key, display, order
    return None


def is_event_stream(raw: str) -> bool:
    """Ad bir maç/etkinlik yayinina mi ait (Takim A - Takim B)?"""
    return parse_event(raw) is not None


def event_key(event: Dict[str, str]) -> str:
    """Maç yayinlari icin tekillestirme anahtari (takim sirasindan bagimsiz)."""
    def slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.translate(_TR_MAP).lower())

    teams = sorted([slug(event["home"]), slug(event["away"])])
    return "evt:" + "|".join(t for t in teams if t)


def assign_keys(streams: List[StreamInfo]) -> List[StreamInfo]:
    """Her yayina mantiksal kanal anahtari ve duzgun ad atar."""
    for stream in streams:
        canon = canonical_channel(stream.name)
        if canon:
            key, display, _order = canon
            stream.key = key
            stream.name = display
            continue

        event = parse_event(stream.name)
        if event:
            stream.key = event_key(event)
            stream.name = event["title"]
            if event["competition"]:
                stream.group = event["competition"]
            continue

        cleaned = clean_title(stream.name) or stream.name
        stream.key = "raw:" + re.sub(
            r"[^a-z0-9]", "", cleaned.translate(_TR_MAP).lower()
        )
        stream.name = cleaned
    return streams


def dedupe_and_rank(streams: List[StreamInfo]) -> List[StreamInfo]:
    """
    Ayni mantiksal kanalin kopyalarini birlestirir.

    En dusuk gecikmeli dogrulanmis yayin birincil olur; digerleri `backups`
    listesine yedek olarak eklenir. Boylece oynatici otomatik gecis yapabilir.
    """
    buckets: Dict[str, List[StreamInfo]] = {}
    for stream in streams:
        buckets.setdefault(stream.key or stream.url, []).append(stream)

    merged: List[StreamInfo] = []
    for group in buckets.values():
        # Ayni URL'yi iki kez tutma
        seen_urls = set()
        unique: List[StreamInfo] = []
        for stream in group:
            if stream.url in seen_urls:
                continue
            seen_urls.add(stream.url)
            unique.append(stream)

        unique.sort(key=lambda s: (not s.verified, s.latency_ms or 99999))
        primary = unique[0]
        primary.backups = [
            BackupLink(
                url=s.url, referrer=s.referrer, source=s.source,
                user_agent=s.user_agent,
            )
            for s in unique[1:8]
        ]
        merged.append(primary)

    def sort_key(stream: StreamInfo) -> Tuple:
        canon = canonical_channel(stream.name)
        if canon:
            return (0, canon[2], stream.name.lower())
        if stream.key.startswith("evt:"):
            return (1, 0, stream.name.lower())
        return (2, 0, stream.name.lower())

    merged.sort(key=sort_key)
    return merged


# =============================================================================
# CIKTI URETIMI
# =============================================================================

def proxied(url: str, referrer: str = "", _ua: str = "") -> str:
    """
    Tarayici oynaticisinin kullanacagi adres.

    PLAYER_PROXY tanimliysa, header enjekte eden proxy uzerinden gecirilir;
    aksi halde ham URL dondurulur.
    """
    if not Settings.PLAYER_PROXY or not url.lower().startswith(("http://", "https://")):
        return url
    query = urllib.parse.urlencode(
        {"url": url, "ref": referrer or "", "ua": _ua or USER_AGENT}
    )
    return f"{Settings.PLAYER_PROXY}/hls?{query}"


def build_m3u(streams: List[StreamInfo], generated_at: str) -> str:
    """M3U icerigi uretir (VLC/Kodi/TiviMate uyumlu header etiketleriyle)."""
    out: List[str] = ["#EXTM3U", f"# Son Guncelleme: {generated_at}"]
    verified = sum(1 for s in streams if s.verified)
    out.append(f"# Kanal: {len(streams)} | Dogrulanan: {verified}")

    for stream in streams:
        attrs = [
            f'tvg-id="{stream.key}"',
            f'tvg-name="{stream.name}"',
            f'group-title="{stream.group}"',
        ]
        if stream.logo:
            attrs.append(f'tvg-logo="{stream.logo}"')
        out.append(f'#EXTINF:-1 {" ".join(attrs)},{stream.name}')

        ua = stream.user_agent or USER_AGENT
        if stream.referrer:
            out.append(f"#EXTVLCOPT:http-referrer={stream.referrer}")
            out.append(f"#EXTVLCOPT:http-origin={stream.referrer}")
        out.append(f"#EXTVLCOPT:http-user-agent={ua}")

        # Kodi/TiviMate tarzi inline header'lar da eklensin
        exthttp = {"User-Agent": ua}
        if stream.referrer:
            exthttp["Referer"] = stream.referrer
        out.append(f"#EXTHTTP:{json.dumps(exthttp)}")

        out.append(proxied(stream.url, stream.referrer, ua))

    return "\n".join(out) + "\n"


def _backup_dict(backup, fallback_referrer: str = "") -> Dict[str, str]:
    """Yedek kaydi sozluge cevirir (duz string de kabul edilir)."""
    if isinstance(backup, str):
        return {"url": backup, "referrer": fallback_referrer, "source": "", "user_agent": ""}
    return {
        "url": backup.url,
        "referrer": backup.referrer or fallback_referrer,
        "source": backup.source,
        "user_agent": getattr(backup, "user_agent", ""),
    }


def build_json(streams: List[StreamInfo], generated_at: str) -> str:
    """Web oynatici icin zengin JSON (yedek linkler + header bilgisi dahil)."""
    payload = {
        "generated_at": generated_at,
        "user_agent": USER_AGENT,
        # Oynatici proxy'yi CALISMA ZAMANINDA uygular. Boylece proxy adresi
        # degistiginde listeyi yeniden uretmek gerekmez; ham adresler korunur.
        "proxy": Settings.PLAYER_PROXY,
        "count": len(streams),
        "verified": sum(1 for s in streams if s.verified),
        "channels": [
            {
                "key": s.key,
                "name": s.name,
                "group": s.group,
                "logo": s.logo,
                "referrer": s.referrer,
                "source": s.source,
                "verified": s.verified,
                "status": s.status,
                "latency_ms": s.latency_ms,
                "url": s.url,
                "user_agent": s.user_agent,
                "backups": [_backup_dict(b, s.referrer) for b in s.backups],
            }
            for s in streams
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


def build_report(
    all_streams: List[StreamInfo],
    final_streams: List[StreamInfo],
    generated_at: str,
    families: Optional[Dict[str, str]] = None,
) -> str:
    """Kaynak bazli saglik raporu."""
    by_source: Dict[str, Dict[str, int]] = {}
    reasons: Dict[str, int] = {}

    for stream in all_streams:
        entry = by_source.setdefault(stream.source or "?", {"total": 0, "ok": 0})
        entry["total"] += 1
        if stream.verified:
            entry["ok"] += 1
        else:
            reasons[stream.status] = reasons.get(stream.status, 0) + 1

    return json.dumps(
        {
            "generated_at": generated_at,
            "scraped": len(all_streams),
            "verified": sum(1 for s in all_streams if s.verified),
            "published": len(final_streams),
            "families": families or {},
            "by_source": dict(sorted(by_source.items())),
            "failure_reasons": dict(
                sorted(reasons.items(), key=lambda kv: -kv[1])
            ),
        },
        ensure_ascii=False,
        indent=1,
    )
