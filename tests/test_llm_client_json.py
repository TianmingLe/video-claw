import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: str
    value_tags: list[str]
    reason: str

def test_real_openai_client_parses_think_tags_correctly():
    """
    Test that RealOpenAIClient correctly strips <think> tags from DeepSeek R1 responses
    before parsing the JSON.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """<think>
Okay, so I'm trying to analyze this thread.
I'll make sure to keep the JSON clean.
</think>
```json
{
  "is_valuable": "true",
  "value_tags": ["Social Media", "Video Analysis"],
  "reason": "The thread discusses a video's first comment."
}
```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == "true"
        assert result.value_tags == ["Social Media", "Video Analysis"]
        assert result.reason == "The thread discusses a video's first comment."