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
        
    def _extract_values_from_schema_hallucination(self, parsed_data: dict, schema: Type[T]) -> dict:
        """
        Extreme fallback: The model hallucinates an entire JSON Schema block with 'title', 'type', 
        and nested values (sometimes inside 'default' or mixed). We recursively hunt for actual data.
        """
        extracted = {}
        for field_name, field_info in schema.model_fields.items():
            if field_name in parsed_data:
                field_val = parsed_data[field_name]
                # If the field value is a schema dict (has 'type' and 'title'), try to extract 'default' or assume it's garbage
                if isinstance(field_val, dict) and "type" in field_val:
                    if "default" in field_val:
                        val = field_val["default"]
                    elif "example" in field_val:
                        val = field_val["example"]
                    else:
                        continue
                else:
                    val = field_val
                
                # Type coercion for common hallucinations (e.g. model output a comma separated string for a list)
                expected_type = str(field_info.annotation)
                if "list" in expected_type.lower() or "List" in expected_type:
                    if isinstance(val, str):
                        val = [s.strip() for s in val.split(",")]
                
                extracted[field_name] = val
        return extracted

    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
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
            
            # Model hallucination fallback: sometimes models wrap the actual data inside a "properties" key
            if isinstance(parsed_data, dict) and "properties" in parsed_data:
                properties_dict = parsed_data["properties"]
                # Try to extract the real values, whether they are direct values or nested inside a schema def
                parsed_data = self._extract_values_from_schema_hallucination(properties_dict, schema)
            elif isinstance(parsed_data, dict):
                # Even without "properties", check if the root dict is hallucinated with "type" and "default"
                parsed_data = self._extract_values_from_schema_hallucination(parsed_data, schema)
            
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
                "value_tags": ["tips", "tutorial"],
                "reason": "Simulated value detection."
            })
            
        elif schema_name == "VideoSummary":
            return schema(**{
                "key_points": ["Point 1", "Point 2"],
                "actionable_insights": "Do this simulated action."
            })
            
        # Fallback
        raise ValueError(f"Unknown schema: {schema_name}")