@echo off
title AI Construction System - Quota A111
cd /d E:\workspace\01_Projects\ai-construction-system\construction_cost_knowledge_engine

echo Starting quota-a111 on http://127.0.0.1:8005/quota-a111
echo Do not close this window while using the page.
echo.

..\.venv\Scripts\python.exe -m uvicorn web_collab_prototype.app:app --host 127.0.0.1 --port 8005

echo.
echo Server stopped.
pause