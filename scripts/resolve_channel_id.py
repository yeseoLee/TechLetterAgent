"""채널 URL/핸들로부터 YouTube channel_id 를 찾아 config/channels.json 채우기를 돕는다.

사용법:
    python scripts/resolve_channel_id.py https://www.youtube.com/@woowatech
"""
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0"}


def resolve(url: str) -> str | None:
    html = requests.get(url, headers=UA, timeout=15).text
    m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', html)
    return m.group(1) if m else None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    channel_id = resolve(sys.argv[1])
    print(channel_id or "찾지 못했습니다. 채널 페이지 HTML에서 channelId 를 직접 확인하세요.")
