from abc import ABC, abstractmethod

class ASRProvider(ABC):
    @abstractmethod
    def transcribe(self, video_path: str) -> str:
        pass

class FakeASRProvider(ASRProvider):
    def transcribe(self, video_path: str) -> str:
        return f"[ASR] Simulated transcription for {video_path}: This video talks about great tips."
