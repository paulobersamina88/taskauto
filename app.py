import io
import re
import textwrap
from typing import List, Dict

import pandas as pd
import streamlit as st

st.set_page_config(page_title="IMDO Executive Dashboard", layout="wide")

STATUS_MAP = {
    "UI": "Urgent & Important",
    "IN": "Important, Not Urgent",
    "U": "Urgent, Not Important",
    "NN": "Not Important, Not Urgent",
    "D": "Done",
    "": "Unspecified",
}

STATUS_SORT = {"UI": 0, "U": 1, "IN": 2, "NN": 3, "D": 4, "": 5}
STATUS_SEQUENCE = ["UI", "U", "IN", "NN", "D", ""]

DEFAULT_TEXT = """\
\t\tOWNER\tSUPPORT\tSTATUS\tPriority
\t\t\t\nIT building\t\t\t\t\t
Project Description\t\tSir Emet; PDO\tRose\tcontinue 5 floors\tIN
TOR\t\tPDO\tTin\ttalk to IT Director for justification\tIN
BOQ\t\tPDO\tTin\ttry check IMDO office\tIN
Drawings\t\tPDO\tRose\tdrawing as per Elearning format\tIN
Archi\t\tSir Emet; PDO\tRose\tno AC and Elevator\tIN
CE\t\tPDO\tTin\trequire contractor experience in floor addition\tIN
ME\t\tCOE\tPDO\tsignatory contractor\tIN
EE\t\tCOE\tPDO\tFDAS; network voice and cctv\tIN
Cr Phase 2\t\t\t\t\ttap EE expert
Project Description\t\tSir Emet; PDO\tRose\t\tUI
TOR\t\tPDO\tTin\t\tUI
BOQ\t\tPDO\tTin\t\tUI
Drawings\t\tPDO\tRose\t\tUI
Archi\t\tSir Emet; PDO\tRose\t\tUI
CE\t\tPDO\tTin\t\tUI
ME\t\tCOE\tPDO\t\tUI
EE\t\tCOE\tPDO\t\tUI
"""

TASK_KEYWORDS = {
    "project description",
    "tor",
    "boq",
    "drawings",
    "archi",
    "ce",
    "me",
    "ee",
    "structural",
    "plumbing",
    "budget",
    "office order",
    "sched",
    "speaker",
    "invite",
    "topics",
    "rate to pres",
    "masterplanning",
    "ppmp",
    "journal",
    "ludip depdev",
    "imdo office",
    "ot setup",
    "cnc application",
    "provide power requirement and coe team",
    "lot ownership clarification",
    "lot ownership",
    "masterplan",
    "new member moa",
    "erector 2000",
    "atlantic erector",
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
                "quadrant": priority_code or "",
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["assigned_staff"] = df.apply(
        lambda r: sorted(set(split_people(r["owner"]) + split_people(r["support"]))), axis=1
    )
    df["assigned_staff_text"] = df["assigned_staff"].apply(lambda x: ", ".join(x))
    df["has_notes"] = df["notes"].fillna("").str.strip().ne("")
    df["sort_priority"] = df["priority_code"].map(STATUS_SORT).fillna(99)
    return df


def build_staff_view(df: pd.DataFrame) -> pd.DataFrame:
    expanded = df.copy().explode("assigned_staff")
    expanded = expanded.rename(columns={"assigned_staff": "staff"})
    expanded["staff"] = expanded["staff"].fillna("Unassigned")
    return expanded


def download_df(df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    df.to_csv(out, index=False)
    return out.getvalue()


def compute_project_health(project_df: pd.DataFrame) -> Dict[str, object]:
    counts = {code: int((project_df["priority_code"] == code).sum()) for code in STATUS_SEQUENCE}
    total = len(project_df)
    done = counts["D"]
    ui = counts["UI"]
    u = counts["U"]
    in_count = counts["IN"]
    nn = counts["NN"]
    backlog = ui + u + in_count + nn + counts[""]
    done_rate = done / total if total else 0.0

    if total == 0:
        signal, level = "⚪", "No Data"
    elif backlog == 0 or done == total:
        signal, level = "🟢", "Green"
    elif ui > 0:
        signal, level = "🔴", "Red"
    elif u > 0 or in_count > 0:
        signal, level = "🟡", "Yellow"
    else:
        signal, level = "🟢", "Green"

    if level == "Red":
        remark = "Immediate management attention needed."
    elif level == "Yellow":
        remark = "In progress; monitor and close remaining actions."
    elif level == "Green":
        remark = "Healthy or substantially completed."
    else:
        remark = "Awaiting encoded tasks."

    return {
        "health_signal": signal,
        "health_level": level,
        "total_tasks": total,
        "done_tasks": done,
        "done_rate_pct": round(done_rate * 100, 1),
        "ui_tasks": ui,
        "u_tasks": u,
        "in_tasks": in_count,
        "nn_tasks": nn,
        "blank_tasks": counts[""],
        "backlog_tasks": backlog,
        "executive_remark": remark,
    }


st.title("IMDO Executive Dashboard")
st.caption("Paste a portion of your Google Sheet, then generate executive-level and staff-level task monitoring.")

with st.sidebar:
    st.header("Input")
    use_sample = st.toggle("Load sample data", value=True)
    raw_text = st.text_area(
        "Paste Google Sheet text here",
        value=DEFAULT_TEXT if use_sample else "",
        height=380,
        help="Copy rows directly from Google Sheets and paste them here.",
    )
    st.markdown("---")
    st.markdown("**Priority / Eisenhower legend**")
    st.write("UI = Urgent and Important")
    st.write("U = Urgent, Not Important")
    st.write("IN = Important, Not Urgent")
    st.write("NN = Not Important, Not Urgent")
    st.write("D = Done")
    st.markdown("---")
    show_done_in_action_board = st.checkbox("Show Done items in Action Board", value=False)


df = parse_imdo_text(raw_text)

if df.empty:
    st.warning("No tasks were parsed yet. Paste your Google Sheet block in the sidebar.")
    st.stop()

staff_df = build_staff_view(df)
all_staff = sorted([x for x in staff_df["staff"].dropna().unique().tolist() if x])
all_projects = sorted(df["project"].dropna().unique().tolist())
all_codes = [code for code in STATUS_SEQUENCE if code in set(df["priority_code"].fillna(""))]
code_label_map = {code: f"{code or 'Blank'} - {STATUS_MAP.get(code, 'Unspecified')}" for code in all_codes}

col1, col2, col3 = st.columns(3)
selected_staff = col1.multiselect("Filter by staff", all_staff, default=[])
selected_projects = col2.multiselect("Filter by project", all_projects, default=[])
selected_codes = col3.multiselect(
    "Filter by priority code",
    all_codes,
    default=[],
    format_func=lambda x: code_label_map.get(x, x),
)

filtered = df.copy()
if selected_projects:
    filtered = filtered[filtered["project"].isin(selected_projects)]
if selected_codes:
    filtered = filtered[filtered["priority_code"].isin(selected_codes)]
if selected_staff:
    filtered = filtered[filtered["assigned_staff"].apply(lambda lst: any(s in lst for s in selected_staff))]

f_staff = build_staff_view(filtered)

project_health_rows = []
for project_name, project_df in filtered.groupby("project", dropna=False):
    row = {"project": project_name}
    row.update(compute_project_health(project_df))
    project_health_rows.append(row)
project_health = pd.DataFrame(project_health_rows).sort_values(["health_level", "ui_tasks", "u_tasks", "project"])

view_cols = ["project", "task", "owner", "support", "notes", "priority_code", "priority", "assigned_staff_text"]

k1, k2, k3, k4, k5, k6 = st.columns(6)
projects_count = int(filtered["project"].nunique())
tasks_count = int(len(filtered))
staff_count = int(f_staff["staff"].nunique())
done_count = int((filtered["priority_code"] == "D").sum())
ui_backlog = int((filtered["priority_code"] == "UI").sum())
completion_rate = (done_count / tasks_count * 100) if tasks_count else 0
k1.metric("Projects", projects_count)
k2.metric("Tasks", tasks_count)
k3.metric("Staff involved", staff_count)
k4.metric("Done", done_count)
k5.metric("Urgent & Important", ui_backlog)
k6.metric("Completion %", f"{completion_rate:.1f}%")


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Executive Summary",
    "Parsed Tasks",
    "Staff Dashboard",
    "Project Dashboard",
    "Action Board",
])

with tab1:
    st.subheader("Executive portfolio view")
    executive_cols = [
        "health_signal",
        "health_level",
        "project",
        "total_tasks",
        "done_tasks",
        "done_rate_pct",
        "ui_tasks",
        "u_tasks",
        "in_tasks",
        "nn_tasks",
        "blank_tasks",
        "backlog_tasks",
        "executive_remark",
    ]
    st.dataframe(project_health[executive_cols], use_container_width=True, hide_index=True)

    summary_text = []
    red_count = int((project_health["health_level"] == "Red").sum()) if not project_health.empty else 0
    yellow_count = int((project_health["health_level"] == "Yellow").sum()) if not project_health.empty else 0
    green_count = int((project_health["health_level"] == "Green").sum()) if not project_health.empty else 0
    summary_text.append(f"{projects_count} projects monitored")
    summary_text.append(f"{red_count} red")
    summary_text.append(f"{yellow_count} yellow")
    summary_text.append(f"{green_count} green")
    summary_text.append(f"{completion_rate:.1f}% portfolio completion")
    st.info(" | ".join(summary_text))

    st.download_button(
        "Download executive summary CSV",
        data=download_df(project_health[executive_cols]),
        file_name="imdo_executive_summary.csv",
        mime="text/csv",
    )

with tab2:
    st.dataframe(filtered[view_cols].sort_values(["sort_priority", "project", "task"]), use_container_width=True, hide_index=True)
    st.download_button(
        "Download parsed CSV",
        data=download_df(filtered[view_cols]),
        file_name="imdo_parsed_tasks.csv",
        mime="text/csv",
    )

with tab3:
    staff_summary = (
        f_staff.groupby(["staff", "priority_code"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["staff", "count"], ascending=[True, False])
    )
    staff_total = (
        f_staff.groupby("staff", dropna=False)
        .size()
        .reset_index(name="total_tasks")
        .sort_values("total_tasks", ascending=False)
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Task count per staff")
        if not staff_total.empty:
            st.bar_chart(staff_total.set_index("staff")["total_tasks"])
    with c2:
        st.subheader("Priority mix by staff")
        if not staff_summary.empty:
            pivot = staff_summary.pivot(index="staff", columns="priority_code", values="count").fillna(0)
            st.bar_chart(pivot)

    focus_staff = st.selectbox("Select staff member", options=["All"] + all_staff, index=0)
    focus_code = st.selectbox(
        "Select priority bucket for selected staff",
        options=["All"] + [c for c in STATUS_SEQUENCE if c in set(f_staff["priority_code"].fillna(""))],
        index=0,
        format_func=lambda x: "All" if x == "All" else code_label_map.get(x, x),
    )

    if focus_staff != "All":
        staff_tasks = filtered[filtered["assigned_staff"].apply(lambda x: focus_staff in x)].copy()
        metric_base = staff_tasks.copy()
        if focus_code != "All":
            staff_tasks = staff_tasks[staff_tasks["priority_code"] == focus_code]

        metric_cols = st.columns(5)
        metric_cols[0].metric("UI", int((metric_base["priority_code"] == "UI").sum()))
        metric_cols[1].metric("U", int((metric_base["priority_code"] == "U").sum()))
        metric_cols[2].metric("IN", int((metric_base["priority_code"] == "IN").sum()))
        metric_cols[3].metric("NN", int((metric_base["priority_code"] == "NN").sum()))
        metric_cols[4].metric("D", int((metric_base["priority_code"] == "D").sum()))

        st.markdown(f"### Tasks for {focus_staff}")
        for code in STATUS_SEQUENCE:
            if focus_code not in ["All", code]:
                continue
            section = staff_tasks[staff_tasks["priority_code"] == code].sort_values(["project", "task"])
            if section.empty:
                continue
            label = code_label_map.get(code, f"{code or 'Blank'}")
            st.markdown(f"#### {label}")
            st.dataframe(section[view_cols], use_container_width=True, hide_index=True)
    else:
        st.dataframe(staff_total, use_container_width=True, hide_index=True)

with tab4:
    project_summary = (
        filtered.groupby(["project", "priority_code"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["project", "count"], ascending=[True, False])
    )
    project_total = (
        filtered.groupby("project", dropna=False)
        .size()
        .reset_index(name="total_tasks")
        .sort_values("total_tasks", ascending=False)
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Tasks per project")
        if not project_total.empty:
            st.bar_chart(project_total.set_index("project")["total_tasks"])
    with c2:
        st.subheader("Priority mix by project")
        if not project_summary.empty:
            project_pivot = project_summary.pivot(index="project", columns="priority_code", values="count").fillna(0)
            st.bar_chart(project_pivot)

    focus_project = st.selectbox("Select project", options=["All"] + all_projects, index=0)
    if focus_project != "All":
        st.markdown(f"### Tasks for {focus_project}")
        st.dataframe(
            filtered[filtered["project"] == focus_project][view_cols].sort_values(["sort_priority", "task"]),
            use_container_width=True,
            hide_index=True,
        )

with tab5:
    st.subheader("Top action items")
    action_df = filtered.copy().sort_values(["sort_priority", "project", "task"])
    if not show_done_in_action_board:
        action_df = action_df[action_df["priority_code"] != "D"]

    st.dataframe(
        action_df[["project", "task", "owner", "support", "notes", "priority_code", "priority"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Quick staff workload table")
    workload = (
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
        .sort_values(["ui_tasks", "u_tasks", "in_tasks", "total_tasks"], ascending=False)
    )
    if not workload.empty:
        workload["completion_pct"] = (workload["d_tasks"] / workload["total_tasks"] * 100).round(1)
    st.dataframe(workload, use_container_width=True, hide_index=True)

with st.expander("Notes about the parser and executive logic"):
    st.markdown(
        textwrap.dedent(
            """
            - Project headers are detected when a line contains only one main label, such as **IT building** or **Library**.
            - Task rows are read from pasted tab-separated lines.
            - Continuation lines without owners/support are appended to the previous task's notes.
            - Staff names in owner/support are split using semicolons or commas.
            - Priority codes supported are **UI**, **U**, **IN**, **NN**, and **D**.
            - Executive health logic is simplified for dashboard use:
              - **Red** = any UI task exists
              - **Yellow** = no UI, but U or IN backlog remains
              - **Green** = completed or no active backlog remains
            """
        )
    )
