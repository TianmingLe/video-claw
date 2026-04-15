import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_unescaped_quotes_in_list_fallback():
    """
    Test that RealOpenAIClient uses its ultimate regex fallback when json.loads 
    fails completely due to an array string having UNESCAPED inner quotes.
    e.g. "value_tags": "["cybersecurity", "technical"]"
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    
    # This simulates the user's VERY latest error:
    mock_response.choices[0].message.content = """```json
{
  "is_valuable": "false",
  "value_tags": "["cybersecurity", "technical discussions", "avoiding pitfalls"]",
  "reason": "The thread discusses real抓取底端, which is valuable for understanding cybersecurity concepts, but the use of emojis may detract from its depth."
}
```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        # Verify that despite the garbage, the regex fallback successfully extracted the fields
        assert result.is_valuable == False
        assert "cybersecurity" in result.value_tags
        assert "technical discussions" in result.value_tags
        assert "avoiding pitfalls" in result.value_tags
        assert "The thread discusses real抓取底端" in result.reason