import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_missing_open_think_tag():
    """
    Test that RealOpenAIClient correctly handles a response that has </think> but NO <think> at the start.
    This often happens when DeepSeek-R1 streams the output and misses the opening tag.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """Okay, so I need to analyze this thread about a video's first comment being truly captured. The user provided the thread content and some replies. Let me break this down step by step. First, I'll look at the main thread. It's about a video where the first comment was successfully captured. In summary, this thread is valuable. </think> ```json { "is_valuable": true, "value_tags": ["Authenticity", "Data Integrity"], "reason": "The thread demonstrates a method to verify the authenticity." } ```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == True
        assert result.value_tags == ["Authenticity", "Data Integrity"]
        assert result.reason == "The thread demonstrates a method to verify the authenticity."