"""
提交文件打包工具
自动收集: 综述PDF、查重报告、AICG报告、反思报告 → 打包成zip
"""

import argparse
import zipfile
from pathlib import Path


def package_submission(
    paper_pdf: Path,
    plagiarism_pdf: Path,
    aicg_pdf: Path,
    reflection_docx: Path,
    output_zip: Path,
    student_info: str = "专业-姓名-学号",
):
    required_files = [paper_pdf, plagiarism_pdf, aicg_pdf, reflection_docx]
    missing_files = [f for f in required_files if not f.exists()]

    if missing_files:
        print("❌ 缺少以下文件:")
        for f in missing_files:
            print(f"  - {f}")
        return False

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(paper_pdf, arcname=f"{student_info}_综述.pdf")
        zf.write(plagiarism_pdf, arcname=f"{student_info}_查重报告.pdf")
        zf.write(aicg_pdf, arcname=f"{student_info}_AICG报告.pdf")
        zf.write(reflection_docx, arcname=f"{student_info}_反思报告.docx")

    print(f"✅ 提交包已生成: {output_zip}")
    print(f"📦 包含文件:")
    print(f"  1. {paper_pdf.name}")
    print(f"  2. {plagiarism_pdf.name}")
    print(f"  3. {aicg_pdf.name}")
    print(f"  4. {reflection_docx.name}")

    return True


def main():
    parser = argparse.ArgumentParser(description="打包提交文件")
    parser.add_argument("--paper", required=True, help="综述PDF路径")
    parser.add_argument("--plagiarism", required=True, help="查重报告PDF路径")
    parser.add_argument("--aicg", required=True, help="AICG报告PDF路径")
    parser.add_argument("--reflection", required=True, help="反思报告docx路径")
    parser.add_argument(
        "--output", "-o", default="submission.zip", help="输出zip文件路径"
    )
    parser.add_argument("--info", default="专业-姓名-学号", help="学生信息")

    args = parser.parse_args()

    package_submission(
        paper_pdf=Path(args.paper),
        plagiarism_pdf=Path(args.plagiarism),
        aicg_pdf=Path(args.aicg),
        reflection_docx=Path(args.reflection),
        output_zip=Path(args.output),
        student_info=args.info,
    )


if __name__ == "__main__":
    main()
