#!/usr/bin/env python3
"""Read complete opening-method entries from the bundled Wiki snapshot."""

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "references" / "wiki-opening-hook.md"
MANIFEST = ROOT / "references" / "source-manifest.json"
NOTICE = (
    "以下为 Wiki 教学资料原文。例句中的事实属于原案例，不可移植成当前稿件事实。\n"
    "流程以当前用户要求、creation_teacher 和 SKILL.md 为准；原文的情境建议须判断适用。\n"
)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entries(text):
    result = {}
    for match in re.finditer(r"^#### (\d+)\. ([^\n]+)\n", text, re.M):
        next_heading = re.search(r"^#{2,4} ", text[match.end():], re.M)
        end = match.end() + next_heading.start() if next_heading else len(text)
        number = int(match.group(1))
        if number in result:
            raise ValueError(f"Duplicate method: {number}")
        result[number] = text[match.start():end].rstrip() + "\n"
    return result


def section(text, heading, next_heading=None):
    start = text.index(heading)
    end = text.index(next_heading, start + len(heading)) if next_heading else len(text)
    return text[start:end].rstrip() + "\n"


def verify(text, methods, source_json=None):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    checks = [
        ("snapshot_sha256", digest(text) == manifest["snapshot_sha256"]),
        ("method_ids", list(methods) == list(range(1, 38))),
    ]
    expected_fields = ["怎么做", "素材里要有", "和相近写法的区别", "变体", "适合", "别用在/风险", "例子", "来源数"]
    for item in manifest["sections"]:
        number = item["id"]
        body = methods.get(number, "")
        checks.extend([
            (f"method_{number}_text", digest(body) == item["sha256"]),
            (f"method_{number}_fields", re.findall(r"^- \*\*([^*]+)\*\*：", body, re.M) == expected_fields),
            (f"method_{number}_sources", re.findall(r"\[\[([^\]]+)\]\]", body) == item["source_slugs"]),
        ])
    if source_json:
        source = json.loads(Path(source_json).read_text(encoding="utf-8"))
        checks.append(("fresh_source_text", text == source["compiled_truth"]))
        checks.append(("fresh_source_hash", source["content_hash"] == manifest["source_content_hash"]))
    failed = [name for name, passed in checks if not passed]
    print(json.dumps({"passed": len(checks) - len(failed), "failed": len(failed), "failures": failed,
                      "method_count": len(methods), "snapshot_sha256": digest(text)}, ensure_ascii=False))
    return not failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", type=int, help="Method numbers, 1 through 37")
    parser.add_argument("--common", action="store_true", help="Read general cautions")
    parser.add_argument("--video", action="store_true", help="Read the two video-only companions")
    parser.add_argument("--gaps", action="store_true", help="Read documented evidence and long-form gaps")
    parser.add_argument("--all", action="store_true", help="Read the entire source page for an audit")
    parser.add_argument("--verify", action="store_true", help="Check full text, all method fields and source links")
    parser.add_argument("--source-json", type=Path, help="Also compare against a captured get_page JSON response")
    args = parser.parse_args()
    if not any([args.ids, args.common, args.video, args.gaps, args.all, args.verify]):
        parser.error("Choose method numbers or a named section; use --all only for an audit")
    if args.source_json and not args.verify:
        parser.error("--source-json requires --verify")
    if any(number < 1 or number > 37 for number in args.ids):
        parser.error("Method numbers must be between 1 and 37")
    text = SNAPSHOT.read_text(encoding="utf-8")
    methods = entries(text)
    if args.verify and not verify(text, methods, args.source_json):
        return 1
    output = []
    if args.all:
        output.append(text)
    else:
        if args.common:
            output.append(section(text, "### 通用禁忌", "## 钩子清单"))
        for number in dict.fromkeys(args.ids):
            output.append(methods[number])
        if args.video:
            output.append(section(text, "## 拍摄和剪辑上的配合", "## 缺口"))
        if args.gaps:
            output.append(section(text, "## 缺口"))
    if output:
        print(NOTICE + "\n" + "\n".join(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
