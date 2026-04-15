import pytest
from pydantic import BaseModel
from backend.llm.client import RealOpenAIClient
from unittest.mock import MagicMock, patch

class DummySchema(BaseModel):
    is_valuable: str
    value_tags: list[str]
    reason: str

def test_real_openai_client_parses_responses_without_think_tags_but_with_preamble():
    """
    Test that RealOpenAIClient correctly strips preambles when <think> tags are absent
    (e.g., when reasoning mode is disabled or model naturally chatters before outputting JSON).
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """Okay, so I'm trying to analyze this thread. The user provided a thread with a title in Chinese, which translates to something like "Real Capture: This video's first comment." The thread has one reply with two Chinese comments. First, I need to understand the content. The main thread is about a video, and the first comment is in Chinese. The replies are also in Chinese, so I need to figure out what they're saying. Since I'm not fluent in Chinese, I'll have to make some educated guesses based on context or common phrases. I should consider the sentiment of the comments. Are they positive, negative, or neutral? Without knowing the exact meaning, it's tricky, but I can look for common sentiments. For example, if someone is complimenting the video, that's positive. If they're pointing out something wrong, that's negative. Next, I need to determine if this thread is valuable. Valuable could mean it provides useful information, sparks discussions, or helps in understanding a trend. If the comments are constructive or raise important points, it's valuable. If it's just random noise without much context, it might not be. Then, I have to assign value tags. These are categories that describe the content. Common tags might include "Technology," "Social Media," "Video Analysis," etc. I need to see what category this thread falls into. Since it's about a video comment, "Social Media" seems likely, but if the video is about tech, maybe "Technology" as well. The reason for valuing it could be that it highlights issues in video quality, user engagement, or something else relevant. For example, if the comment points out a problem with the video, it might be valuable for quality improvement discussions. I should also consider the structure of the JSON. It needs to have "is_valuable," "value_tags," and "reason." All fields should be strings, and "is_valuable" is a boolean. I need to make sure the JSON is valid and matches the schema provided. Putting it all together, I'll assess the thread's content, determine if it's valuable, assign appropriate tags, and state the reason. I'll make sure to keep the JSON clean and accurate without any markdown formatting. </think> ```json { "is_valuable": "true", "value_tags": ["Social Media", "Video Analysis"], "reason": "The thread discusses a video's first comment, which may provide insights into viewer reactions or content quality, making it valuable for analysis." } ```"""

    with patch('openai.OpenAI') as mock_openai:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create.return_value = mock_response
        
        client = RealOpenAIClient(model_name="deepseek-r1", api_key="test_key", base_url="https://test")
        result = client.generate_structured("test prompt", DummySchema)
        
        assert result.is_valuable == "true"
        assert result.value_tags == ["Social Media", "Video Analysis"]
        assert result.reason == "The thread discusses a video's first comment, which may provide insights into viewer reactions or content quality, making it valuable for analysis."
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