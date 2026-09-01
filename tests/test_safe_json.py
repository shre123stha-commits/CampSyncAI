import pytest

from utils.safe_json import JSONParseError, safe_json_parse


def test_plain_object():
    assert safe_json_parse('{"a": 1}') == {"a": 1}


def test_plain_array():
    assert safe_json_parse('[{"a": 1}]') == [{"a": 1}]


def test_markdown_fence():
    raw = '```json\n{"mode": "day_with_timings", "plan": []}\n```'
    assert safe_json_parse(raw)["mode"] == "day_with_timings"


def test_bare_fence():
    assert safe_json_parse('```\n{"a": 1}\n```') == {"a": 1}


def test_think_block_is_stripped():
    raw = '<think>Let me reason about this...</think>\n{"a": 1}'
    assert safe_json_parse(raw) == {"a": 1}


def test_think_block_containing_braces():
    raw = '<think>maybe {"b": 2} works</think>{"a": 1}'
    assert safe_json_parse(raw) == {"a": 1}


def test_leading_commentary():
    raw = 'Here is your study plan:\n{"plan": [1, 2]}'
    assert safe_json_parse(raw) == {"plan": [1, 2]}


def test_trailing_commentary():
    raw = '{"plan": []}\n\nHope this helps!'
    assert safe_json_parse(raw) == {"plan": []}


def test_braces_inside_strings_do_not_confuse_the_parser():
    raw = '{"work": "use the {placeholder} syntax", "n": 1}'
    parsed = safe_json_parse(raw)
    assert parsed["work"] == "use the {placeholder} syntax"


def test_escaped_quote_inside_string():
    raw = '{"work": "say \\"hello\\" politely"}'
    assert safe_json_parse(raw)["work"] == 'say "hello" politely'


def test_trailing_comma_is_repaired():
    raw = 'text {"a": 1, "b": 2,}'
    assert safe_json_parse(raw) == {"a": 1, "b": 2}


def test_nested_structures():
    raw = '{"plan": [{"sub": {"deep": [1, 2]}}]}'
    assert safe_json_parse(raw)["plan"][0]["sub"]["deep"] == [1, 2]


@pytest.mark.parametrize("bad", ["", "   ", "no json here at all", None])
def test_unparseable_raises(bad):
    with pytest.raises(JSONParseError):
        safe_json_parse(bad)
