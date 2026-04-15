from pydantic import BaseModel
from typing import List, Dict, Any
from backend.llm.client import LLMClient

class ThreadAnalysis(BaseModel):
    is_valuable: bool
    value_tags: List[str]
    reason: str

class VideoSummary(BaseModel):
    key_points: List[str]
    actionable_insights: str

class LLMAnalyzer:
    def __init__(self, client: LLMClient):
        self.client = client
        
    def analyze_thread(self, root_comment: str, replies: str) -> ThreadAnalysis:
        prompt = f"Analyze this thread: {root_comment} | Replies: {replies}"
        return self.client.generate_structured(prompt, ThreadAnalysis)
        
    def generate_summary(self, video_title: str, asr_text: str, ocr_text: str, valuable_threads: List[Dict[str, Any]]) -> VideoSummary:
        prompt = f"Summarize video '{video_title}'. ASR: {asr_text}. OCR: {ocr_text}. Threads: {len(valuable_threads)}"
        return self.client.generate_structured(prompt, VideoSummary)