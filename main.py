#!/usr/bin/env python3
"""
Canli Spor Kanallari - M3U Liste Olusturucu

Akis:
    1. Tum kaynaklar paralel taranir (biri cokerse digerleri etkilenmez).
    2. Kanal adlari normalize edilip mantiksal anahtara baglanir.
    3. Her yayin gercekten oynatilabilir mi diye dogrulanir (playlist+segment).
    4. Ayni kanalin kopyalari birlestirilir; en hizlisi birincil, digerleri yedek.
    5. M3U + JSON + saglik raporu yazilir.

Ortam degiskenleri:
    VALIDATE=0            dogrulamayi kapatir (hizli calisma)
    VALIDATE_SEGMENT=0    sadece playlist kontrolu yapar
    KEEP_UNVERIFIED=1     dogrulanamayan yayinlari da listeye yazar
    PLAYER_PROXY=<url>    tarayici oynatici icin header enjekte eden proxy
    ONLY=netspor,andro    sadece secili kaynaklari tarar
"""

from __future__ import annotations

import concurrent.futures
import datetime
import os
import sys
import time
from typing import Dict, List

import core
from core import Settings, StreamInfo
from sources import COLLECTORS


def collect_all() -> List[StreamInfo]:
    """Tum kaynaklari paralel tarar; her kaynak izole edilir."""
    only = {
        token.strip().lower()
        for token in os.environ.get("ONLY", "").split(",")
        if token.strip()
    }

    collectors = COLLECTORS
    if only:
        collectors = [
            (label, fn)
            for label, fn in COLLECTORS
            if any(token in label.lower() or token in fn.__name__ for token in only)
        ]
        print(f"[i] ONLY filtresi: {[c[0] for c in collectors]}")

    results: List[StreamInfo] = []

    def run(entry):
        label, fn = entry
        started = time.time()
        try:
            streams = fn() or []
        except Exception as exc:  # kaynak cokerse digerlerini etkilemesin
            print(f"[!] {label}: HATA {type(exc).__name__}: {exc}", flush=True)
            return label, [], time.time() - started
        return label, streams, time.time() - started

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(collectors) or 1) as pool:
        futures = [pool.submit(run, entry) for entry in collectors]
        for future in concurrent.futures.as_completed(futures):
            label, streams, elapsed = future.result()
            print(f"[+] {label}: {len(streams)} kayit ({elapsed:.1f}s)", flush=True)
            results.extend(streams)

    return results


def main() -> int:
    started = time.time()
    generated_at = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    print("=" * 60)
    print(" SPOR LISTESI OLUSTURUCU")
    print("=" * 60)

    print("\n[1/4] Kaynaklar taraniyor...")
    streams = collect_all()
    print(f"\n    Toplam ham kayit: {len(streams)}")

    if not streams:
        print("[!] Hicbir kaynaktan kayit alinamadi. Mevcut dosya korunuyor.")
        return 1

    print("\n[2/4] Kanal adlari normalize ediliyor...")
    core.assign_keys(streams)
    unique_keys = len({s.key for s in streams})
    print(f"    {len(streams)} kayit -> {unique_keys} mantiksal kanal")

    print("\n[3/4] Yayinlar dogrulaniyor...")
    if Settings.VALIDATE:
        streams = core.validate_all(streams)
        verified = sum(1 for s in streams if s.verified)
        print(f"    Dogrulanan: {verified}/{len(streams)}")
    else:
        for stream in streams:
            stream.verified = True
            stream.status = "skipped"
        print("    Dogrulama atlandi (VALIDATE=0)")

    playable = [s for s in streams if s.verified]
    if not playable and not Settings.KEEP_UNVERIFIED:
        print("[!] Hicbir yayin dogrulanamadi. Mevcut dosya korunuyor.")
        print("    Ipucu: aginiz kaynaklara erisemiyor olabilir (KEEP_UNVERIFIED=1).")
        _write_report(streams, [], generated_at)
        return 1

    candidates = streams if Settings.KEEP_UNVERIFIED else playable

    print("\n[4/4] Kopyalar birlestiriliyor ve dosyalar yaziliyor...")
    final = core.dedupe_and_rank(candidates)
    with_backup = sum(1 for s in final if s.backups)
    print(f"    {len(candidates)} yayin -> {len(final)} kanal "
          f"({with_backup} kanalda yedek link var)")

    _write(Settings.M3U_OUTPUT_FILE, core.build_m3u(final, generated_at))
    _write(Settings.JSON_OUTPUT_FILE, core.build_json(final, generated_at))
    _write_report(streams, final, generated_at)

    print("\n" + "=" * 60)
    print(f" TAMAM - {len(final)} kanal, {time.time() - started:.1f}s")
    print(f" Cikti: {Settings.M3U_OUTPUT_FILE}, {Settings.JSON_OUTPUT_FILE}")
    print("=" * 60)
    return 0


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8-sig") as handle:
        handle.write(content)
    print(f"    -> {path} ({len(content):,} bayt)")


def _write_report(
    all_streams: List[StreamInfo], final: List[StreamInfo], generated_at: str
) -> None:
    report = core.build_report(all_streams, final, generated_at)
    with open(Settings.REPORT_FILE, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(f"    -> {Settings.REPORT_FILE}")


if __name__ == "__main__":
    sys.exit(main())
