import json
import re
import time
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Any
from pydantic import BaseModel
import openai

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    @abstractmethod
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """
        使用提示词让大模型按指定 Schema 输出 JSON
        """
        pass
        
    def _regex_fallback_extract(self, raw_content: str, schema: Type[T]) -> dict:
        """
        Ultimate fallback: When json.loads completely fails (due to missing commas,
        unclosed quotes, or trailing garbage), we try to extract the fields directly 
        using regex patterns based on the expected schema.
        """
        extracted = {}
        for field_name, field_info in schema.model_fields.items():
            expected_type = str(field_info.annotation)
            
            # Try to find the field key, e.g., "is_valuable": or 'is_valuable':
            # and capture the value until the next field, comma, or end of brace
            if "bool" in expected_type.lower():
                # Look for true/false (case insensitive)
                match = re.search(rf'"{field_name}"\s*:\s*["\']?(true|false)["\']?', raw_content, re.IGNORECASE)
                if match:
                    extracted[field_name] = match.group(1).lower() == 'true'
                else:
                    extracted[field_name] = False # Safe default
                    
            elif "list" in expected_type.lower() or "List" in expected_type:
                # Look for an array-like structure, optionally wrapped in quotes
                match = re.search(rf'"{field_name}"\s*:\s*["\']?\s*\[(.*?)\]\s*["\']?', raw_content, re.DOTALL)
                if match:
                    inner = match.group(1)
                    # Extract quoted strings from inside the brackets
                    items = re.findall(r'["\'](.*?)["\']', inner)
                    # Filter out empty or whitespace-only items
                    extracted[field_name] = [item for item in items if item.strip()]
                else:
                    # Fallback to capturing a string and splitting by comma
                    match = re.search(rf'"{field_name}"\s*:\s*["\'](.*?)["\']', raw_content)
                    if match:
                        items = [s.strip() for s in match.group(1).split(",")]
                        extracted[field_name] = [item for item in items if item]
                    else:
                        extracted[field_name] = []
                        
            elif "str" in expected_type.lower():
                # Look for a string value
                # Match `"field_name": "value"` or `"field_name": \"value\"`
                # And capture until the next `",` or `"}` or just the end of the file if it's truncated
                match = re.search(rf'"{field_name}"\s*:\s*\\?["\']([\s\S]*?)(?:\\?["\']\s*(?:,|}})|$)', raw_content)
                if match:
                    # Clean up escaped quotes
                    val = match.group(1).replace('\\"', '"').replace('\\n', '\n')
                    extracted[field_name] = val
                else:
                    extracted[field_name] = ""
                    
        return extracted

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

class RealOpenAIClient(LLMClient):
    def __init__(self, model_name: str, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("API Key is required for RealOpenAIClient")
        self.model_name = model_name
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        
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
        
        max_retries = 3
        last_exception = None
        response = None
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=4096
                )
                break
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
                
        if not response:
            raise RuntimeError(f"LLM API completely failed after {max_retries} attempts. Last Error: {str(last_exception)}")
        
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
                
        # Fix common JSON syntax errors caused by hallucinations before parsing
        # 1. Handle arrays wrapped in quotes with escaped inner quotes
        # Example: `"[\"A\", \"B\"]"` -> `["A", "B"]`
        def fix_array_string(match):
            inner = match.group(1)
            # Remove all backslashes that escape quotes
            inner = inner.replace('\\"', '"')
            # Remove any stray double quotes that were surrounding the list
            return f"[{inner}]"

        # Match literally `"[... ]"` with anything inside, allowing for spaces
        cleaned_content = re.sub(r'"\s*\[(.*?)\]\s*"', fix_array_string, cleaned_content)
        
        # Sometimes the regex above leaves things like `[""A"", "B"]`
        # We can clean up double-double quotes inside lists to single double quotes
        cleaned_content = cleaned_content.replace('""', '"')

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
        except (json.JSONDecodeError, Exception):
            # ULTIMATE FALLBACK: If standard parsing or Pydantic validation fails, 
            # use regex to rip values out of the text directly.
            try:
                parsed_data = self._regex_fallback_extract(cleaned_content, schema)
                return schema(**parsed_data)
            except Exception as final_e:
                raise RuntimeError(
                    f"Failed to parse LLM response even with regex fallback.\n"
                    f"Error: {str(final_e)}\n"
                    f"Raw Content: {raw_content}"
                )

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