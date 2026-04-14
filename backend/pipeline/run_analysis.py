import json
from sqlalchemy.orm import Session
from backend.database.models import Video, Thread, Summary
from backend.multimodal.asr import FakeASRProvider
from backend.multimodal.ocr import FakeOCRProvider
from backend.llm.client import FakeLLMClient
from backend.llm.analyzer import LLMAnalyzer
from backend.llm.exporter import MarkdownExporter

class AnalysisPipeline:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.asr_provider = FakeASRProvider()
        self.ocr_provider = FakeOCRProvider()
        self.llm_client = FakeLLMClient()
        self.analyzer = LLMAnalyzer(self.llm_client)
        self.exporter = MarkdownExporter()

    def run_for_video(self, video_id: str, local_video_path: str = "dummy.mp4"):
        # 1. 查询视频
        video = self.db.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found in DB")

        # 2. 多模态提取
        video.asr_text = self.asr_provider.transcribe(local_video_path)
        video.ocr_text = self.ocr_provider.extract(local_video_path)
        self.db.commit()

        # 3. 分析线程价值
        threads = self.db.query(Thread).filter_by(video_id=video_id).all()
        valuable_threads_data = []
        for t in threads:
            analysis = self.analyzer.analyze_thread(t.root_comment, t.replies_json)
            t.is_valuable = analysis.is_valuable
            t.value_tags = analysis.value_tags
            
            if t.is_valuable:
                valuable_threads_data.append({
                    "root": t.root_comment,
                    "tags": t.value_tags
                })
        self.db.commit()

        # 4. 生成总结
        summary_obj = self.analyzer.generate_summary(
            video_title=video.title,
            asr_text=video.asr_text,
            ocr_text=video.ocr_text,
            valuable_threads=valuable_threads_data
        )
        
        db_summary = self.db.query(Summary).filter_by(video_id=video_id).first()
        if not db_summary:
            db_summary = Summary(video_id=video_id)
            self.db.add(db_summary)
            
        db_summary.key_points_json = json.dumps(summary_obj.key_points)
        db_summary.actionable_insights = summary_obj.actionable_insights
        db_summary.model_name = self.llm_client.model_name
        self.db.commit()

        try:
            # 5. 生成并保存 Markdown 报告
            report_md = self.exporter.generate_report(video, threads, db_summary)
            db_summary.report_markdown = report_md
            self.db.commit()
            return report_md
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"Pipeline failed to generate or save report: {str(e)}")