#!/usr/bin/env python3
"""
Domain kesfi / checklist sunucu kesfi testleri.

Sahte panel sayfalari uzerinde gercek HTTP ile calisir; disari ag
erisimi GEREKTIRMEZ.
"""

import os
import socketserver
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import core
import sources
from mockserver import Handler


class DiscoveryTestBase(unittest.TestCase):
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

    def setUp(self):
        # Gercek onceki-liste dosyasi testleri etkilemesin
        core.Settings.JSON_OUTPUT_FILE = os.path.join(tempfile.mkdtemp(), "yok.json")


class TestHelpers(DiscoveryTestBase):
    def test_andro_servers_extracts_baseurls(self):
        html = 'var baseUrls = ["http://a.example/x/", \'http://b.example/y\'];'
        self.assertEqual(
            sources._andro_servers(html),
            ["http://a.example/x", "http://b.example/y"],
        )

    def test_andro_servers_empty(self):
        self.assertEqual(sources._andro_servers("nothing here"), [])

    def test_checklist_candidates_from_text(self):
        text = (
            "https://srv1.example/checklist/androstreamlivebs1.m3u8 ve "
            "https://androsrv2.example/ artik yayinda"
        )
        found = sources._checklist_candidates_from_text(text)
        self.assertIn("https://srv1.example", found)
        self.assertIn("https://androsrv2.example", found)

    def test_andro_url_shapes(self):
        self.assertEqual(
            sources._andro_url("https://s.example/checklist", "id1"),
            "https://s.example/checklist/id1.m3u8",
        )
        self.assertEqual(
            sources._andro_url("https://s.example", "id1"),
            "https://s.example/checklist/id1.m3u8",
        )

    def test_guncel_address_candidates(self):
        html = (
            "GÜNCEL ADRESİMİZ: <a href='https://yeni.example/'>MAHSUNSPORTS.XYZ</a>"
        )
        self.assertEqual(
            sources._guncel_address_candidates(html, "https://eski.example/"),
            ["https://yeni.example"],
        )

    def test_harvest_family_urls(self):
        html = "yayinlarimiz https://sporcafe77.xyz ve https://www.sporcafe99.xyz/ da"
        found = sources._harvest_family_urls("selcuk", html)
        self.assertTrue(any("sporcafe77" in u for u in found))
        self.assertTrue(any("sporcafe99" in u for u in found))


class TestFindDomain(DiscoveryTestBase):
    def test_follows_redirect_and_signature(self):
        cfg = {
            "label": "Test",
            "seeds": [f"{self.base}/redirect-panel"],
            "patterns": [],
            "signature": ("bein",),
        }
        domain = sources.find_domain(cfg)
        # 302 -> /newpanel/ takip edilmeli ve SON adres donmeli
        self.assertEqual(domain, f"{self.base}/newpanel")

    def test_follows_guncel_address_announcement(self):
        cfg = {
            "label": "Test",
            "seeds": [f"{self.base}/oldpanel/"],
            "patterns": [],
            "signature": ("gunksiz-imza",) if False else (),
        }
        # imza bos: her icerik kabul; oldpanel'de guncel adres duyurusu var
        domain = sources.find_domain(cfg)
        self.assertEqual(domain, f"{self.base}/newpanel")

    def test_dead_family_returns_none(self):
        cfg = {
            "label": "Test",
            "seeds": ["http://127.0.0.1:1/"],
            "patterns": [("http://127.0.0.1:1/{}.html", range(1, 3))],
            "signature": (),
        }
        self.assertIsNone(sources.find_domain(cfg))


class TestM3uParsing(DiscoveryTestBase):
    SAMPLE = """#EXTM3U
#EXTINF:-1 tvg-logo="http://l.png" group-title="SPOR",BeIN Sports UHD 1
#EXTVLCOPT:http-user-agent=Dalvik/2.1.0 (Linux; U; Android 13)
https://andro.226503.xyz/checklist/androstreamlivebs1.m3u8
#EXTINF:-1 group-title="SPOR",TRT Spor
#EXTHTTP:{"User-Agent": "X/1", "Referer": "https://ref.example/"}
https://cdn.example/live/trt.m3u8
"""

    def test_parses_name_url_ua_referer(self):
        entries = sources.parse_m3u_entries(self.SAMPLE)
        self.assertEqual(len(entries), 2)

        first, second = entries
        self.assertEqual(first["name"], "BeIN Sports UHD 1")
        self.assertEqual(first["user_agent"], "Dalvik/2.1.0 (Linux; U; Android 13)")
        self.assertEqual(first["attr_group-title"], "SPOR")
        self.assertEqual(second["referrer"], "https://ref.example/")
        self.assertEqual(second["user_agent"], "X/1")

    def test_parse_empty(self):
        self.assertEqual(sources.parse_m3u_entries(""), [])


class TestExternalScriptExtraction(DiscoveryTestBase):
    def test_extract_follows_script_src(self):
        found = core.extract_m3u8(f"{self.base}/jspage.html")
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("/good.m3u8"))


class TestChecklistDiscovery(DiscoveryTestBase):
    def test_discovers_servers_from_panel_html(self):
        html = sources.get_text(f"{self.base}/newpanel/")
        servers = sources.discover_checklist_servers(html)
        self.assertIn(f"http://127.0.0.1:{self.port}/checklisthost", servers)

    def test_probe_checklist_accepts_valid_hls(self):
        found = sources._probe_checklist(f"http://127.0.0.1:{self.port}")
        self.assertEqual(found[0], f"http://127.0.0.1:{self.port}")

    def test_probe_checklist_rejects_dead(self):
        self.assertIsNone(sources._probe_checklist("http://127.0.0.1:1"))

    def test_previous_list_servers(self):
        import json

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "channels.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "channels": [
                        {
                            "url": "https://live.example/checklist/androstreamlivebs1.m3u8",
                            "backups": [
                                {"url": "https://old.example/checklist/x.m3u8"}
                            ],
                        }
                    ]
                },
                handle,
            )
        core.Settings.JSON_OUTPUT_FILE = path
        found = sources._previous_list_servers()
        self.assertIn("https://live.example", found)
        self.assertIn("https://old.example", found)


if __name__ == "__main__":
    unittest.main()
