"""
ScorerAgent - 使用 review 配置进行评分
关键：只上传文档，不发送任何文字（评分规则已内置在review模式中）
"""

import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path
from paper_api.client import YuketangAIClient
from paper_api.config import load_cookies, load_session_params, load_conversation_id


class ScorerAgent:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        try:
            cookies = load_cookies("config/cookies.json")
            params = load_session_params("config/session_params_review.json")
            conversation_id = load_conversation_id(
                "config/conversation_config_review.json"
            )
        except FileNotFoundError as e:
            self.logger.error(f"Review配置文件未找到: {e}")
            raise

        self.client = YuketangAIClient(
            cookies, params, conversation_id=conversation_id, logger=self.logger.info
        )

    def score_reflection_report(
        self, report_path: str, reset_conversation: bool = True
    ) -> Dict[str, Any]:
        if reset_conversation:
            self.logger.info("重置review对话...")
            try:
                self.client.create_new_conversation()
            except Exception as e:
                self.logger.warning(f"重置对话失败: {e}")

        txt_path = self._prepare_file_for_upload(report_path)
        if not txt_path:
            return {}

        self.logger.info(f"上传反思报告进行评分（不发送prompt）: {txt_path}")

        response = self.client.send_message_with_file(
            message="", file_path=txt_path, stream=True
        )

        if txt_path != report_path:
            try:
                os.remove(txt_path)
            except OSError:
                pass

        if not response:
            self.logger.error("评分请求失败")
            return {}

        return self._parse_scoring_response(response)

    def _prepare_file_for_upload(self, file_path: str) -> Optional[str]:
        try:
            if file_path.endswith(".txt"):
                return file_path

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            txt_path = file_path.rsplit(".", 1)[0] + "_for_scoring.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)

            return txt_path
        except Exception as e:
            self.logger.error(f"文件准备失败: {e}")
            return None

    def _parse_scoring_response(self, response: str) -> Dict[str, Any]:
        import json
        import re

        result = {
            "A": 0,
            "B": 0,
            "C": 0,
            "D": 0,
            "E": 0,
            "total": 0,
            "feedback": "",
            "raw_response": response,
        }

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = response[start:end]
                data = json.loads(json_str)

                if "scores" in data:
                    scores = data["scores"]
                    result.update(
                        {
                            "A": scores.get("A", 0),
                            "B": scores.get("B", 0),
                            "C": scores.get("C", 0),
                            "D": scores.get("D", 0),
                            "E": scores.get("E", 0),
                            "total": data.get("overall", 0) or data.get("total", 0),
                            "feedback": data.get("feedback", ""),
                        }
                    )
                    return result
        except Exception:
            pass

        try:
            for dimension in ["A", "B", "C", "D", "E"]:
                pattern = rf"{dimension}[：:]\s*(\d+(?:\.\d+)?)\s*/\s*\d+"
                match = re.search(pattern, response)
                if match:
                    result[dimension] = float(match.group(1))

            total_pattern = r"总分[：:]\s*(\d+(?:\.\d+)?)\s*/\s*\d+"
            total_match = re.search(total_pattern, response)
            if total_match:
                result["total"] = float(total_match.group(1))
            else:
                result["total"] = sum(
                    [result["A"], result["B"], result["C"], result["D"], result["E"]]
                )

            if total_match:
                feedback_start = total_match.end()
                result["feedback"] = response[feedback_start:].strip()
            else:
                result["feedback"] = response.strip()

        except Exception as e:
            self.logger.error(f"解析评分结果失败: {e}")
            result["feedback"] = response

        return result


def score_final_report(
    report_path: str, output_json: Optional[str] = None
) -> Dict[str, Any]:
    scorer = ScorerAgent()
    result = scorer.score_reflection_report(report_path)

    print("\n" + "=" * 60)
    print("反思报告评分结果")
    print("=" * 60)
    print(f"A（定位与路线图）: {result['A']}/15")
    print(f"B（交互质量）: {result['B']}/25")
    print(f"C（证据与效果）: {result['C']}/25")
    print(f"D（方法迁移）: {result['D']}/20")
    print(f"E（反思深度与表达）: {result['E']}/15")
    print(f"\n总分: {result['total']}/100")
    print("\n反馈:")
    print(result.get("feedback", ""))
    print("=" * 60)

    if output_json:
        import json

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n✅ 评分结果已保存: {output_json}")

    return result
