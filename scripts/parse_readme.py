import re
import json
from pathlib import Path

README = Path("lnrelease-src/README.md")
OUTPUT = Path("data/releases.json")

# Regex to match table rows
ROW_RE = re.compile(
    r"\|(?P<date>[^|]+)\|"
    r"\[(?P<title>[^\]]+)\]\((?P<link>[^ ]+) \"(?P<publisher>[^\"]+)\"\)\|"
    r"(?P<volume>[^|]+)\|"
    r"(?P<pub2>[^|]+)\|"
    r"(?P<format>[^|]+)\|"
)

YEAR_RE = re.compile(r"^##\s+(\d{4})")
MONTH_RE = re.compile(r"^###\s+([A-Za-z]+)")

def parse_readme():
    # Load existing releases.json if present
    old = {}
    if OUTPUT.exists():
        with OUTPUT.open("r", encoding="utf-8") as f:
            for r in json.load(f):
                key = f"{r['title']}::{r['volume']}"
                old[key] = r

    releases = []
    current_year = None
    current_month = None

    with README.open("r", encoding="utf-8") as f:
        for line in f:
            y = YEAR_RE.match(line)
            if y:
                current_year = int(y.group(1))
                continue

            m = MONTH_RE.match(line)
            if m:
                current_month = m.group(1)
                continue

            r = ROW_RE.match(line)
            if not r:
                continue

            vol_field = r.group("volume").strip()

            # Expand ranges like "11-12"
            if "-" in vol_field:
                start, end = vol_field.split("-", 1)
                try:
                    start = int(start)
                    end = int(end)
                    volumes = [str(v) for v in range(start, end + 1)]
                except ValueError:
                    volumes = [vol_field]
            else:
                volumes = [vol_field]

            for vol in volumes:
                title = r.group("title").strip()
                key = f"{title}::{vol}"

                new_entry = {
                    "date": r.group("date").strip(),
                    "month": current_month,
                    "year": current_year,
                    "title": title,
                    "link": r.group("link").strip(),
                    "volume": vol,
                    "publisher": r.group("publisher").strip(),
                    "format": r.group("format").strip(),
                }

                # Merge old fields (cover, isbn, slug, etc.)
                if key in old:
                    merged = old[key].copy()
                    merged.update(new_entry)
                    releases.append(merged)
                else:
                    releases.append(new_entry)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    parse_readme()

