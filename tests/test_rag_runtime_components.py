from app.services.rag_runtime_components import build_fallback_prompt
from app.services.rag_runtime_components import build_qa_prompt
from app.services.rag_runtime_components import build_summary_prompt
from app.services.rag_runtime_components import build_text_splitter


def test_rag_text_splitter_keeps_existing_chunk_settings():
    splitter = build_text_splitter()

    assert splitter._chunk_size == 1000
    assert splitter._chunk_overlap == 200
    assert splitter._separators == [
        "\n\n",
        "\n",
        "。",
        "！",
        "？",
        ".",
        "!",
        "?",
        " ",
    ]


def test_rag_prompts_keep_existing_roles_and_variables():
    qa_prompt = build_qa_prompt()
    fallback_prompt = build_fallback_prompt()
    summary_prompt = build_summary_prompt()

    assert qa_prompt.input_variables == ["context", "question"]
    assert fallback_prompt.input_variables == ["question"]
    assert summary_prompt.input_variables == ["content"]
    assert "知识库助手" in qa_prompt.messages[0].prompt.template
    assert "没有找到与用户问题相关的内容" in fallback_prompt.messages[0].prompt.template
    assert "内容总结专家" in summary_prompt.messages[0].prompt.template
