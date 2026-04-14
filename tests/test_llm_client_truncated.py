import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: str
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_truncated_output():
    """
    Test that RealOpenAIClient raises a meaningful error when the model output is completely truncated 
    and no valid JSON structure (no closing bracket) can be found.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "好，我现在需要分析这个用户提供的中文数据，并按照他们给的JSON schema来生成一个有效的响应。首先，我得仔细阅读用户的问题，了解他们想要什么。综上所述，这条数据在技术分析、网络安全、法律合规等方面都有潜在的价值，因此“is_valuable"

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_structured("test prompt", DummySchema)
            
        assert "Model output was likely truncated" in str(exc_info.value)
        assert "No complete JSON object found" in str(exc_info.value)