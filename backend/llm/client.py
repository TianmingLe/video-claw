import json
import re
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Any
from pydantic import BaseModel
import openai

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    @abstractmethod
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        pass

class RealOpenAIClient(LLMClient):
    def __init__(self, model_name: str, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("API Key is required for RealOpenAIClient")
        self.model_name = model_name
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        system_prompt = f"You are a professional data analyst. You MUST respond with ONLY valid JSON that matches the following schema:\n{schema.schema_json()}\nDo not wrap the JSON in markdown code blocks."
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        # Clean markdown code blocks if the model still outputs them
        cleaned_content = re.sub(r'^```json\s*', '', raw_content)
        cleaned_content = re.sub(r'^```\s*', '', cleaned_content)
        cleaned_content = re.sub(r'\s*```$', '', cleaned_content)
        
        try:
            parsed_data = json.loads(cleaned_content)
            return schema(**parsed_data)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse LLM JSON response: {str(e)}\nRaw Response: {raw_content}")

class FakeLLMClient(LLMClient):
    def __init__(self, model_name: str = "fake-gpt-4o-mini", api_key: str = None, base_url: str = None):
        self.model_name = model_name or "fake-gpt-4o-mini"
        self.api_key = api_key
        self.base_url = base_url
        
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """根据 schema 类名返回硬编码的模拟数据"""
        schema_name = schema.__name__
        
        if schema_name == "ThreadAnalysis":
            return schema(**{
                "is_valuable": True,
                "value_tags": "tips, tutorial",
                "reason": "Simulated value detection."
            })
            
        elif schema_name == "VideoSummary":
            return schema(**{
                "key_points": ["Point 1", "Point 2"],
                "actionable_insights": "Do this simulated action."
            })
            
        # Fallback
        raise ValueError(f"Unknown schema: {schema_name}")