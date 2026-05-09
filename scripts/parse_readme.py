import re
import json
from pathlib import Path

README = Path("lnrelease-src/README.md")
OUTPUT = Path("data/releases.json")

# Regex to match table rows
ROW_RE = re.compile(
    r"\|(?P<date>[^|]+)\|"
    r"

\[(?P<title>[^\]

]+)\]

\((?P<link>[^ ]+) \"(?P<publisher>[^\"]+)\"\)\|"
    r"(?P<volume>[^|]+)\|"
    r"(?P<pub2>[^|]+)\|"
    r"(?P<format>[^|]+)\|"
)

def parse_readme():
    releases = []

    with README.open("r", encoding="utf-8") as f:
        for line in f:
            m = ROW_RE.match(line)
            if not m:
                continue

            releases.append({
                "date": m.group("date").strip(),
                "title": m.group("title").strip(),
                "link": m.group("link").strip(),
                "volume": m.group("volume").strip(),
                "publisher": m.group("publisher").strip(),
                "format": m.group("format").strip(),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    parse_readme()
