from src.utils.hashing import title_hash


def test_title_hash_stable():
    assert title_hash("Dual Three-Phase PMSM") == title_hash("Dual Three-Phase PMSM")


def test_title_hash_normalizes():
    # Different case/punctuation should produce the same hash
    assert title_hash("Dual Three-Phase PMSM!") == title_hash("dual three-phase pmsm")


def test_title_hash_distinct():
    assert title_hash("Topic A") != title_hash("Topic B")


def test_title_hash_length():
    assert len(title_hash("anything")) == 16  # first 16 hex of sha256
