"""GitHub Actions IP 에서 유튜브 접근 경로별로 무엇이 되는지 확인하는 진단 스크립트.

로컬(주거용 IP)에서는 다 되지만 데이터센터 IP 에서는 차단되는 경로가 있어,
어떤 수집 방식을 택할지 결정하려면 실제 러너에서 재봐야 한다.
"""
import time

import requests

VIDEO = "wo0Rsh9hlTo"
CHANNEL = "UCNrehnUq7Il-J7HQxrzp7CA"
PLAYLIST = "PLGIkkJsrT83Y"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}


def probe(label, fn):
    try:
        print(f"  {label:<38} {fn()}")
    except Exception as exc:
        print(f"  {label:<38} 실패: {str(exc)[:90]}")


def rss(kind, ident, headers=None, attempts=6):
    url = f"https://www.youtube.com/feeds/videos.xml?{kind}={ident}"
    codes = []
    for i in range(attempts):
        r = requests.get(url, headers=headers or {}, timeout=15)
        codes.append(r.status_code)
        if r.ok:
            return f"성공 (시도 {i + 1}회차) codes={codes}"
        time.sleep(2 * (i + 1))
    return f"전부 실패 codes={codes}"


print("=== 1. RSS ===")
probe("채널 RSS (UA 없음)", lambda: rss("channel_id", CHANNEL))
probe("채널 RSS (브라우저 UA)", lambda: rss("channel_id", CHANNEL, UA))
probe("재생목록 RSS (브라우저 UA)", lambda: rss("playlist_id", PLAYLIST, UA))

print("\n=== 2. oEmbed (제목/채널명만) ===")
probe("oembed", lambda: requests.get(
    f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={VIDEO}&format=json",
    timeout=15).status_code)

print("\n=== 3. watch 페이지 직접 ===")
def watch():
    r = requests.get(f"https://www.youtube.com/watch?v={VIDEO}", headers=UA, timeout=20)
    has_caption = "captionTracks" in r.text
    return f"HTTP {r.status_code}, {len(r.text)}바이트, captionTracks={has_caption}"
probe("watch 페이지", watch)

print("\n=== 4. yt-dlp ===")
def ytdlp(opts_extra=None):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    opts.update(opts_extra or {})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={VIDEO}", download=False)
    return f"성공 duration={info.get('duration')} auto_caps={len(info.get('automatic_captions') or {})}"

probe("yt-dlp 기본", ytdlp)
probe("yt-dlp web_safari 클라이언트", lambda: ytdlp(
    {"extractor_args": {"youtube": {"player_client": ["web_safari"]}}}))
probe("yt-dlp android 클라이언트", lambda: ytdlp(
    {"extractor_args": {"youtube": {"player_client": ["android"]}}}))
probe("yt-dlp tv 클라이언트", lambda: ytdlp(
    {"extractor_args": {"youtube": {"player_client": ["tv"]}}}))
