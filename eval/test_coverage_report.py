from coverage_report import is_word, parse_tokens


def test_known_and_unknown_tokens():
    assert parse_tokens("^abc/abc<n>$ ^xyz/*xyz$") == [("abc", True), ("xyz", False)]


def test_multiple_analyses_count_as_known():
    assert parse_tokens("^abc/abc<n>/abc<v>$") == [("abc", True)]


def test_escaped_characters_stay_in_the_token():
    assert parse_tokens(r"^a\/b/*a\/b$ ^\$5/*\$5$") == [("a/b", False), ("$5", False)]


def test_is_word_needs_a_letter():
    assert is_word("1828дж")
    assert not is_word("1828")
    assert not is_word(".")
