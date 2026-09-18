"""Blog Agent — 빅테크 기술 블로그의 신규 글을 RSS/Atom 피드로 수집한다.

유튜브 파이프라인(content_agent)과 같은 dict 모양으로 돌려주므로 run_collect 의
사전 필터 → 분석 → 임베딩 단계를 그대로 탄다. 구분은 `kind: "blog"` 와
`youtube_id` 부재로 한다. 중복 판정 키는 url.

피드 파싱은 stdlib xml.etree 로 한다. RSS 2.0(channel/item)과 Atom(entry)
둘 다 태그 이름만 다르고 구조는 같아서 `{*}` 와일드카드로 한 번에 처리한다.
"""
import html
import logging
import re
import xml.etree.ElementTree as ET

import requests

from . import config, content_store

log = logging.getLogger(__name__)

_TAG = re.compile(r"<[^>]+>")
# 분석 입력으로 넣을 요약 길이. 피드 요약은 글 도입부라 이 정도면 주제 판단에 충분하다.
SUMMARY_CHARS = 3000


def _text(node, *names: str) -> str:
    """names 중 처음 찾은 자식 요소의 텍스트. 없으면 빈 문자열."""
    for name in names:
        if (child := node.find(f"{{*}}{name}")) is not None and (child.text or "").strip():
            return child.text.strip()
    return ""


def _link(node) -> str:
    """RSS 는 <link>텍스트</link>, Atom 은 <link href=...>."""
    for child in node.findall("{*}link"):
        if href := child.get("href"):
            if child.get("rel") in (None, "alternate"):
                return href
        elif (child.text or "").strip():
            return child.text.strip()
    return ""


def _plain(markup: str) -> str:
    """HTML 을 평문으로. 피드 요약에는 태그가 섞여 있다."""
    return " ".join(html.unescape(_TAG.sub(" ", markup)).split())


def parse_feed(xml_text: str) -> list[dict]:
    """RSS/Atom XML 을 {url, title, published_at, description} 목록으로 바꾼다."""
    root = ET.fromstring(xml_text)
    posts = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        url = _link(item)
        if not url:
            continue
        posts.append({
            "url": url,
            "title": _plain(_text(item, "title")),
            "published_at": _text(item, "pubDate", "published", "updated"),
            "description": _plain(_text(item, "content", "encoded", "description", "summary"))[:SUMMARY_CHARS],
        })
    return posts


def collect_new_posts(per_source: int = 20) -> list[dict]:
    """blogs.json 의 전 피드에서 videos.json 에 없는 글만 반환한다."""
    sources = content_store.load(config.BLOGS, {}).get("blogs", [])
    known = {v.get("url") for v in content_store.load(config.VIDEOS, [])}
    fresh: list[dict] = []

    for blog in sources:
        try:
            response = requests.get(blog["feed"], timeout=20,
                                    headers={"User-Agent": "TechLetterAgent/1.0"})
            response.raise_for_status()
            posts = parse_feed(response.text)[:per_source]
        except Exception as exc:  # 피드 하나가 죽어도 나머지는 계속 수집한다.
            log.warning("피드 조회 실패 (%s): %s", blog["name"], exc)
            continue

        added = 0
        for post in posts:
            if post["url"] in known:
                continue
            known.add(post["url"])
            post.update({
                "kind": "blog",
                "source": blog["name"],
                "channel": blog["name"],
                "language": blog.get("language", "en"),
                "duration_sec": None,  # 글에는 길이가 없다. 사전 필터는 None 을 통과시킨다.
            })
            fresh.append(post)
            added += 1
        log.info("%s: %d개 조회, 신규 %d개", blog["name"], len(posts), added)

    return fresh
