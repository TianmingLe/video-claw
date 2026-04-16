import json
import os
from sqlalchemy.orm import Session
from backend.multimodal.asr import FakeASRProvider
from backend.multimodal.ocr import FakeOCRProvider
from backend.llm.client import FakeLLMClient, RealOpenAIClient
from backend.llm.analyzer import LLMAnalyzer
from backend.llm.exporter import MarkdownExporter
from backend.database.models import Video, Thread, Summary

class AnalysisPipeline:
    def __init__(self, db_session: Session, config: dict = None):
        self.db = db_session
        self.config = config or {}
        self.run_id = self.config.get("run_id")
        
        self.asr_provider = FakeASRProvider()
        self.ocr_provider = FakeOCRProvider(
            model=self.config.get("vlm_model"), 
            api_key=self.config.get("vlm_api_key"),
            base_url=self.config.get("vlm_base_url")
        )
        
        # 智能路由：如果有真实 api key 则走 OpenAIClient
        api_key = self.config.get("llm_api_key")
        if api_key:
            self.llm_client = RealOpenAIClient(
                model_name=self.config.get("llm_model", "gpt-4o-mini"),
                api_key=api_key,
                base_url=self.config.get("llm_base_url", "https://api.openai.com/v1")
            )
        else:
            self.llm_client = FakeLLMClient(
                model_name=self.config.get("llm_model", "fake-gpt-4o-mini"),
                api_key=api_key,
                base_url=self.config.get("llm_base_url")
            )
            
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
        if self.run_id is not None:
            threads = self.db.query(Thread).filter_by(video_id=video_id, run_id=self.run_id).all()
        else:
            threads = self.db.query(Thread).filter_by(video_id=video_id).all()
        valuable_threads_data = []
        for t in threads:
            try:
                analysis = self.analyzer.analyze_thread(t.root_comment, t.replies_json)
                t.is_valuable = analysis.is_valuable
                t.value_tags = json.dumps(analysis.value_tags, ensure_ascii=False) if isinstance(analysis.value_tags, list) else analysis.value_tags
                t.reason = analysis.reason
                
                if t.is_valuable:
                    valuable_threads_data.append({
                        "root": t.root_comment,
                        "tags": t.value_tags
                    })
            except Exception as e:
                # 如果单个评论分析失败（即便有兜底机制也挂了），记录日志并将其标记为无价值，防止阻断后续流程
                print(f"[WARN] Failed to analyze thread {t.id}: {str(e)}")
                t.is_valuable = False
                t.value_tags = "[]"
                t.reason = f"Analysis failed: {str(e)}"
                
        self.db.commit()

        # 4. 生成总结
        try:
            summary_obj = self.analyzer.generate_summary(
                video_title=video.title,
                asr_text=video.asr_text,
                ocr_text=video.ocr_text,
                valuable_threads=valuable_threads_data
            )
            key_points = summary_obj.key_points
            actionable_insights = summary_obj.actionable_insights
        except Exception as e:
            print(f"[WARN] Failed to generate overall summary: {str(e)}")
            key_points = ["Summary generation failed due to API or parsing error."]
            actionable_insights = str(e)
            
        if self.run_id is not None:
            db_summary = self.db.query(Summary).filter_by(video_id=video_id, run_id=self.run_id).first()
        else:
            db_summary = self.db.query(Summary).filter_by(video_id=video_id).first()
        if not db_summary:
            db_summary = Summary(video_id=video_id, run_id=self.run_id)
            self.db.add(db_summary)
            
        db_summary.key_points_json = json.dumps(key_points)
        db_summary.actionable_insights = actionable_insights
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
