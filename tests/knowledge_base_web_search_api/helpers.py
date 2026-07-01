import json

from tests.test_knowledge_base_scoping import create_knowledge_base, register_user


def fake_document(page_content: str, metadata: dict):
    return type(
        "FakeDocument",
        (),
        {
            "page_content": page_content,
            "metadata": metadata,
        },
    )()


class FakeToolFunction:
    def __init__(self, name: str, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments):
        self.id = call_id
        self.function = FakeToolFunction(name, arguments)


class FakeMessage:
    def __init__(self, *, content: str = "", tool_calls=None):
        self.content = content
        self.reasoning_content = ""
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls is not None:
            data["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in self.tool_calls
            ]
        return data


def fake_completion_response(*, content: str = "", tool_calls=None):
    return type(
        "Response",
        (),
        {
            "choices": [
                type(
                    "Choice",
                    (),
                    {"message": FakeMessage(content=content, tool_calls=tool_calls)},
                )()
            ]
        },
    )()


def fake_client(completions):
    return type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": completions})()},
    )()


def web_search_tool_call(call_id: str, arguments, *, encode_json: bool = True):
    encoded_arguments = (
        json.dumps(arguments, ensure_ascii=False) if encode_json else arguments
    )
    return FakeToolCall(call_id, "web_search", encoded_arguments)
