import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_catastrophic_json_with_regex_fallback():
    """
    Test that RealOpenAIClient uses its ultimate regex fallback when json.loads 
    fails completely due to catastrophic JSON formatting.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    
    # This simulates the user's latest error:
    # 1. Missing comma after array
    # 2. Reason field unescaped and bleeding into trailing garbage
    # 3. Trailing garbage text that completely breaks JSON format
    mock_response.choices[0].message.content = """```json
{
  "is_valuable": "true",
  "value_tags": "["\\"technical terms\\"", \\"cybersecurity\\", \\"niche relevance\\"]",
  "reason": \\"The thread contains a technical term \\"真实抓取兜底\\" which is relevant to cybersecurity and data extraction techniques, making it valuable for analysis in that niche. The replies are neutral and do not add significant additional value beyond the main comment.\\ \\" technical terms \\"\\" \\" cybersecurity \\"\\" \\" niche relevance \\"\\" \\" reason \\"\\" "
```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        # Verify that despite the garbage, the regex fallback successfully extracted the fields
        assert result.is_valuable == True
        assert "technical terms" in result.value_tags
        assert "cybersecurity" in result.value_tags
        assert "niche relevance" in result.value_tags
        assert "The thread contains a technical term" in result.reason