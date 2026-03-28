
import io
import re
import textwrap
from typing import List, Dict

import pandas as pd
import streamlit as st

st.set_page_config(page_title="IMDO Presidential Dashboard", layout="wide")

STATUS_MAP = {
    "UI": "Urgent & Important",
    "U": "Urgent, Not Important",
    "IN": "Important, Not Urgent",
    "NN": "Not Important, Not Urgent",
    "D": "Done",
    "": "Unspecified",
}

STATUS_SORT = {"UI": 0, "U": 1, "IN": 2, "NN": 3, "D": 4, "": 5}
DISPLAY_CODES = ["UI", "U", "IN", "NN", "D", ""]

DEFAULT_TEXT = """\
\t\tOWNER\tSUPPORT\tSTATUS\tPriority

IT building\t\t\t\t\t
Project Description\t\tSir Emet; PDO\tRose\tcontinue 5 floors\tIN
TOR\t\tPDO\tTin\ttalk to IT Director for justification\tIN
BOQ\t\tPDO\tTin\ttry check IMDO office\tIN
Drawings\t\tPDO\tRose\tdrawing as per Elearning format\tIN
Archi\t\tSir Emet; PDO\tRose\tno AC and Elevator\tIN
CE\t\tPDO\tTin\trequire contractor experience in floor addition\tIN
ME\t\tCOE\tPDO\tsignatory contractor\tIN
EE\t\tCOE\tPDO\tFDAS; network voice and cctv\tIN

Cr Phase 2\t\t\t\t\t
Project Description\t\tSir Emet; PDO\tRose\t\tUI
TOR\t\tPDO\tTin\t\tUI
BOQ\t\tPDO\tTin\t\tUI
Drawings\t\tPDO\tRose\t\tUI
Archi\t\tSir Emet; PDO\tRose\t\tUI
CE\t\tPDO\tTin\t\tUI
ME\t\tCOE\tPDO\t\tU
EE\t\tCOE\tPDO\t\tD
"""

TASK_KEYWORDS = {
    "project description", "tor", "boq", "drawings", "archi", "ce", "me", "ee", "structural",
    "plumbing", "budget", "office order", "sched", "speaker", "invite", "topics", "rate to pres",
    "masterplanning", "ppmp", "journal", "ludip depdev", "imdo office", "ot setup", "cnc application",
    "provide power requirement and coe team", "lot ownership clarification", "lot ownership",
    "masterplan", "new member moa", "erector 2000", "atlantic erector", "show details",
}


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def split_people(value: str) -> List[str]:
    if not value:
        return []
    cleaned = value.replace("/", ";").replace(",", ";")
    parts = [normalize_ws(x) for x in cleaned.split(";")]
    return [p for p in parts if p]


@st.cache_data(show_spinner=False)
def parse_imdo_text(raw_text: str) -> pd.DataFrame:
    lines = raw_text.splitlines()
    current_project = None
    rows: List[Dict] = []

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue

        cells = [c.strip() for c in line.split("\t")]
        nonempty = [c for c in cells if c.strip()]
        if not nonempty:
            continue

        joined = " ".join(nonempty).lower()
        if joined == "owner support status priority":
            continue

        if len(nonempty) == 1 and normalize_ws(nonempty[0]).lower() not in TASK_KEYWORDS:
            current_project = normalize_ws(nonempty[0])
            continue

        first = normalize_ws(cells[0]) if len(cells) > 0 else ""
        second = normalize_ws(cells[1]) if len(cells) > 1 else ""
        third = normalize_ws(cells[2]) if len(cells) > 2 else ""
        fourth = normalize_ws(cells[3]) if len(cells) > 3 else ""
        fifth = normalize_ws(cells[4]) if len(cells) > 4 else ""
        sixth = normalize_ws(cells[5]) if len(cells) > 5 else ""

        task = first
        owner = third
        support = fourth
        notes = fifth
        priority_code = sixth.upper()

        if not priority_code and fifth.upper() in {"UI", "IN", "U", "NN", "D"}:
            priority_code = fifth.upper()
            notes = ""
        if not owner and second and any(ch.isalpha() for ch in second):
            owner = second
        if not task and second and normalize_ws(second).lower() not in {"owner", "support", "status", "priority"}:
            task = second

        if task == "" and (notes or fifth or sixth or second or third or fourth):
            extra_parts = [x for x in [second, third, fourth, fifth, sixth] if x]
            extra_note = normalize_ws("; ".join(extra_parts))
            if rows and extra_note:
                rows[-1]["notes"] = normalize_ws((rows[-1].get("notes", "") + "; " + extra_note).strip("; "))
            continue

        if task and not owner and not support and not priority_code and current_project is not None:
            task_lower = task.lower()
            if task_lower not in TASK_KEYWORDS and rows:
                rows[-1]["notes"] = normalize_ws((rows[-1].get("notes", "") + "; " + task).strip("; "))
                continue

        if not task:
            continue

        rows.append(
            {
                "project": current_project or "Unassigned Project",
                "task": task,
                "owner": owner,
                "support": support,
                "notes": notes,
                "priority_code": priority_code,
                "priority": STATUS_MAP.get(priority_code, priority_code or "Unspecified"),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["assigned_staff"] = df.apply(lambda r: sorted(set(split_people(r["owner"]) + split_people(r["support"]))), axis=1)
    df["assigned_staff_text"] = df["assigned_staff"].apply(lambda x: ", ".join(x))
    df["has_notes"] = df["notes"].fillna("").str.strip().ne("")
    df["sort_priority"] = df["priority_code"].map(STATUS_SORT).fillna(99)
    return df


def build_staff_view(df: pd.DataFrame) -> pd.DataFrame:
    expanded = df.copy().explode("assigned_staff")
    expanded = expanded.rename(columns={"assigned_staff": "staff"})
    expanded["staff"] = expanded["staff"].fillna("Unassigned")
    return expanded


def project_health(row) -> str:
    if row["ui"] >= 3 or (row["ui"] >= 1 and row["in_progress"] >= 5):
        return "Red"
    if row["ui"] >= 1 or row["u"] >= 2 or row["in_progress"] >= 3:
        return "Yellow"
    return "Green"


def health_emoji(h: str) -> str:
    return {"Red": "🔴", "Yellow": "🟡", "Green": "🟢"}.get(h, "⚪")


def download_df(df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    df.to_csv(out, index=False)
    return out.getvalue()


st.title("IMDO Presidential Dashboard")
st.caption("Executive and presidential-level monitoring for IMDO projects, staff priorities, completion, and urgent backlog.")

with st.sidebar:
    st.header("Input")
    use_sample = st.toggle("Load sample data", value=True)
    raw_text = st.text_area(
        "Paste Google Sheet text here",
        value=DEFAULT_TEXT if use_sample else "",
        height=360,
        help="Copy rows directly from Google Sheets and paste them here.",
    )
    st.markdown("---")
    st.markdown("**Priority legend**")
    st.write("UI = Urgent and Important")
    st.write("U = Urgent, Not Important")
    st.write("IN = Important, Not Urgent")
    st.write("NN = Not Important, Not Urgent")
    st.write("D = Done")
    st.markdown("---")
    hide_done_action_board = st.checkbox("Hide Done in action board", value=True)
    red_ui_threshold = st.number_input("Red threshold: UI tasks per project", min_value=1, max_value=10, value=3)
    yellow_ui_threshold = st.number_input("Yellow threshold: UI tasks per project", min_value=1, max_value=10, value=1)

df = parse_imdo_text(raw_text)

if df.empty:
    st.warning("No tasks were parsed yet. Paste your Google Sheet block in the sidebar.")
    st.stop()

staff_df = build_staff_view(df)

all_staff = sorted([x for x in staff_df["staff"].dropna().unique().tolist() if x])
all_projects = sorted(df["project"].dropna().unique().tolist())
available_codes = set(df["priority_code"].fillna(""))
all_codes = [code for code in DISPLAY_CODES if code in available_codes]
code_label_map = {code: f"{code or 'Blank'} - {STATUS_MAP.get(code, 'Unspecified')}" for code in all_codes}

col1, col2, col3 = st.columns(3)
selected_staff = col1.multiselect("Filter by staff", all_staff, default=[])
selected_projects = col2.multiselect("Filter by project", all_projects, default=[])
selected_codes = col3.multiselect("Filter by priority code", all_codes, default=[], format_func=lambda x: code_label_map.get(x, x))

filtered = df.copy()
if selected_projects:
    filtered = filtered[filtered["project"].isin(selected_projects)]
if selected_codes:
    filtered = filtered[filtered["priority_code"].isin(selected_codes)]
if selected_staff:
    filtered = filtered[filtered["assigned_staff"].apply(lambda lst: any(s in lst for s in selected_staff))]

f_staff = build_staff_view(filtered)

done_count = int((filtered["priority_code"] == "D").sum())
ui_count = int((filtered["priority_code"] == "UI").sum())
completion_pct = (done_count / len(filtered) * 100) if len(filtered) else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Projects", filtered["project"].nunique())
k2.metric("Tasks", len(filtered))
k3.metric("Staff involved", f_staff["staff"].nunique())
k4.metric("Done", done_count)
k5.metric("Urgent & Important", ui_count)
k6.metric("Completion %", f"{completion_pct:.1f}%")

view_cols = ["project", "task", "owner", "support", "notes", "priority_code", "priority", "assigned_staff_text"]

project_exec = (
    filtered.assign(
        ui=lambda x: (x["priority_code"] == "UI").astype(int),
        u=lambda x: (x["priority_code"] == "U").astype(int),
        inn=lambda x: (x["priority_code"] == "IN").astype(int),
        nn=lambda x: (x["priority_code"] == "NN").astype(int),
        done=lambda x: (x["priority_code"] == "D").astype(int),
    )
    .groupby("project", dropna=False)
    .agg(
        total_tasks=("task", "count"),
        ui=("ui", "sum"),
        u=("u", "sum"),
        inn=("inn", "sum"),
        nn=("nn", "sum"),
        done=("done", "sum"),
    )
    .reset_index()
)

project_exec["in_progress"] = project_exec["total_tasks"] - project_exec["done"]
project_exec["completion_pct"] = (project_exec["done"] / project_exec["total_tasks"] * 100).round(1)
project_exec["health"] = project_exec.apply(
    lambda row: "Red" if row["ui"] >= red_ui_threshold or (row["ui"] >= yellow_ui_threshold and row["in_progress"] >= 5)
    else ("Yellow" if row["ui"] >= yellow_ui_threshold or row["u"] >= 2 or row["in_progress"] >= 3 else "Green"),
    axis=1,
)
project_exec["indicator"] = project_exec["health"].apply(health_emoji)
project_exec["presidential_note"] = project_exec.apply(
    lambda row: "Needs top management intervention" if row["health"] == "Red"
    else ("Monitor closely and clear blockers" if row["health"] == "Yellow" else "Generally on track"),
    axis=1,
)

staff_workload = (
    f_staff.groupby("staff")
    .agg(
        total_tasks=("task", "count"),
        ui_tasks=("priority_code", lambda s: int((s == "UI").sum())),
        u_tasks=("priority_code", lambda s: int((s == "U").sum())),
        in_tasks=("priority_code", lambda s: int((s == "IN").sum())),
        nn_tasks=("priority_code", lambda s: int((s == "NN").sum())),
        d_tasks=("priority_code", lambda s: int((s == "D").sum())),
    )
    .reset_index()
)
staff_workload["completion_pct"] = (staff_workload["d_tasks"] / staff_workload["total_tasks"] * 100).round(1)
staff_workload["backlog"] = staff_workload["total_tasks"] - staff_workload["d_tasks"]

tabs = st.tabs(["Presidential Summary", "Executive Summary", "Parsed Tasks", "Staff Dashboard", "Project Dashboard", "Action Board"])

with tabs[0]:
    red_count = int((project_exec["health"] == "Red").sum())
    yellow_count = int((project_exec["health"] == "Yellow").sum())
    green_count = int((project_exec["health"] == "Green").sum())

    c1, c2 = st.columns([1.6, 1])
    with c1:
        st.subheader("Portfolio Health Overview")
        summary_df = project_exec[[
            "indicator", "health", "project", "total_tasks", "ui", "u", "inn", "nn", "done",
            "in_progress", "completion_pct", "presidential_note"
        ]].sort_values(["health", "ui", "in_progress", "project"], ascending=[True, False, False, True])
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        st.info(
            f"{len(project_exec)} projects monitored | "
            f"{red_count} red | {yellow_count} yellow | {green_count} green | "
            f"{completion_pct:.1f}% portfolio completion"
        )
        st.download_button(
            "Download presidential summary CSV",
            data=download_df(summary_df),
            file_name="imdo_presidential_summary.csv",
            mime="text/csv",
        )
    with c2:
        st.subheader("Presidential Attention Projects")
        hot = project_exec.sort_values(["health", "ui", "in_progress"], ascending=[True, False, False]).head(10)
        st.dataframe(
            hot[["indicator", "project", "ui", "u", "in_progress", "completion_pct", "presidential_note"]],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Recommended Talking Points")
        red_projects = hot[hot["health"] == "Red"]["project"].tolist()
        yellow_projects = hot[hot["health"] == "Yellow"]["project"].tolist()
        notes = []
        if red_projects:
            notes.append(f"Immediate intervention may be needed for: {', '.join(red_projects[:5])}.")
        if yellow_projects:
            notes.append(f"Close monitoring is advised for: {', '.join(yellow_projects[:5])}.")
        if done_count:
            notes.append(f"{done_count} tasks are already marked done, equivalent to {completion_pct:.1f}% completion.")
        if not notes:
            notes.append("No major backlog flags detected from the current filtered view.")
        for n in notes:
            st.write(f"- {n}")

with tabs[1]:
    st.subheader("Executive Summary")
    exec_cols = st.columns(3)
    with exec_cols[0]:
        st.bar_chart(project_exec.set_index("project")[["ui", "u", "inn", "nn", "done"]])
    with exec_cols[1]:
        health_counts = project_exec["health"].value_counts()
        st.bar_chart(health_counts)
    with exec_cols[2]:
        st.dataframe(
            staff_workload.sort_values(["ui_tasks", "backlog", "total_tasks"], ascending=False),
            use_container_width=True,
            hide_index=True,
        )

with tabs[2]:
    st.subheader("Parsed Tasks")
    st.dataframe(
        filtered.sort_values(["sort_priority", "project", "task"])[view_cols],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download parsed CSV",
        data=download_df(filtered[view_cols]),
        file_name="imdo_parsed_tasks.csv",
        mime="text/csv",
    )

with tabs[3]:
    st.subheader("Staff Dashboard")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.bar_chart(staff_workload.set_index("staff")[["ui_tasks", "u_tasks", "in_tasks", "nn_tasks", "d_tasks"]])
    with c2:
        st.dataframe(
            staff_workload.sort_values(["ui_tasks", "backlog", "completion_pct"], ascending=[False, False, False]),
            use_container_width=True,
            hide_index=True,
        )

    focus_staff = st.selectbox("Select staff member", options=["All"] + all_staff, index=0)
    focus_code_options = ["All"] + [c for c in DISPLAY_CODES if c in set(f_staff["priority_code"].fillna(""))]
    focus_code = st.selectbox(
        "Select priority bucket for selected staff",
        options=focus_code_options,
        index=0,
        format_func=lambda x: "All" if x == "All" else code_label_map.get(x, x),
    )

    if focus_staff != "All":
        staff_tasks = filtered[filtered["assigned_staff"].apply(lambda x: focus_staff in x)].copy()
        if focus_code != "All":
            staff_tasks = staff_tasks[staff_tasks["priority_code"] == focus_code]

        metric_cols = st.columns(5)
        metric_cols[0].metric("UI", int((staff_tasks["priority_code"] == "UI").sum()))
        metric_cols[1].metric("U", int((staff_tasks["priority_code"] == "U").sum()))
        metric_cols[2].metric("IN", int((staff_tasks["priority_code"] == "IN").sum()))
        metric_cols[3].metric("NN", int((staff_tasks["priority_code"] == "NN").sum()))
        metric_cols[4].metric("D", int((staff_tasks["priority_code"] == "D").sum()))

        for code in DISPLAY_CODES:
            if focus_code not in ["All", code]:
                continue
            section = staff_tasks[staff_tasks["priority_code"] == code].sort_values(["sort_priority", "project", "task"])
            if section.empty:
                continue
            st.markdown(f"#### {code_label_map.get(code, code or 'Blank')}")
            st.dataframe(section[view_cols], use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Project Dashboard")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.bar_chart(project_exec.set_index("project")[["total_tasks", "done", "in_progress"]])
    with c2:
        st.dataframe(
            project_exec.sort_values(["health", "ui", "in_progress"], ascending=[True, False, False]),
            use_container_width=True,
            hide_index=True,
        )

    focus_project = st.selectbox("Select project", options=["All"] + all_projects, index=0)
    if focus_project != "All":
        st.markdown(f"### Tasks for {focus_project}")
        st.dataframe(
            filtered[filtered["project"] == focus_project].sort_values(["sort_priority", "task"])[view_cols],
            use_container_width=True,
            hide_index=True,
        )

with tabs[5]:
    st.subheader("Action Board")
    action_df = filtered.copy()
    if hide_done_action_board:
        action_df = action_df[action_df["priority_code"] != "D"]
    st.dataframe(
        action_df.sort_values(["sort_priority", "project", "task"])[["project", "task", "owner", "support", "notes", "priority_code", "priority"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Quick staff workload table")
    st.dataframe(
        staff_workload.sort_values(["ui_tasks", "backlog", "total_tasks"], ascending=False),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Notes about the parser"):
    st.markdown(
        textwrap.dedent(
            """
            - Project headers are detected when a line contains only one main label, such as **IT building** or **Library**.
            - Task rows are read from pasted tab-separated lines.
            - Continuation lines without owners/support are appended to the previous task's notes.
            - Staff names in owner/support are split using semicolons or commas.
            - Priority codes are preserved exactly, including **D** for done.
            - Sorting is applied before selecting display columns to avoid KeyError on hidden helper columns like `sort_priority`.
            """
        )
    )
