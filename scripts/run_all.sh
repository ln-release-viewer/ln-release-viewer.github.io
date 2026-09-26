#!/bin/bash
set -e

# 1. Parse README
python3 scripts/parse_readme.py

# 2. Add ISBNs
xvfb-run -a python3 -u scripts/add_isbns.py

# 4. Fetch covers (with Xvfb)
xvfb-run -a python3 -u scripts/fetch_covers.py

# 5. Add vendor links
python3 scripts/add_vendors.py
