import os
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

FILE_PATH = "tasks.xlsx"
SHEET_NAME = "tasks"
MAX_TASKS = 3
GOAL_HOURS_DEFAULT = 1000
GOAL_MINUTES_DEFAULT = GOAL_HOURS_DEFAULT * 60


def ensure_file_exists(path: str) -> None:
    """Create an empty Excel file with the right schema if it doesn't exist."""
    if os.path.exists(path):
        return

    df = pd.DataFrame(
        columns=[
            "task_id",
            "task_name",
            "goal_minutes",
            "minutes_spent",
            "created_at",
            "updated_at",
        ]
    )
    df.to_excel(path, index=False, sheet_name=SHEET_NAME, engine="openpyxl")


def load_tasks(path: str) -> pd.DataFrame:
    ensure_file_exists(path)
    df = pd.read_excel(path, sheet_name=SHEET_NAME, engine="openpyxl")

    # Hardening: enforce required columns even if file was edited manually
    required = {
        "task_id": [],
        "task_name": [],
        "goal_minutes": [],
        "minutes_spent": [],
        "created_at": [],
        "updated_at": [],
    }
    for col in required:
        if col not in df.columns:
            df[col] = None

    # Fill defaults
    if df.empty:
        return df

    df["goal_minutes"] = df["goal_minutes"].fillna(GOAL_MINUTES_DEFAULT).astype(int)
    df["minutes_spent"] = df["minutes_spent"].fillna(0).astype(int)
    df["task_name"] = df["task_name"].fillna("").astype(str)

    return df


def save_tasks(df: pd.DataFrame, path: str) -> None:
    df.to_excel(path, index=False, sheet_name=SHEET_NAME, engine="openpyxl")


def fmt_time(minutes: int) -> str:
    """Format minutes into 'Xh Ym'."""
    if minutes < 0:
        minutes = 0
    h = minutes // 60
    m = minutes % 60
    return f"{h}h {m}m"


def donut(task_name: str, spent_min: int, goal_min: int) -> go.Figure:
    spent_min = max(0, min(spent_min, goal_min))
    left_min = max(0, goal_min - spent_min)

    # Plotly donut (no custom colors to keep it simple & theme-friendly)
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Spent", "Left"],
                values=[spent_min, left_min],
                hole=0.7,
                textinfo="none",
                sort=False,
                direction="clockwise",
            )
        ]
    )

    center_text = (
        f"<b>{task_name}</b><br>"
        f"Spent: {fmt_time(spent_min)}<br>"
        f"Left: {fmt_time(left_min)}"
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        annotations=[
            dict(
                text=center_text,
                x=0.5,
                y=0.5,
                font=dict(size=12),
                showarrow=False,
                align="center",
            )
        ],
    )
    return fig


st.set_page_config(page_title="1000 Hours Tracker", layout="wide")

st.title("⏱️ 1000 Hours Task Tracker (Max 3 Tasks)")
st.caption("Prototype storage: Excel file in the app folder. Use Download Backup regularly.")

tasks = load_tasks(FILE_PATH)

# ---------- Create Task ----------
with st.expander("➕ Create a new task", expanded=True):
    colA, colB, colC = st.columns([2, 1, 1])

    with colA:
        new_name = st.text_input("Task name", placeholder="e.g., Paper writing, Gym, Grant proposal")

    with colB:
        goal_hours = st.number_input("Goal (hours)", min_value=1, max_value=10000, value=GOAL_HOURS_DEFAULT, step=10)

    with colC:
        can_create = len(tasks) < MAX_TASKS
        create_clicked = st.button("Create task", disabled=not can_create, use_container_width=True)

    if not can_create:
        st.warning("You already have 3 tasks. Delete one before creating a new task.")

    if create_clicked:
        name_clean = (new_name or "").strip()
        if not name_clean:
            st.error("Please enter a task name.")
        else:
            now = datetime.now().isoformat(timespec="seconds")
            next_id = 1 if tasks.empty else int(tasks["task_id"].max()) + 1
            new_row = {
                "task_id": next_id,
                "task_name": name_clean,
                "goal_minutes": int(goal_hours * 60),
                "minutes_spent": 0,
                "created_at": now,
                "updated_at": now,
            }
            tasks = pd.concat([tasks, pd.DataFrame([new_row])], ignore_index=True)
            save_tasks(tasks, FILE_PATH)
            st.success(f"Created task: {name_clean}")
            st.rerun()

st.divider()

# ---------- Backup ----------
with open(FILE_PATH, "rb") as f:
    st.download_button(
        label="⬇️ Download Excel backup",
        data=f,
        file_name="tasks_backup.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )

st.divider()

# ---------- Display tasks (up to 3 at once) ----------
if tasks.empty:
    st.info("No tasks yet. Create up to 3 tasks above.")
    st.stop()

# Ensure display always shows at most 3 (even if file edited)
tasks = tasks.head(MAX_TASKS).copy()

# Layout: 3 columns
cols = st.columns(3)

for idx, (_, row) in enumerate(tasks.iterrows()):
    with cols[idx]:
        task_id = int(row["task_id"])
        task_name = row["task_name"]
        goal_min = int(row["goal_minutes"])
        spent_min = int(row["minutes_spent"])

        st.subheader(task_name if task_name else f"Task {task_id}")

        # Donut chart
        st.plotly_chart(donut(task_name or f"Task {task_id}", spent_min, goal_min), use_container_width=True)

        # Progress metrics
        left_min = max(0, goal_min - spent_min)
        st.metric("Time spent", fmt_time(spent_min))
        st.metric("Time left", fmt_time(left_min))

        st.markdown("### Add time")
        tcol1, tcol2 = st.columns([2, 1])
        with tcol1:
            amount = st.number_input(
                "Amount",
                min_value=0.0,
                value=0.0,
                step=0.25,
                key=f"amount_{task_id}",
                help="Enter a number (supports decimals).",
            )
        with tcol2:
            unit = st.selectbox("Unit", ["hours", "minutes"], key=f"unit_{task_id}")

        add_clicked = st.button("Add time", key=f"add_{task_id}", use_container_width=True)

        # Optional: allow subtract (mistakes)
        with st.expander("Fix mistakes (subtract time)"):
            scol1, scol2 = st.columns([2, 1])
            with scol1:
                sub_amount = st.number_input(
                    "Subtract amount",
                    min_value=0.0,
                    value=0.0,
                    step=0.25,
                    key=f"sub_amount_{task_id}",
                )
            with scol2:
                sub_unit = st.selectbox("Unit ", ["hours", "minutes"], key=f"sub_unit_{task_id}")
            sub_clicked = st.button("Subtract time", key=f"sub_{task_id}", use_container_width=True)

        dcol1, dcol2 = st.columns([1, 1])
        with dcol1:
            reset_clicked = st.button("Reset to 0", key=f"reset_{task_id}", use_container_width=True)
        with dcol2:
            delete_clicked = st.button("Delete task", key=f"delete_{task_id}", use_container_width=True)

        def to_minutes(x: float, u: str) -> int:
            return int(round(x * 60)) if u == "hours" else int(round(x))

        # Handle actions
        if add_clicked:
            delta = to_minutes(amount, unit)
            if delta <= 0:
                st.warning("Enter a positive amount to add.")
            else:
                now = datetime.now().isoformat(timespec="seconds")
                tasks.loc[tasks["task_id"] == task_id, "minutes_spent"] = (
                    tasks.loc[tasks["task_id"] == task_id, "minutes_spent"].astype(int) + delta
                )
                # Cap at goal to keep donut clean
                tasks.loc[tasks["task_id"] == task_id, "minutes_spent"] = tasks.loc[
                    tasks["task_id"] == task_id, "minutes_spent"
                ].clip(upper=goal_min)
                tasks.loc[tasks["task_id"] == task_id, "updated_at"] = now
                save_tasks(tasks, FILE_PATH)
                st.success(f"Added {fmt_time(delta)}")
                st.rerun()

        if "sub_clicked" in locals() and sub_clicked:
            delta = to_minutes(sub_amount, sub_unit)
            if delta <= 0:
                st.warning("Enter a positive amount to subtract.")
            else:
                now = datetime.now().isoformat(timespec="seconds")
                tasks.loc[tasks["task_id"] == task_id, "minutes_spent"] = (
                    tasks.loc[tasks["task_id"] == task_id, "minutes_spent"].astype(int) - delta
                )
                tasks.loc[tasks["task_id"] == task_id, "minutes_spent"] = tasks.loc[
                    tasks["task_id"] == task_id, "minutes_spent"
                ].clip(lower=0)
                tasks.loc[tasks["task_id"] == task_id, "updated_at"] = now
                save_tasks(tasks, FILE_PATH)
                st.success(f"Subtracted {fmt_time(delta)}")
                st.rerun()

        if reset_clicked:
            now = datetime.now().isoformat(timespec="seconds")
            tasks.loc[tasks["task_id"] == task_id, "minutes_spent"] = 0
            tasks.loc[tasks["task_id"] == task_id, "updated_at"] = now
            save_tasks(tasks, FILE_PATH)
            st.success("Reset complete.")
            st.rerun()

        if delete_clicked:
            tasks = tasks[tasks["task_id"] != task_id].copy()
            save_tasks(tasks, FILE_PATH)
            st.success("Task deleted.")
            st.rerun()
