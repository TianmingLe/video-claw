import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_schema_hallucination():
    """
    Test that RealOpenAIClient correctly extracts actual values when the model hallucinates
    and returns a JSON Schema definition instead of a plain JSON object.
    (e.g. wraps the answer in {"properties": {...}, "required": [...]})
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    # This simulates the model getting confused by `schema.schema_json()` and wrapping its answer
    mock_response.choices[0].message.content = """```json 
{ 
  "properties": { 
    "is_valuable": true, 
    "value_tags": ["Data Extraction", "Web Scraping"], 
    "reason": "Addresses specific technical problem." 
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
        assert result.value_tags == ["Data Extraction", "Web Scraping"]
        assert result.reason == "Addresses specific technical problem."