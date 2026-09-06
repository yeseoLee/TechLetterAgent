"""collect.yml 진입점: 신규 영상 수집 → 사전 필터 → 분석 → videos.json 갱신.

무료 모델 요청 한도를 아끼기 위해 비싼 단계를 뒤로 미룬다:
  RSS 수집 → prefilter 규칙 판정 → prefilter LLM 판정 → 자막 추출 → LLM 분석 → 임베딩
분석 건수는 config.MAX_ANALYSIS_PER_RUN 으로 제한하고, 초과분은 다음 실행으로 밀린다.
"""


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
