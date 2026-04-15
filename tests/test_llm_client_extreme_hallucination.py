import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: bool
    value_tags: list[str]
    reason: str

def test_real_openai_client_handles_extreme_schema_hallucination_with_fallback_regex():
    """
    Test that RealOpenAIClient can fall back to regex extraction if the model outputs 
    a completely invalid JSON Schema (where data isn't cleanly inside properties).
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """```json
{ 
  "properties": { 
    "is_valuable": { "title": "Is Valuable", "type": "boolean", "default": true }, 
    "value_tags": { "title": "Value Tags", "type": "string", "default": "真实抓取, 回复积极" }, 
    "reason": { "title": "Reason", "type": "string", "default": "该帖子展示了真实抓取的措施。" } 
  }, 
  "required": ["is_valuable", "value_tags", "reason"], 
  "title": "ThreadAnalysis", 
  "type": "object" 
}
```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        
        # In this extreme case, standard JSON parsing might fail to extract the real values 
        # (they are buried in "default" keys inside the schema properties).
        # The client should be smart enough to at least extract these defaults or fail gracefully.
        # But wait! If we modify our system prompt to NEVER output "properties" and it STILL DOES,
        # we can parse the AST. Let's see if we can extract values.
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == True
        # Note: the mock uses a comma-separated string for value_tags because the hallucination did
        assert "真实抓取" in result.value_tags[0] if len(result.value_tags) == 1 else "真实抓取" in result.value_tags
        assert "该帖子展示了真实抓取" in result.reason