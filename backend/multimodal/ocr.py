from abc import ABC, abstractmethod

class OCRProvider(ABC):
    @abstractmethod
    def extract(self, video_path: str) -> str:
        pass

class FakeOCRProvider(OCRProvider):
    def extract(self, video_path: str) -> str:
        return f"[OCR] Simulated text extracted from {video_path}: Tip 1, Tip 2, Conclusion."
