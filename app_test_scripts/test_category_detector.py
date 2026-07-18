from src.llm.category_detector import _extract_json_from_response


def test_extract_json_raw_object():
    content = '{"preferred_category":"profile","confidence":0.95,"reasoning":"ok"}'
    result = _extract_json_from_response(content)
    assert result == content


def test_extract_json_with_prefix_and_suffix_text():
    content = 'Model output: {"preferred_category":"subject","confidence":0.7,"reasoning":"matched"} done.'
    result = _extract_json_from_response(content)
    assert result == '{"preferred_category":"subject","confidence":0.7,"reasoning":"matched"}'


def test_extract_json_with_braces_inside_string():
    content = (
        '{"preferred_category":"detail","confidence":0.8,"reasoning":"contains brace text like {example} safely"} trailing'
    )
    result = _extract_json_from_response(content)
    assert result == (
        '{"preferred_category":"detail","confidence":0.8,"reasoning":"contains brace text like {example} safely"}'
    )


def test_extract_json_returns_original_when_decode_fails():
    content = "prefix {not valid json"
    result = _extract_json_from_response(content)
    assert result == content
