"""임베딩 base64 인코딩 왕복 검증."""
import numpy as np

from src.embedding_store import decode, encode, matrix


def test_roundtrip_preserves_values():
    original = [0.0, 1.0, -1.0, 0.123456789, -0.000123]
    restored = decode(encode(original))
    assert len(restored) == len(original)
    # float32 로 낮추므로 완전 일치가 아니라 근사 일치를 본다.
    np.testing.assert_allclose(restored, original, rtol=1e-6, atol=1e-8)


def test_roundtrip_preserves_cosine_similarity():
    rng = np.random.default_rng(42)
    a, b = rng.normal(size=4096), rng.normal(size=4096)

    def cos(x, y):
        return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))

    before = cos(a, b)
    after = cos(decode(encode(a)).astype(np.float64), decode(encode(b)).astype(np.float64))
    assert abs(before - after) < 1e-6, f"{before} vs {after}"


def test_matrix_skips_missing_ids():
    store = {"video_001": encode([1.0, 2.0]), "video_003": encode([3.0, 4.0])}
    ids, m = matrix(["video_001", "video_002", "video_003"], store)
    assert ids == ["video_001", "video_003"]
    assert m.shape == (2, 2)


def test_matrix_handles_empty():
    ids, m = matrix(["nope"], {})
    assert ids == [] and m.shape == (0, 0)
