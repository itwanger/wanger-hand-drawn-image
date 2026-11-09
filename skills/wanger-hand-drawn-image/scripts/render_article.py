"""Render verified local media into standalone Markdown placeholders; write to stdout."""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
PLACEHOLDER = re.compile(r"【截图[：:].+】")


def render(article, mapping):
    if not isinstance(mapping, dict):
        raise ValueError("Expected a placeholder-to-asset object")
    references = {}
    for key, asset in mapping.items():
        if not PLACEHOLDER.fullmatch(key):
            raise ValueError(f"Invalid placeholder: {key}")
        file = Path(asset["file"])
        if file.is_absolute() or not (article.parent / file).is_file():
            raise ValueError(f"Expected an existing article-relative file: {file}")
        alt = asset["alt"]
        if not isinstance(alt, str) or not alt.strip() or "\n" in alt or "\r" in alt:
            raise ValueError(f"Expected single-line alt text for {file}")
        alt = re.sub(r"([\\\[\]])", r"\\\1", alt)
        references[key] = f"![{alt}]({quote(file.as_posix(), safe='/.-_~')})"

    lines = article.read_bytes().decode("utf-8").splitlines(keepends=True)
    frontmatter = bool(lines and lines[0].rstrip("\r\n") == "---")
    fence = ""
    found = set()
    for index, line in enumerate(lines):
        content = line.rstrip("\r\n")
        if frontmatter:
            if index and content in ("---", "..."):
                frontmatter = False
            continue
        marker = FENCE.match(content)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
            continue
        if marker:
            fence = marker[1]
            continue
        if content in references:
            if content in found:
                raise ValueError(f"Ambiguous duplicate placeholder: {content}")
            found.add(content)
            lines[index] = references[content] + line[len(content):]
    missing = references.keys() - found
    if missing:
        raise ValueError("Missing placeholder: " + ", ".join(sorted(missing)))
    return "".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path)
    parser.add_argument("mapping", type=Path)
    args = parser.parse_args()
    try:
        result = render(args.article, json.loads(args.mapping.read_text(encoding="utf-8")))
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Cannot render article: {error}\n")
    sys.stdout.buffer.write(result.encode("utf-8"))


if __name__ == "__main__":
    main()
