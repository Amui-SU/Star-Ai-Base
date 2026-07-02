import pytest

from app.services.rag_summary import summarize_text_content


@pytest.mark.asyncio
async def test_summarize_text_content_truncates_long_content_before_invoking_chain():
    invoked = []

    class FakeChain:
        async def ainvoke(self, content):
            invoked.append(content)
            return "summary"

    def build_chain(summary_prompt, llm):
        assert summary_prompt == "prompt"
        assert llm == "llm"
        return FakeChain()

    content = "a" * 10005

    result = await summarize_text_content(
        content,
        summary_prompt="prompt",
        llm="llm",
        build_chain=build_chain,
    )

    assert result == "summary"
    assert invoked == ["a" * 10000 + "\n...(内容已截断)"]
