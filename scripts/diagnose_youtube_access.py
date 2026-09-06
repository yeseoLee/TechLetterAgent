"""GitHub Actions IP 에서 유튜브 자막 접근이 되는지 확인하는 진단 스크립트.

로컬(주거용 IP)에서는 되지만 데이터센터 IP 에서는 막히는 경로가 있어,
어떤 방식을 택할지 결정하려면 실제 러너에서 재봐야 한다.
"""
import sys

VIDEOS = [
    ("wo0Rsh9hlTo", "NAVER D2 - Playwright E2E (ko 자동자막)"),
    ("EEsYbiqqcc0", "토스 SLASH 22 - ML 서비스 (ko)"),
    ("VdElizwWE4s", "kakao tech - AI Coding Agent (ko)"),
]


def probe(label, fn):
    try:
        print(f"  {label:<44} {fn()}")
        return True
    except Exception as exc:
        print(f"  {label:<44} 실패: {type(exc).__name__}: {str(exc)[:130]}")
        return False


def via_transcript_api(video_id):
    from youtube_transcript_api import YouTubeTranscriptApi

    fetched = YouTubeTranscriptApi().fetch(video_id, languages=("ko", "en"))
    head = [s.text for s in fetched.snippets if s.start < 180]
    return (f"성공 lang={fetched.language_code} generated={fetched.is_generated} "
            f"조각={len(fetched.snippets)} 초반3분={len(' '.join(head))}자")


def via_ytdlp(video_id):
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    return f"성공 자동자막 {len(info.get('automatic_captions') or {})}개 언어"


print("=== youtube-transcript-api ===")
ok = sum(probe(name, lambda v=vid: via_transcript_api(v)) for vid, name in VIDEOS)
print(f"  → {ok}/{len(VIDEOS)} 성공")

print("\n=== yt-dlp (비교용) ===")
probe(VIDEOS[0][1], lambda: via_ytdlp(VIDEOS[0][0]))

sys.exit(0 if ok else 1)
