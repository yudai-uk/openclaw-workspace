#!/bin/bash

# OpenClaw Workspace Auto-Sync Script
# Runs every 5 minutes to push changes to GitHub

cd ~/.openclaw/workspace

# Check for changes
if [ -n "$(git status --porcelain)" ]; then
  # Add all changes
  git add -A

  # Commit with timestamp
  git commit -m "Auto-sync $(date '+%Y-%m-%d %H:%M:%S')"

  # Push to GitHub
  git push origin main
fi
