"""블로그 피드 수집 테스트 (네트워크 없음)."""
import json

from src import blog_agent, config

RSS = """<rss><channel>
<item><title>Scaling &amp; Sharding</title><link>https://x.test/a</link>
<description><![CDATA[<p>How we <b>sharded</b> Postgres.</p>]]></description><pubDate>Mon, 01 Sep 2026 00:00:00 GMT</pubDate></item>
<item><title>Old</title><link>https://x.test/old</link><description>seen</description></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom post</title><link rel="alternate" href="https://y.test/b"/>
<summary>Atom summary</summary><published>2026-09-01T00:00:00Z</published></entry>
</feed>"""


def test_parse_rss_and_atom():
    rss = blog_agent.parse_feed(RSS)
    assert rss[0] == {"url": "https://x.test/a", "title": "Scaling & Sharding",
                      "published_at": "Mon, 01 Sep 2026 00:00:00 GMT",
                      "description": "How we sharded Postgres."}
    atom = blog_agent.parse_feed(ATOM)
    assert atom[0]["url"] == "https://y.test/b" and atom[0]["description"] == "Atom summary"


def test_collect_skips_known_and_bad_feeds(tmp_path, monkeypatch):
    blogs = tmp_path / "blogs.json"
    blogs.write_text(json.dumps({"blogs": [
        {"name": "X", "feed": "http://x", "language": "en"},
        {"name": "Dead", "feed": "http://dead"},
    ]}))
    videos = tmp_path / "videos.json"
    videos.write_text(json.dumps([{"url": "https://x.test/old"}]))
    monkeypatch.setattr(config, "BLOGS", blogs)
    monkeypatch.setattr(config, "VIDEOS", videos)

    class Resp:
        text = RSS
        def raise_for_status(self): pass

    def fake_get(url, **_):
        if url == "http://dead":
            raise ConnectionError("down")
        return Resp()
    monkeypatch.setattr(blog_agent.requests, "get", fake_get)

    fresh = blog_agent.collect_new_posts()
    assert [p["url"] for p in fresh] == ["https://x.test/a"]
    assert fresh[0]["kind"] == "blog" and fresh[0]["source"] == "X" and fresh[0]["duration_sec"] is None
