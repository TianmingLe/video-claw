from abc import ABC, abstractmethod

class OCRProvider(ABC):
    @abstractmethod
    def extract(self, video_path: str) -> str:
        pass

class FakeOCRProvider(OCRProvider):
    def __init__(self, model: str = None, api_key: str = None):
        self.model = model or "fake-vlm-model"
        self.api_key = api_key
        
    def extract(self, video_path: str) -> str:
        return f"[OCR by {self.model}] Simulated text extracted from {video_path}: Tip 1, Tip 2, Conclusion."
