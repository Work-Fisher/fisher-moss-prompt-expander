"""Build the complete Markdown and portable ZIP from this skill directory."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


def anchor(path):
    return "file-" + hashlib.sha256(path.as_posix().encode()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = Path(args.output_dir).resolve()
    if output == root or root in output.parents:
        raise ValueError("Output directory must be outside the skill directory")
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    metrics = {}
    for path in sorted((root / "examples").glob("full-*.md")):
        body = re.search(r"```text\n(.*?)```", path.read_text("utf-8"), re.S)
        if not body:
            raise ValueError(f"Missing prompt block: {path.name}")
        count = len(re.findall(r"[\u4e00-\u9fff]", body.group(1)))
        if not 1500 <= count <= 2500:
            raise ValueError(f"Full example length: {path.name}: {count}")
        metrics[path.name] = count
    if len(metrics) != 6:
        raise ValueError("Expected six complete examples")
    parts = ["# fisher-moss-prompt-expander 完整版", "由技能目录统一导出。包含规则、完整案例、局部模块、验收记录、参考素材名称与导出脚本；本文档不嵌入图片。"]
    ordered = sorted(files, key=lambda p: (p.name != "SKILL.md", p.relative_to(root).as_posix()))
    for path in ordered:
        relative = path.relative_to(root)
        parts.append(f'<a id="{anchor(relative)}"></a>\n\n## {relative.as_posix()}')
        if path.suffix.lower() in (".jpg", ".png"):
            parts.append("参考素材：仅记录文件名，图片不嵌入本文档。")
            continue
        content = path.read_text("utf-8")
        if path.suffix == ".md":
            if len(re.findall(r"^```", content, re.M)) % 2:
                raise ValueError(f"Unbalanced fences: {relative}")
            def rewrite(match):
                label, target = match.group(1), match.group(2)
                if target.startswith(("http:", "https:", "#", "data:")):
                    return match.group(0)
                destination = (path.parent / target.split("#")[0]).resolve()
                if not destination.is_file() or root not in destination.parents:
                    raise ValueError(f"Invalid local link in {relative}: {target}")
                return f"[{label}](#{anchor(destination.relative_to(root))})"
            content = re.sub(r"!?\[([^\]]*)\]\(([^)]+)\)", rewrite, content)
            if content.startswith("---\n"):
                closing = content.find("\n---", 4)
                if closing >= 0:
                    content = "```yaml\n" + content[4:closing] + "\n```" + content[closing+4:]
            inside = False
            lines = []
            for line in content.splitlines():
                if line.startswith("```"):
                    inside = not inside
                if not inside and line.startswith("#"):
                    line = "##" + line
                lines.append(line)
            parts.append("\n".join(lines))
        else:
            language = "python" if path.suffix == ".py" else "yaml"
            parts.append(f"````{language}\n{content}\n````")
    document = "\n\n".join(parts) + "\n"
    (output / "fisher-moss-prompt-expander-完整版.md").write_text(document, encoding="utf-8")
    archive_path = output / "fisher-moss-prompt-expander.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path(root.name) / path.relative_to(root))
    with zipfile.ZipFile(archive_path) as archive:
        for path in files:
            name = (Path(root.name) / path.relative_to(root)).as_posix()
            if archive.read(name) != path.read_bytes():
                raise ValueError(f"Archive mismatch: {name}")
    report = {"full_examples_han_characters": metrics, "source_files": len(files), "sha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (output / "fisher-moss-prompt-expander-build.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(files), "examples": metrics, "archive_verified": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
