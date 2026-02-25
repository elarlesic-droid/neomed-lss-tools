# Course Prep-to-Launch Checklist App

This Streamlit app provides a database-backed launch checklist for courses.

## What it does

- Stores course-specific launch checklist items in a local SQLite database.
- Lets users choose a course and see the correct checklist.
- Tracks two completion checkpoints for each row:
  - **Build Complete**
  - **QI Complete**
- Shows row-level status (`Not Started`, `In Progress`, `Ready`).
- Shows an overall readiness progress bar that updates as items are checked.
- Includes a **Program launched ✅ (reset checklist)** button to clear all checkboxes for the selected course.

## How to run locally

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the app:

   ```bash
   streamlit run streamlit_app.py
   ```

A SQLite file named `course_launch_checklist.db` is created automatically on first run.
