import json

class MarkdownExporter:
    @staticmethod
    def generate_report(video, threads, summary) -> str:
        """
        根据 ORM 对象或字典构建 Markdown 报告。
        """
        title = video.title if hasattr(video, 'title') else video.get('title', 'Unknown Video')
        url = video.url if hasattr(video, 'url') else video.get('url', '#')
        
        md_lines = []
        md_lines.append(f"# Video Analysis Report: {title}")
        md_lines.append(f"**URL:** {url}")
        md_lines.append("\n## 1. Key Points")
        
        # 尝试解析 summary 的 key_points_json
        key_points = []
        kp_json = summary.key_points_json if hasattr(summary, 'key_points_json') else summary.get('key_points_json', '[]')
        try:
            key_points = json.loads(kp_json)
        except:
            key_points = [kp_json]
            
        for pt in key_points:
            md_lines.append(f"- {pt}")
            
        md_lines.append("\n## 2. Actionable Insights")
        insights = summary.actionable_insights if hasattr(summary, 'actionable_insights') else summary.get('actionable_insights', '')
        md_lines.append(insights or "None")
        
        md_lines.append("\n## 3. Valuable Conversations")
        valuable_threads = [t for t in threads if (getattr(t, 'is_valuable', False) or t.get('is_valuable') is True)]
        
        if not valuable_threads:
            md_lines.append("No valuable conversations found.")
        else:
            for i, t in enumerate(valuable_threads):
                tags = getattr(t, 'value_tags', '') or t.get('value_tags', '')
                root = getattr(t, 'root_comment', '') or t.get('root_comment', '')
                md_lines.append(f"### Thread {i+1} [Tags: {tags}]")
                md_lines.append(f"> {root}")
                md_lines.append("")
                
        return "\n".join(md_lines)