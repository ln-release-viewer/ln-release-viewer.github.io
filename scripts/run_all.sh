#!/bin/bash
set -e

# 1. Parse README
python3 scripts/parse_readme.py

# 2. Add ISBNs
python3 scripts/add_isbns.py

# 3. Fetch covers (with Xvfb)
xvfb-run -a python3 -u scripts/fetch_covers.py
