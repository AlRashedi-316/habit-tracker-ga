# Habit Tracker

A clean, sequential Habit Tracker dashboard built with Python and Streamlit. It guides you from daily habit check-ins and streak celebrations through habit creation, management, visual progress analytics, and CSV-backed excuse accountability.

---

## Live App & Walkthrough Video

- **Live Deployed App:** [https://habit-tracker-ga.streamlit.app/](https://habit-tracker-ga.streamlit.app/)
- **Video Link:** [Walkthrough Video (Placeholder)](https://www.youtube.com)
- **What the Walkthrough Covers (2-minute tour):**
  1. Landing directly on **Log Habit** (default home page), previewing the test dataset, triggering a 7-day streak `st.balloons()` celebration on *Drink Water*, and logging a **Not Done** habit with the inline excuse prompt.
  2. Creating a new habit on **Add Habit** with validation and preview.
  3. Selecting and updating or deleting a habit sequentially on **Manage Habits**.
  4. Filtering **My Progress** with interactive category checkboxes and inspecting the 30-day attendance heatmap with its Green/Red visual legend.
  5. Reviewing missed records, on-demand **Excuse History**, habit-specific missed dates, and storytelling charts on **Excuse Manager**.

> *Note: Any AI-generated images or visuals used in accompanying slides or presentation materials are explicitly labeled as AI-generated.*

---

## Sequential Page Overview

The app flows sequentially across 5 pages from left-to-right / top-to-bottom in the sidebar:

1. **Log Habit (Default Home)**
   - Opens directly to your daily check-in dashboard with subtle category icons.
   - Clicking **Done** saves the completion to CSV and displays responsive feedback with your live streak count. Reaching a 7-day streak milestone (7, 14, 21, ...) triggers congratulatory balloons (`st.balloons()`).
   - Clicking **Not Done** immediately opens an inline excuse prompt to choose a predefined reason or enter a custom one before writing to CSV.
2. **Add Habit**
   - Create a habit with a unique name, category, frequency (`Daily` or `Weekly`), numeric goal, and start date, plus a `.head()` preview table of existing habits.
3. **Manage Habits**
   - Organized into two tabs: **Edit by Habit** (sequential habit-first dropdown to inspect metrics, edit, or delete) and **Interactive Table** (`st.data_editor()` spreadsheet-style editing with full validation).
   - Includes a quick button to switch to test data, validated CSV upload, and UTF-8 CSV download.
4. **My Progress**
   - Interactive category checkboxes and status radio buttons update all metrics and charts live.
   - Includes a completion progress bar, Done vs. Not Done breakdown, category comparison, current vs. best streaks, daily attendance trend, and a 30-day attendance heatmap with a visual **Green = Attended / Red = Missed / Dark = Not Logged** legend.
5. **Excuse Manager**
   - Fetches missed check-ins (`Status == "Not Done"`) and logged excuses straight from the active CSV, showing summary KPIs, a `.head(5)` preview, and an on-demand **Excuse History** view.
   - Lets you pick a habit to review its missed dates and add or update an excuse.
   - Storytelling charts highlight which habits are missed most often, top excuse reasons, weekly trends, and day-of-week patterns.

---

## Libraries Used

The application uses the following Python libraries (matching the imports in `app.py`):

- `streamlit` — Web interface, layout, forms, metrics, and celebrations (`st.balloons()`)
- `pandas` — CSV loading/saving, filtering, grouping, and `.head()` / `.pivot_table()` summaries
- `numpy` — Fast vectorized status encoding (`np.where`)
- `matplotlib` — Figure styling and custom heatmap legend patches
- `seaborn` — 30-day attendance heatmap visualization
- `plotly` (`plotly.express`) — Interactive dark-mode pie, bar, and line charts
- `datetime` *(Python standard library)* — Date picking, streak calculations, and date validation

---

## Setup & Running Locally

### Prerequisites
- Python 3.10 or higher

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AlRashedi-316/habit-tracker-ga.git
   cd habit-tracker-ga
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. **Install the libraries:**
   ```bash
   pip install streamlit pandas numpy matplotlib seaborn plotly
   ```

4. **Run the updated Streamlit app:**
   ```bash
   streamlit run app.py
   ```

5. Open `http://localhost:8501` in your browser.

---

## Testing `st.balloons()` & Data Files

Data is loaded into `st.session_state["habits_df"]` for the active session and stored in long-format CSV files inside `data/` (`Habit,Category,Frequency,Goal,Start_Date,Date,Status,Excuse`), with CSV upload and UTF-8 download support:

- `data/Habit.csv` — Primary personal dataset (starts empty; use **Add Habit** to begin).
- `data/test_habits.csv` — Sample history for testing dashboards and demonstrating milestones.

### Quick 3-Step `st.balloons()` Test Case
1. On **Log Habit**, select **Test data** in the sidebar (or click **Preview with Test Data**).
2. Make sure **Check-in Date** is set to `2026-11-20` (*Drink Water* already has a 6-day streak from `2026-11-14` to `2026-11-19`).
3. Click **Done** on **Drink Water** — it hits Day 7 and triggers the milestone banner and `st.balloons()`.
