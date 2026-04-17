"""Tests for decipher.analyzer."""

from decipher.analyzer import _parse_json_response


class TestParseJsonResponse:
    def test_clean_json(self):
        text = '{"architecture": "Monolith", "components": ["web", "api"]}'
        result = _parse_json_response(text)
        assert result is not None
        assert result["architecture"] == "Monolith"

    def test_json_in_markdown_fences(self):
        text = '```json\n{"architecture": "MVC"}\n```'
        result = _parse_json_response(text)
        assert result is not None
        assert result["architecture"] == "MVC"

    def test_json_with_surrounding_text(self):
        text = 'Here is the analysis:\n{"architecture": "Microservices"}\nEnd.'
        result = _parse_json_response(text)
        assert result is not None
        assert result["architecture"] == "Microservices"

    def test_invalid_json(self):
        result = _parse_json_response("This is not JSON at all.")
        assert result is None

    def test_empty_string(self):
        result = _parse_json_response("")
        assert result is None
