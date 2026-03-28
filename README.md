# IMDO Executive Dashboard

A Streamlit dashboard for pasted Google Sheet task blocks used by IMDO.

## Features
- Parses tab-separated Google Sheet text
- Supports UI, U, IN, NN, and D priority codes
- Executive Summary tab with Red / Yellow / Green project health
- Staff Dashboard with per-person filtering
- Project Dashboard
- Action Board with optional hiding of Done items
- CSV export for parsed tasks and executive summary

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Priority Codes
- UI = Urgent and Important
- U = Urgent, Not Important
- IN = Important, Not Urgent
- NN = Not Important, Not Urgent
- D = Done
