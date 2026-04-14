import json
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Any
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    @abstractmethod
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        pass

class FakeLLMClient(LLMClient):
    def __init__(self, model_name: str = "fake-gpt-4o-mini", api_key: str = None):
        self.model_name = model_name or "fake-gpt-4o-mini"
        self.api_key = api_key
        
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