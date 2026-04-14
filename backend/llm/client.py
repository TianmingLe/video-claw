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
        # Instead of sending the full JSON Schema which confuses DeepSeek R1 into 
        # generating another JSON Schema, we send a simplified example format.
        
        # Build a simple format string from the Pydantic schema fields
        fields_format = {}
        for field_name, field_info in schema.model_fields.items():
            field_type = str(field_info.annotation).replace("<class '", "").replace("'>", "")
            fields_format[field_name] = f"<{field_type}>"
            
        format_example = json.dumps(fields_format, indent=2)
        
        system_prompt = (
            f"You are a professional data analyst. You MUST respond with ONLY a raw JSON object.\n"
            f"Your output must exactly match this JSON structure:\n"
            f"{format_example}\n\n"
            f"IMPORTANT RULES:\n"
            f"1. DO NOT output a JSON Schema definition (do NOT use 'properties', 'type', or 'required').\n"
            f"2. DO NOT wrap the JSON in markdown code blocks like ```json ... ```. Just output the raw JSON.\n"
            f"3. Fill in the actual analyzed values in place of the type placeholders."
        )
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=4096
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        # 1. First extract everything after </think> if it exists
        if '</think>' in raw_content:
            cleaned_content = raw_content.split('</think>')[-1].strip()
        else:
            cleaned_content = raw_content

        # 2. Extract JSON content from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned_content)
        if json_match:
            cleaned_content = json_match.group(1).strip()
        else:
            # If no code block, try to find the first { and last }
            start_idx = cleaned_content.find('{')
            end_idx = cleaned_content.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                cleaned_content = cleaned_content[start_idx:end_idx+1].strip()
            else:
                # Truncation case: we didn't find a complete pair of braces
                raise RuntimeError(
                    f"Model output was likely truncated due to max_tokens limits. "
                    f"No complete JSON object found in response.\nRaw Response: {raw_content}"
                )
        
        try:
            parsed_data = json.loads(cleaned_content)
            
            # Model hallucination fallback: sometimes models output the schema definition instead of the data object.
            if isinstance(parsed_data, dict) and "properties" in parsed_data and "type" not in parsed_data.get("properties", {}):
                # Only fallback if "properties" looks like it holds actual data rather than type definitions
                if all(not isinstance(v, dict) or "type" not in v for v in parsed_data["properties"].values()):
                    parsed_data = parsed_data["properties"]
            
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