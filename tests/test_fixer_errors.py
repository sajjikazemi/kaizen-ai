from kaizen.fixer.errors import summarize_exception


class _FakeOpenAIError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Error code: 400 - {{'error': {{'message': '{message}'}}}}")
        self.body = {"error": {"message": message}}


def test_summarize_exception_extracts_openai_style_body_dict():
    exc = _FakeOpenAIError("Function tools with reasoning_effort are not supported for this model")
    summary = summarize_exception(exc)
    assert "Function tools with reasoning_effort" in summary
    assert "_FakeOpenAIError" in summary
    assert len(summary) < 200  # much shorter than the raw str(exc)


def test_summarize_exception_handles_json_string_body():
    exc = RuntimeError("boom")
    exc.body = '{"error": {"message": "bad request from string body"}}'
    summary = summarize_exception(exc)
    assert "bad request from string body" in summary


def test_summarize_exception_falls_back_to_first_line():
    exc = ValueError("first line\nsecond line with lots of detail")
    summary = summarize_exception(exc)
    assert summary == "first line"


def test_summarize_exception_truncates_long_messages():
    exc = ValueError("x" * 1000)
    summary = summarize_exception(exc)
    assert len(summary) <= 500
