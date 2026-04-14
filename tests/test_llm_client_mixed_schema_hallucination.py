import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_mixed_schema_hallucination():
    """
    Test that RealOpenAIClient correctly extracts actual values when the model outputs
    data wrapped inside a "properties" key alongside other schema keys like "required" and "title".
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """```json
{
  "properties": {
    "is_valuable": true,
    "value_tags": ["Data Extraction", "Web Scraping", "Analysis"],
    "reason": "Addresses specific technical problem related to data extraction from video comments."
  },
  "required": ["is_valuable", "value_tags", "reason"],
  "title": "ThreadAnalysis"
}
```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == True
        assert result.value_tags == ["Data Extraction", "Web Scraping", "Analysis"]
        assert result.reason == "Addresses specific technical problem related to data extraction from video comments."