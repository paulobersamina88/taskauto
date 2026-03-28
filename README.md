# IMDO Task Automator

A Streamlit prototype that parses pasted Google Sheet task blocks and turns them into:

- a clean task table
- staff workload dashboard
- project dashboard
- action board sorted by urgency

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## How to use

1. Copy rows from Google Sheets.
2. Paste them into the text box in the sidebar.
3. Review parsed tasks.
4. Filter by staff, project, or priority.
5. Download the parsed CSV if needed.

## Current logic

- Detects project headers
- Parses owner, support, notes, and priority
- Expands assigned staff from owner/support
- Appends orphan continuation lines to the previous task note

## Suggested next upgrades

- due dates
- editable status updates
- Google Sheets API sync
- automatic weekly report per staff
- email reminder generation
- color-coded Kanban board
