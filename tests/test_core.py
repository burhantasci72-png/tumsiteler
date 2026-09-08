#!/usr/bin/env python3
"""core.py birim testleri (ag erisimi gerektirmez)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core
from core import StreamInfo


class TestNaming(unittest.TestCase):
    def test_canonical_bein(self):
        for raw in [
            "Bein Sports 1",
            "BEIN SPORTS 1",
            "NET - Bein Sports 1CANLI|7/24.",
            "SL - BEIN SPORTS 1",
            "TR:beIN Sport 1 HD",
            "B1 ydk",
            "beinsports 1",
        ]:
            with self.subTest(raw=raw):
                result = core.canonical_channel(raw)
                self.assertIsNotNone(result, raw)
                self.assertEqual(result[1], "beIN Sports 1", raw)

    def test_max_not_confused_with_plain(self):
        self.assertEqual(core.canonical_channel("Bein Max 1")[1], "beIN Sports Max 1")
        self.assertEqual(
            core.canonical_channel("beIN Sports Max 2")[1], "beIN Sports Max 2"
        )
        self.assertEqual(core.canonical_channel("Bein Sports 2")[1], "beIN Sports 2")

    def test_s_sport_variants(self):
        self.assertEqual(core.canonical_channel("S Sport 2")[1], "S Sport 2")
        self.assertEqual(core.canonical_channel("S SPORT")[1], "S Sport 1")
        self.assertEqual(core.canonical_channel("S Sport Plus")[1], "S Sport Plus")

    def test_tail_noise_removed(self):
        self.assertEqual(core.clean_title("NET - A SporCANLI|7/24."), "A Spor")
        self.assertEqual(core.clean_title("ATOM - Tivibu Spor 1"), "Tivibu Spor 1")

    def test_non_channel_returns_none(self):
        self.assertIsNone(core.canonical_channel("Galatasaray - Fenerbahce"))


class TestEvents(unittest.TestCase):
    def test_parse_event_full(self):
        event = core.parse_event(
            "NET - Club Brugge - Aston Villa19:45|UEFA Şampiyonlar Ligi"
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["home"], "Club Brugge")
        self.assertEqual(event["away"], "Aston Villa")
        self.assertEqual(event["time"], "19:45")
        self.assertEqual(event["competition"], "UEFA Şampiyonlar Ligi")

    def test_event_key_order_independent(self):
        a = core.parse_event("A Takim - B Takim20:00|Lig")
        b = core.parse_event("B Takim - A Takim20:00|Lig")
        self.assertEqual(core.event_key(a), core.event_key(b))

    def test_channel_is_not_event(self):
        self.assertIsNone(core.parse_event("beIN Sports 1"))
        self.assertIsNone(core.parse_event("Tivibu Spor 3"))


class TestDedupe(unittest.TestCase):
    def _make(self, name, url, verified=True, latency=100):
        return StreamInfo(
            name=name, url=url, group="G", verified=verified, latency_ms=latency
        )

    def test_merges_same_channel_across_sources(self):
        streams = [
            self._make("NET - Bein Sports 1CANLI|7/24.", "http://a/1.m3u8", True, 300),
            self._make("SL - BEIN SPORTS 1", "http://b/1.m3u8", True, 100),
            self._make("ATOM - Bein Sports 1", "http://c/1.m3u8", True, 200),
        ]
        core.assign_keys(streams)
        merged = core.dedupe_and_rank(streams)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].name, "beIN Sports 1")
        # En dusuk gecikmeli birincil olmali
        self.assertEqual(merged[0].url, "http://b/1.m3u8")
        self.assertEqual(len(merged[0].backups), 2)

    def test_verified_preferred_over_unverified(self):
        streams = [
            self._make("Bein Sports 3", "http://slow/ok.m3u8", False, 10),
            self._make("Bein Sports 3", "http://fast/ok.m3u8", True, 900),
        ]
        core.assign_keys(streams)
        merged = core.dedupe_and_rank(streams)
        self.assertEqual(merged[0].url, "http://fast/ok.m3u8")

    def test_backups_keep_own_referrer(self):
        """Yedekler kendi Referer'ini korumali; aksi halde failover 403 alir."""
        a = self._make("Bein Sports 1", "http://a/1.m3u8", True, 100)
        a.referrer = "https://site-a/"
        a.source = "a"
        b = self._make("ATOM - Bein Sports 1", "http://b/1.m3u8", True, 500)
        b.referrer = "https://site-b/"
        b.source = "b"

        core.assign_keys([a, b])
        merged = core.dedupe_and_rank([a, b])

        self.assertEqual(merged[0].referrer, "https://site-a/")
        self.assertEqual(merged[0].backups[0].referrer, "https://site-b/")
        self.assertEqual(merged[0].backups[0].source, "b")

    def test_identical_urls_collapse(self):
        streams = [
            self._make("Bein Sports 4", "http://same/x.m3u8"),
            self._make("NET - Bein Sports 4CANLI|7/24.", "http://same/x.m3u8"),
        ]
        core.assign_keys(streams)
        merged = core.dedupe_and_rank(streams)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].backups, [])


class TestCategories(unittest.TestCase):
    """Kategoriler temiz ve oncelik sirali olmali (beIN Sports en basta)."""

    def test_bein_is_first_category(self):
        self.assertEqual(core.CATEGORY_ORDER[0], "BEIN SPORTS")
        self.assertEqual(core.categorize("beIN Sports 3"), "BEIN SPORTS")
        self.assertEqual(core.categorize("S Sport 2"), "S SPORT")
        self.assertEqual(core.categorize("Tivibu Spor 1"), "TİVİBU SPOR")
        self.assertEqual(core.categorize("TRT Spor"), "TRT SPOR")
        self.assertEqual(core.categorize("Tabii Spor 2"), "TABİİ SPOR")
        self.assertEqual(core.categorize("Eurosport 1"), "DİĞER SPOR KANALLARI")
        self.assertEqual(core.categorize("x", is_event=True), "CANLI MAÇLAR")

    def test_rank_order(self):
        ranks = [core.category_rank(c) for c in core.CATEGORY_ORDER]
        self.assertEqual(ranks, sorted(ranks))
        self.assertGreater(core.category_rank("BILINMEYEN"), ranks[-1])

    def test_group_is_category_after_assign(self):
        stream = StreamInfo(name="NET - Bein Sports 1", url="http://a/1.m3u8",
                            group="NETSPOR")
        core.assign_keys([stream])
        self.assertEqual(stream.group, "BEIN SPORTS")

    def test_bein_sports_sorted_before_others(self):
        streams = [
            StreamInfo(name="Eurosport 1", url="http://a/e.m3u8", group="X"),
            StreamInfo(name="S Sport 1", url="http://a/s.m3u8", group="X"),
            StreamInfo(name="Bein Sports 1", url="http://a/b1.m3u8", group="X"),
            StreamInfo(name="22:00 Porto - Manchester City", url="http://a/m.m3u8",
                       group="X"),
        ]
        core.assign_keys(streams)
        merged = core.dedupe_and_rank(streams)
        self.assertEqual(merged[0].name, "beIN Sports 1")
        self.assertEqual(merged[-1].name, "22:00 Porto - Manchester City")
        self.assertEqual([s.group for s in merged][0], "BEIN SPORTS")

    def test_turkish_prefix_stripped(self):
        """'İNADINA - TİVİBU SPOR 4' gibi kaynak onekleri atilabilmeli."""
        result = core.canonical_channel("İNADINA - TİVİBU SPOR 4")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "Tivibu Spor 4")

    def test_two_letter_tag_is_not_event(self):
        self.assertIsNone(core.parse_event("TR - KUKILI TV"))
        self.assertIsNotNone(core.parse_event("Fenerbahçe - Beşiktaş"))


class TestSportsFilter(unittest.TestCase):
    """Spor disi kanallar (cocuk/haber/ulusal) listeye girmemeli."""

    def test_non_sport_dropped(self):
        streams = [
            StreamInfo(name="TRT COCUK HD", url="http://a/1.m3u8", group="TR: COCUK"),
            StreamInfo(name="KANAL D UHD", url="http://a/2.m3u8", group="TR ULUSAL-UHD"),
            StreamInfo(name="HABER GLOBAL", url="http://a/3.m3u8", group="HABER"),
            StreamInfo(name="Bein Sports 1", url="http://a/4.m3u8", group="NETSPOR"),
            StreamInfo(name="19:45 Fenerbahçe - Beşiktaş", url="http://a/5.m3u8",
                       group="Süper Lig"),
            StreamInfo(name="Web BeIN Sports+++", url="http://a/6.m3u8",
                       group="SPOR KANALI"),
        ]
        kept, dropped = core.filter_publishable(streams)
        names = {s.name for s in kept}
        self.assertIn("Bein Sports 1", names)
        self.assertIn("19:45 Fenerbahçe - Beşiktaş", names)
        self.assertNotIn("TRT COCUK HD", names)
        self.assertNotIn("KANAL D UHD", names)
        self.assertNotIn("HABER GLOBAL", names)
        self.assertNotIn("Web BeIN Sports+++", names)
        self.assertEqual(sum(dropped.values()), 4)

    def test_national_group_keeps_sports_channel(self):
        """Ulusal grup icindeki TV 8.5 gibi spor kanallari korunmali."""
        streams = [
            StreamInfo(name="TV 8.5", url="http://a/1.m3u8", group="TR ULUSAL-UHD"),
            StreamInfo(name="STAR TV HD", url="http://a/2.m3u8", group="TR ULUSAL-UHD"),
        ]
        kept, _dropped = core.filter_publishable(streams)
        self.assertEqual([s.name for s in kept], ["TV 8.5"])


class TestExtraction(unittest.TestCase):
    def test_absolute(self):
        text = 'var s = "https://cdn.x/live/a.m3u8?t=1";'
        self.assertEqual(
            core.find_m3u8_in_text(text, "https://p/"), "https://cdn.x/live/a.m3u8?t=1"
        )

    def test_relative(self):
        text = "source: '/hls/stream.m3u8'"
        self.assertEqual(
            core.find_m3u8_in_text(text, "https://p/page"),
            "https://p/hls/stream.m3u8",
        )

    def test_base64_atob(self):
        import base64

        blob = base64.b64encode(b"https://cdn.y/z.m3u8").decode()
        text = f"var u = atob('{blob}');"
        self.assertEqual(core.find_m3u8_in_text(text, "https://p/"), "https://cdn.y/z.m3u8")

    def test_url_encoded(self):
        text = "u=https%3A%2F%2Fcdn.z%2Fs.m3u8&x=1"
        self.assertEqual(core.find_m3u8_in_text(text, "https://p/"), "https://cdn.z/s.m3u8")

    def test_no_match(self):
        self.assertIsNone(core.find_m3u8_in_text("<html>nothing</html>", "https://p/"))


class TestOutput(unittest.TestCase):
    def test_m3u_contains_headers(self):
        streams = [
            StreamInfo(
                name="beIN Sports 1",
                url="https://cdn/a.m3u8",
                group="TEST",
                referrer="https://ref/",
                key="beinsports1",
                verified=True,
            )
        ]
        text = core.build_m3u(streams, "now")
        self.assertIn("#EXTM3U", text)
        self.assertIn("http-referrer=https://ref/", text)
        self.assertIn("http-user-agent=", text)
        self.assertIn('group-title="TEST"', text)
        self.assertIn("https://cdn/a.m3u8", text)

    def test_json_roundtrip(self):
        import json

        streams = [
            StreamInfo(
                name="beIN Sports 1",
                url="https://cdn/a.m3u8",
                group="TEST",
                key="beinsports1",
                verified=True,
                backups=[core.BackupLink(url="https://cdn/b.m3u8",
                                         referrer="https://other/")],
            )
        ]
        data = json.loads(core.build_json(streams, "now"))
        self.assertEqual(data["count"], 1)
        backup = data["channels"][0]["backups"][0]
        self.assertEqual(backup["url"], "https://cdn/b.m3u8")
        # Yedek KENDI referrer'ini korumali
        self.assertEqual(backup["referrer"], "https://other/")
        # JSON ham adres tasir; proxy calisma zamaninda uygulanir
        self.assertEqual(data["channels"][0]["url"], "https://cdn/a.m3u8")

    def test_proxy_wrapping(self):
        original = core.Settings.PLAYER_PROXY
        try:
            core.Settings.PLAYER_PROXY = "https://proxy.dev"
            out = core.proxied("https://cdn/a.m3u8", "https://ref/")
            self.assertTrue(out.startswith("https://proxy.dev/hls?"))
            self.assertIn("url=https%3A%2F%2Fcdn%2Fa.m3u8", out)
            self.assertIn("ref=https%3A%2F%2Fref%2F", out)
        finally:
            core.Settings.PLAYER_PROXY = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
