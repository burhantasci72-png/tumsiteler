#!/usr/bin/env python3
"""
Dogrulama katmani entegrasyon testleri.

Sahte bir HLS sunucusu ayaga kaldirip gercek HTTP uzerinden test eder;
disari ag erisimi GEREKTIRMEZ.
"""

import os
import socketserver
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import core
from core import StreamInfo
from mockserver import Handler


class TestValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        cls.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def check(self, path, referrer=""):
        stream = StreamInfo(
            name="t", url=f"{self.base}{path}", group="G", referrer=referrer
        )
        return core.validate_stream(stream)

    def test_healthy_stream(self):
        result = self.check("/good.m3u8")
        self.assertTrue(result.verified)
        self.assertEqual(result.status, "ok")

    def test_master_playlist_follows_variant(self):
        result = self.check("/master.m3u8")
        self.assertTrue(result.verified)

    def test_dead_url(self):
        result = self.check("/dead.m3u8")
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "http-404")

    def test_html_masquerading_as_m3u8(self):
        result = self.check("/notm3u8.m3u8")
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "not-hls")

    def test_playlist_without_segments(self):
        result = self.check("/empty.m3u8")
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "no-segments")

    def test_hotlink_protection_requires_referer(self):
        """Referer yoksa 403, dogru Referer ile 200."""
        self.assertFalse(self.check("/protected.m3u8").verified)
        self.assertTrue(
            self.check("/protected.m3u8", referrer="https://allowed.example/").verified
        )

    def test_playlist_ok_but_segment_forbidden(self):
        """En sinsi hata: manifest 200 doner ama segmentler 403."""
        result = self.check("/badseg.m3u8")
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "segment-http-403")

    def test_segment_referrer_fallback(self):
        """Segment Referer ile 403 veriyorsa Referer'siz denenmeli.

        Selcukspor gibi panellerde manifest geliyor ama segmentler yalnizca
        Referer GONDERILMEDIGINDE aciliyordu; calisan varyant kaydedilir.
        """
        stream = StreamInfo(
            name="t",
            url=f"{self.base}/noref.m3u8",
            group="G",
            referrer="https://panel.example/",
        )
        result = core.validate_stream(stream)
        self.assertTrue(result.verified, result.status)
        self.assertEqual(result.status, "ok")
        # Calisan varyant kaynak olarak kullanilir
        self.assertEqual(result.referrer, "")

    def test_page_url_is_not_a_stream(self):
        """Sayfa linkleri yayin sayilmaz (eski surumun ana hatasi)."""
        result = self.check("/page.html")
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "not-a-stream")

    def test_resolver_url_redirecting_to_hls_is_accepted(self):
        """.m3u8 icermeyen cozucu adres (worker) 302 ile playlist'e gidiyorsa
        kabul edilmeli; segmentler YONLENDIRME SONRASI adrese gore cozulmeli."""
        result = self.check("/resolve?ID=bein-sports-1")
        self.assertTrue(result.verified, result.status)
        self.assertEqual(result.status, "ok")

    def test_resolver_url_returning_html_is_rejected(self):
        result = self.check("/resolve-html?ID=x")
        self.assertFalse(result.verified)
        self.assertEqual(result.status, "not-a-stream")

    def test_extract_m3u8_from_page(self):
        found = core.extract_m3u8(f"{self.base}/page.html")
        self.assertEqual(found, f"{self.base}/good.m3u8")

    def test_end_to_end_failover(self):
        """Bozuk kaynaklar elenmeli, saglam olan birincil olmali."""
        streams = [
            StreamInfo(name="NET - Bein Sports 1CANLI|7/24.",
                       url=f"{self.base}/dead.m3u8", group="A", source="net"),
            StreamInfo(name="ATOM - Bein Sports 1",
                       url=f"{self.base}/badseg.m3u8", group="B", source="atom"),
            StreamInfo(name="B1 ydk",
                       url=f"{self.base}/good.m3u8", group="C", source="trf"),
            StreamInfo(name="SL - BEIN SPORTS 1",
                       url=f"{self.base}/master.m3u8", group="D", source="sl"),
        ]
        core.assign_keys(streams)
        streams = core.validate_all(streams)

        playable = [s for s in streams if s.verified]
        self.assertEqual(len(playable), 2)

        merged = core.dedupe_and_rank(playable)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].name, "beIN Sports 1")
        self.assertEqual(len(merged[0].backups), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
