"""
Reflection Tracer - 审计追踪系统（对齐report.md模板）

记录所有反思报告需要的关键事件：
- 初始诊断（2.1节表格）
- 迭代记录（3.4节12轮表格）
- 失败案例（3.1节）
- 拒绝AI建议（3.3节）
- 转折点事件（4.1节）
- 证据组（4.2节）
- 评分事件（使用review模式）
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ReflectionTracer:
    """记录所有反思报告需要的事件"""

    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir)
        self.audit_dir = self.work_dir / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.trace_file = self.audit_dir / "reflection_trace.jsonl"
        self.logger = logging.getLogger(__name__)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """记录事件到JSONL"""
        event = {"timestamp": datetime.now().isoformat(), "type": event_type, **data}

        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        self.logger.debug(f"[ReflectionTrace] {event_type}")

    def log_initial_diagnosis(self, dimension_scores: Dict[str, Dict[str, Any]]):
        """记录初始诊断结果（2.1节表格）"""
        self.log_event(
            "initial_diagnosis",
            {
                "dimension_scores": dimension_scores,
                "summary": f"Initial review: {len(dimension_scores)} dimensions scored",
            },
        )

    def log_iteration_round(
        self,
        round_num: int,
        iteration: int,
        pass_id: int,
        focused_dimension: str,
        question_strategy: str,
        ai_contribution: str,
        human_judgment: str,
        result_score: Optional[float] = None,
        result_feedback: Optional[str] = None,
    ):
        """记录一轮迭代（3.4节表格的一行）"""
        self.log_event(
            "iteration_round",
            {
                "round": round_num,
                "iter": iteration,
                "pass": pass_id,
                "focused_dimension": focused_dimension,
                "question_strategy": question_strategy,
                "ai_contribution": ai_contribution,
                "human_judgment": human_judgment,
                "result_score": result_score,
                "result_feedback": result_feedback,
            },
        )

    def log_failure_case(
        self, iteration: int, case_type: str, description: str, lesson_learned: str
    ):
        """记录失败案例（3.1节）"""
        self.log_event(
            "failure_case",
            {
                "iter": iteration,
                "case_type": case_type,
                "description": description,
                "lesson_learned": lesson_learned,
            },
        )

    def log_ai_rejection(
        self,
        iteration: int,
        pass_id: int,
        issue_id: str,
        ai_suggestion: str,
        rejection_type: str,
        your_modification: str,
        reason: str,
    ):
        """记录拒绝/修正AI建议的案例（B2高分关键）"""
        self.log_event(
            "ai_rejection",
            {
                "iter": iteration,
                "pass": pass_id,
                "issue_id": issue_id,
                "ai_suggestion": ai_suggestion,
                "rejection_type": rejection_type,
                "your_modification": your_modification,
                "reason": reason,
            },
        )

    def log_turning_point(
        self,
        iteration: int,
        trigger_action: str,
        before_feeling: str,
        after_feeling: str,
        dimension_impact: List[str],
    ):
        """记录质变分水岭（4.1节）"""
        self.log_event(
            "turning_point",
            {
                "iter": iteration,
                "trigger_action": trigger_action,
                "before_feeling": before_feeling,
                "after_feeling": after_feeling,
                "dimension_impact": dimension_impact,
            },
        )

    def log_evidence_group(
        self,
        group_id: int,
        target_dimension: str,
        before_text: str,
        ai_suggestion_summary: str,
        after_text: str,
        improvement_explanation: str,
    ):
        """记录一组修改前后对比证据（4.2节）"""
        self.log_event(
            "evidence_group",
            {
                "group_id": group_id,
                "target_dimension": target_dimension,
                "before_text": before_text,
                "ai_suggestion_summary": ai_suggestion_summary,
                "after_text": after_text,
                "improvement_explanation": improvement_explanation,
            },
        )

    def log_scoring_from_review(
        self,
        iteration: int,
        pass_id: int,
        report_path: str,
        scores: Dict[str, float],
        total_score: float,
        feedback: str,
    ):
        """记录从review模式获取的评分（只上传文档，无prompt）"""
        self.log_event(
            "scoring_review",
            {
                "iter": iteration,
                "pass": pass_id,
                "report_path": report_path,
                "scores": scores,
                "total_score": total_score,
                "feedback": feedback,
                "note": "Scored by review mode (upload-only, no prompt)",
            },
        )

    def log_final_assessment(
        self,
        scores: Dict[str, float],
        total: float,
        strongest_2: List[str],
        weakest_2: List[str],
        reusable_protocol: str,
    ):
        """记录AI助手最终评语（文末）"""
        self.log_event(
            "final_assessment",
            {
                "scores": scores,
                "total": total,
                "strongest_2": strongest_2,
                "weakest_2": weakest_2,
                "reusable_protocol": reusable_protocol,
            },
        )

    def log_patch_applied(
        self,
        iteration: int,
        pass_id: int,
        issue_id: str,
        applied: bool,
        match_mode: str,
    ):
        """记录patch应用结果"""
        self.log_event(
            "patch_applied",
            {
                "iter": iteration,
                "pass": pass_id,
                "issue_id": issue_id,
                "applied": applied,
                "match_mode": match_mode,
            },
        )

    def read_all_events(self) -> List[Dict[str, Any]]:
        """读取所有事件"""
        if not self.trace_file.exists():
            return []

        events = []
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return events

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """按类型筛选事件"""
        return [e for e in self.read_all_events() if e.get("type") == event_type]
