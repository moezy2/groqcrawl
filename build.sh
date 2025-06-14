#!/usr/bin/env bash
# build.sh

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
