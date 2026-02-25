import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

DB_PATH = Path(__file__).with_name("course_launch_checklist.db")

DEFAULT_CHECKLISTS = {
    "LSS Yellow Belt": [
        "Finalize curriculum build",
        "Upload course materials",
        "Confirm instructor schedule",
        "Publish registration page",
        "Send learner welcome email",
    ],
    "LSS Green Belt": [
        "Review capstone requirements",
        "Validate LMS module links",
        "Assign coaching resources",
        "Open course enrollment",
        "Complete readiness communication",
    ],
    "QI Essentials": [
        "Review quality metrics",
        "Validate case studies",
        "Confirm evaluation forms",
        "Publish orientation module",
        "Send launch reminder",
    ],
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checklist_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_order INTEGER NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id),
                UNIQUE(course_id, item_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checklist_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                built_complete INTEGER NOT NULL DEFAULT 0,
                qi_complete INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                FOREIGN KEY (course_id) REFERENCES courses(id),
                FOREIGN KEY (template_id) REFERENCES checklist_templates(id),
                UNIQUE(course_id, template_id)
            )
            """
        )

        for course_name, items in DEFAULT_CHECKLISTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO courses(name) VALUES (?)",
                (course_name,),
            )
            course_id = conn.execute(
                "SELECT id FROM courses WHERE name = ?",
                (course_name,),
            ).fetchone()["id"]

            for item_order, item_name in enumerate(items, start=1):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO checklist_templates(course_id, item_name, item_order)
                    VALUES (?, ?, ?)
                    """,
                    (course_id, item_name, item_order),
                )

        conn.commit()


def fetch_courses() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT id, name FROM courses ORDER BY name").fetchall()


def ensure_status_rows(course_id: int) -> None:
    with get_connection() as conn:
        templates = conn.execute(
            "SELECT id FROM checklist_templates WHERE course_id = ?",
            (course_id,),
        ).fetchall()

        for template in templates:
            conn.execute(
                """
                INSERT OR IGNORE INTO checklist_status(course_id, template_id, built_complete, qi_complete)
                VALUES (?, ?, 0, 0)
                """,
                (course_id, template["id"]),
            )

        conn.commit()


def fetch_course_checklist(course_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                t.id AS template_id,
                t.item_name,
                COALESCE(s.built_complete, 0) AS built_complete,
                COALESCE(s.qi_complete, 0) AS qi_complete
            FROM checklist_templates t
            LEFT JOIN checklist_status s
                ON s.template_id = t.id
                AND s.course_id = t.course_id
            WHERE t.course_id = ?
            ORDER BY t.item_order
            """,
            (course_id,),
        ).fetchall()


def update_check_item(course_id: int, template_id: int, field: str, value: bool) -> None:
    if field not in {"built_complete", "qi_complete"}:
        return

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE checklist_status
            SET {field} = ?, updated_at = ?
            WHERE course_id = ? AND template_id = ?
            """,
            (int(value), datetime.utcnow().isoformat(timespec="seconds"), course_id, template_id),
        )
        conn.commit()


def reset_course_checklist(course_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE checklist_status
            SET built_complete = 0,
                qi_complete = 0,
                updated_at = ?
            WHERE course_id = ?
            """,
            (datetime.utcnow().isoformat(timespec="seconds"), course_id),
        )
        conn.commit()


def status_label(built_complete: bool, qi_complete: bool) -> str:
    if built_complete and qi_complete:
        return "✅ Ready"
    if built_complete or qi_complete:
        return "🟡 In Progress"
    return "⚪ Not Started"


def handle_checkbox_change(course_id: int, template_id: int, key: str, field: str) -> None:
    update_check_item(course_id, template_id, field, bool(st.session_state[key]))


def main() -> None:
    st.set_page_config(page_title="Course Launch Checklist", page_icon="✅", layout="wide")
    st.title("Course Prep-to-Launch Tracker")
    st.write(
        "Select a course, complete each build and QI check-off, and track readiness with an overall status bar."
    )

    initialize_database()

    courses = fetch_courses()
    if not courses:
        st.error("No courses were found in the database.")
        return

    selected_name = st.selectbox("Course to prepare", [course["name"] for course in courses])
    selected_course_id = next(course["id"] for course in courses if course["name"] == selected_name)

    ensure_status_rows(selected_course_id)
    checklist_rows = fetch_course_checklist(selected_course_id)

    if st.button("Program launched ✅ (reset checklist)", type="primary"):
        reset_course_checklist(selected_course_id)
        for row in checklist_rows:
            st.session_state[f"built_{selected_course_id}_{row['template_id']}"] = False
            st.session_state[f"qi_{selected_course_id}_{row['template_id']}"] = False
        st.success("Checklist reset for the next launch cycle.")
        st.rerun()

    if not checklist_rows:
        st.warning("No checklist items are configured for this course.")
        return

    total_checks = len(checklist_rows) * 2
    completed_checks = 0

    header = st.columns([4, 2, 2, 2])
    header[0].markdown("**Checklist Item**")
    header[1].markdown("**Status**")
    header[2].markdown("**Build Complete**")
    header[3].markdown("**QI Complete**")

    st.divider()

    for row in checklist_rows:
        template_id = row["template_id"]
        built_key = f"built_{selected_course_id}_{template_id}"
        qi_key = f"qi_{selected_course_id}_{template_id}"

        if built_key not in st.session_state:
            st.session_state[built_key] = bool(row["built_complete"])
        if qi_key not in st.session_state:
            st.session_state[qi_key] = bool(row["qi_complete"])

        built_value = bool(st.session_state[built_key])
        qi_value = bool(st.session_state[qi_key])
        completed_checks += int(built_value) + int(qi_value)

        cols = st.columns([4, 2, 2, 2])
        cols[0].write(row["item_name"])
        cols[1].write(status_label(built_value, qi_value))
        cols[2].checkbox(
            "Built",
            key=built_key,
            label_visibility="collapsed",
            on_change=handle_checkbox_change,
            args=(selected_course_id, template_id, built_key, "built_complete"),
        )
        cols[3].checkbox(
            "QI",
            key=qi_key,
            label_visibility="collapsed",
            on_change=handle_checkbox_change,
            args=(selected_course_id, template_id, qi_key, "qi_complete"),
        )

    progress = completed_checks / total_checks if total_checks else 0
    st.divider()
    st.progress(progress, text=f"Overall launch readiness: {progress * 100:.0f}%")


if __name__ == "__main__":
    main()
