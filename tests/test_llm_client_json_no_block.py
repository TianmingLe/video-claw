import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: str
    value_tags: list[str]
    reason: str

def test_real_openai_client_parses_responses_without_think_tags_but_with_preamble_no_code_blocks():
    """
    Test that RealOpenAIClient correctly strips preambles when <think> tags are absent
    AND no markdown code blocks are used.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """Okay, here is the JSON you requested:
{
  "is_valuable": "true",
  "value_tags": ["Social Media"],
  "reason": "Because it is."
}
Hope this helps!"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == "true"
        assert result.value_tags == ["Social Media"]
        assert result.reason == "Because it is."