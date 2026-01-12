"""
反思报告生成工具（严格对齐 report.md 模板）
从 reflection_trace.jsonl 自动填充报告内容
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class ReflectionReportGenerator:
    def __init__(self, workspace_dir: Path):
        self.workspace = Path(workspace_dir)
        self.trace_file = self.workspace / "audit" / "reflection_trace.jsonl"
        self.issues_file = self.workspace / "issues.json"
        self.template_path = Path(__file__).parent.parent / "report.md"

    def load_events(self) -> List[Dict[str, Any]]:
        if not self.trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {self.trace_file}")

        events = []
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return events

    def load_issues(self) -> List[Dict[str, Any]]:
        if not self.issues_file.exists():
            return []

        with open(self.issues_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("issues", [])

    def load_template(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        with open(self.template_path, "r", encoding="utf-8") as f:
            return f.read()

    def generate_report(self, output_path: Path, student_info: Dict[str, str]):
        events = self.load_events()
        issues = self.load_issues()
        template = self.load_template()

        report = template

        report = report.replace("[填写]", student_info.get("name", "[待填写]"))
        report = report.replace("[填写]", student_info.get("student_id", "[待填写]"), 1)
        report = report.replace("[填写]", student_info.get("major", "[待填写]"), 1)
        report = report.replace(
            "[填写：你的综述题目]", student_info.get("title", "[待填写]")
        )
        report = report.replace("[日期]", datetime.now().strftime("%Y-%m-%d"))

        initial_diagnosis = [e for e in events if e.get("type") == "initial_diagnosis"]
        if initial_diagnosis:
            table_rows = self._generate_diagnosis_table(initial_diagnosis[0])
            report = self._replace_diagnosis_table(report, table_rows)

        iteration_rounds = [e for e in events if e.get("type") == "iteration_round"]
        if iteration_rounds:
            iteration_table = self._generate_iteration_table(iteration_rounds)
            report = self._replace_iteration_table(report, iteration_table)

        failure_cases = [e for e in events if e.get("type") == "failure_case"]
        if failure_cases:
            failure_text = self._generate_failure_cases(failure_cases)
            report = self._insert_after_marker(
                report, "3.1 失败案例（必须有，越真实越加分）", failure_text
            )

        rejection_cases = [e for e in events if e.get("type") == "ai_rejection"]
        if rejection_cases:
            rejection_text = self._generate_rejection_cases(rejection_cases)
            report = self._insert_after_marker(
                report,
                "3.3 批判性采纳：我如何拒绝/修正AI建议（B2高分关键）",
                rejection_text,
            )

        evidence_groups = [e for e in events if e.get("type") == "evidence_group"]
        if evidence_groups:
            evidence_text = self._generate_evidence_groups(evidence_groups)
            report = self._insert_after_marker(
                report,
                "4.2 修改前后对比证据（至少3组；每组都要绑定评分维度）",
                evidence_text,
            )

        scoring_events = [e for e in events if e.get("type") == "scoring_review"]
        if scoring_events:
            scoring_text = self._generate_scoring_appendix(scoring_events)
            report = report.replace("【粘贴评分截图/表格/记录】", scoring_text)

        final_assessment = [e for e in events if e.get("type") == "final_assessment"]
        if final_assessment:
            assessment_text = self._generate_final_assessment(final_assessment[0])
            report = self._replace_final_assessment(report, assessment_text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"✅ 反思报告已生成: {output_path}")
        print(f"📊 包含事件: {len(events)} 条")

    def _generate_diagnosis_table(self, diagnosis_event: Dict) -> List[str]:
        dimension_scores = diagnosis_event.get("dimension_scores", {})
        rows = []

        for dim, data in sorted(dimension_scores.items()):
            row_data = {
                "dim": dim,
                "score": data.get("score", 0),
                "max": data.get("max", 0),
                "keywords": data.get("keywords", ""),
            }
            rows.append(row_data)

        return rows

    def _replace_diagnosis_table(self, report: str, table_rows: List[Dict]) -> str:
        lines = report.split("\n")
        new_lines = []
        table_row_index = 0

        for line in lines:
            if "[A3/B2/B3/C1…]" in line and table_row_index < len(table_rows):
                row = table_rows[table_row_index]
                new_line = line.replace("[A3/B2/B3/C1…]", row["dim"])
                new_line = new_line.replace("[ ]", str(row["score"]), 1)
                new_line = new_line.replace("[ ]", str(row["max"]), 1)
                new_line = new_line.replace(
                    "[例如：GAP模糊/结构像列表/缺乏框架/批判性弱]", row["keywords"]
                )
                new_lines.append(new_line)
                table_row_index += 1
            else:
                new_lines.append(line)

        return "\n".join(new_lines)

    def _generate_iteration_table(self, rounds: List[Dict]) -> List[Dict]:
        rows = []

        for round_event in rounds[:12]:
            row = {
                "round": f"{round_event.get('round', 1)}-{round_event.get('round', 1) + 2}",
                "dimension": round_event.get("focused_dimension", ""),
                "strategy": round_event.get("question_strategy", ""),
                "ai": round_event.get("ai_contribution", ""),
                "judgment": round_event.get("human_judgment", ""),
                "result": round_event.get("result_score", 0),
            }
            rows.append(row)

        return rows

    def _replace_iteration_table(self, report: str, table_rows: List[Dict]) -> str:
        lines = report.split("\n")
        new_lines = []
        table_row_index = 0

        for line in lines:
            if "[1-3/4-6…]" in line and table_row_index < len(table_rows):
                row = table_rows[table_row_index]
                new_line = line.replace("[1-3/4-6…]", row["round"])
                new_line = new_line.replace("[B3/A3/C1…]", row["dimension"])
                new_line = new_line.replace("[动作化/多方案/追问…]", row["strategy"])
                new_line = new_line.replace("[给出框架/清单…]", row["ai"])
                new_line = new_line.replace("[拒绝/改写/补证…]", row["judgment"])
                new_line = new_line.replace("[62→65→…]", str(row["result"]))
                new_lines.append(new_line)
                table_row_index += 1
            else:
                new_lines.append(line)

        return "\n".join(new_lines)

    def _generate_failure_cases(self, cases: List[Dict]) -> str:
        text_lines = []
        for i, case in enumerate(cases[:2], 1):
            text_lines.append(f"失败案例{i}：{case.get('description', '')}")
            text_lines.append(f"教训：{case.get('lesson_learned', '')}\n")

        return "\n".join(text_lines)

    def _generate_rejection_cases(self, cases: List[Dict]) -> str:
        text_lines = []
        for i, case in enumerate(cases[:2], 1):
            case_type = (
                "学术主张"
                if case.get("rejection_type") == "academic_claim"
                else "概念框架"
            )
            text_lines.append(f"\n案例{chr(64 + i)}（{case_type}）：")
            text_lines.append(f"AI建议：{case.get('ai_suggestion', '')}")
            text_lines.append(f"我的修正：{case.get('your_modification', '')}")
            text_lines.append(f"理由：{case.get('reason', '')}\n")

        return "\n".join(text_lines)

    def _generate_evidence_groups(self, groups: List[Dict]) -> str:
        text_lines = []

        for group in groups[:3]:
            gid = group.get("group_id", 1)
            text_lines.append(
                f"\n【证据组#{gid}】（{group.get('target_dimension', '')}）"
            )
            text_lines.append(f"Before：{group.get('before_text', '')}")
            text_lines.append(f"AI建议要点：{group.get('ai_suggestion_summary', '')}")
            text_lines.append(f"After：{group.get('after_text', '')}")
            text_lines.append(f"维度解释：{group.get('improvement_explanation', '')}\n")

        return "\n".join(text_lines)

    def _generate_scoring_appendix(self, scoring_events: List[Dict]) -> str:
        lines = []
        for event in scoring_events:
            lines.append(
                f"\n## 轮次 {event.get('iter', 0)} - Pass {event.get('pass', 0)}"
            )
            scores = event.get("scores", {})
            for dim, score in sorted(scores.items()):
                lines.append(f"- {dim}: {score}")
            lines.append(f"- 总分: {event.get('total_score', 0)}")
            lines.append(f"- 反馈: {event.get('feedback', '')}\n")

        return "\n".join(lines)

    def _generate_final_assessment(self, assessment: Dict) -> str:
        scores = assessment.get("scores", {})
        total = assessment.get("total", 0)
        strongest = assessment.get("strongest_2", [])
        weakest = assessment.get("weakest_2", [])

        text = f"""【A–E 得分】A：{scores.get("A", 0)}/15；B：{scores.get("B", 0)}/25；C：{scores.get("C", 0)}/25；D：{scores.get("D", 0)}/20；E：{scores.get("E", 0)}/15；总分：{total}/100。
【最强2点】1) {strongest[0] if len(strongest) > 0 else ""} 2) {strongest[1] if len(strongest) > 1 else ""}
【最该补2点】1) {weakest[0] if len(weakest) > 0 else ""} 2) {weakest[1] if len(weakest) > 1 else ""}
【下次复用流程】{assessment.get("reusable_protocol", "TPAMI-Ready Reflow Protocol")}
"""
        return text

    def _replace_final_assessment(self, report: str, assessment_text: str) -> str:
        marker = "【A–E 得分】"
        pos = report.find(marker)
        if pos != -1:
            end_marker = "【下次复用流程】"
            end_pos = report.find(end_marker, pos)
            if end_pos != -1:
                end_pos = report.find("\n", end_pos + 100)
                if end_pos != -1:
                    report = report[:pos] + assessment_text + report[end_pos:]

        return report

    def _insert_after_marker(self, report: str, marker: str, content: str) -> str:
        pos = report.find(marker)
        if pos != -1:
            insert_pos = report.find("\n", pos) + 1
            report = report[:insert_pos] + content + "\n" + report[insert_pos:]

        return report


def main():
    parser = argparse.ArgumentParser(description="生成反思报告")
    parser.add_argument("workspace", help="工作空间目录")
    parser.add_argument("--output", "-o", default="reflection_report_generated.md")
    parser.add_argument("--name", default="张三", help="姓名")
    parser.add_argument("--id", default="2021001", help="学号")
    parser.add_argument("--major", default="计算机科学", help="专业")
    parser.add_argument("--title", default="", help="综述题目")

    args = parser.parse_args()

    student_info = {
        "name": args.name,
        "student_id": args.id,
        "major": args.major,
        "title": args.title,
    }

    generator = ReflectionReportGenerator(args.workspace)
    generator.generate_report(Path(args.output), student_info)


if __name__ == "__main__":
    main()
