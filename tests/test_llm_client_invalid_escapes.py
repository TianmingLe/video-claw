import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_invalid_escape_characters():
    """
    Test that RealOpenAIClient can handle malformed JSON with invalid escape characters,
    such as inner quotes being escaped incorrectly, which breaks json.loads().
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    # This simulates the model hallucinating extra escaped quotes around an array, or inside an array.
    # Like `"value_tags": "["\"个人见解\"", \"情感反馈\"]"` which is totally invalid JSON.
    mock_response.choices[0].message.content = """```json
{
  "is_valuable": "false",
  "value_tags": "["\\"个人见解\\"", \\"情感反馈\\"]",
  "reason": "This is a test."
}
```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == False
        # The list parsing fallback should ideally extract these two tags
        assert "个人见解" in result.value_tags
        assert "情感反馈" in result.value_tags
        assert result.reason == "This is a test."