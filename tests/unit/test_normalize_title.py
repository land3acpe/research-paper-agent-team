from src.normalize.title import normalize_title


def test_lowercase():
    assert normalize_title("Dual Three-Phase PMSM") == "dual three-phase pmsm"


def test_strip_punctuation():
    assert normalize_title("FOC: A Survey!") == "foc a survey"


def test_collapse_whitespace():
    assert normalize_title("  Multiple   Spaces  ") == "multiple spaces"


def test_unicode_dashes():
    # en-dash / em-dash should both collapse to plain hyphen
    assert normalize_title("dtp\u2013pmsm \u2014 method") == "dtp-pmsm method"


def test_strip_html_tags():
    assert normalize_title("<i>Italic</i> Title") == "italic title"


def test_idempotent():
    once = normalize_title("Some Title!")
    twice = normalize_title(once)
    assert once == twice
