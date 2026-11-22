# Habit Tracker

A clean, sequential Habit Tracker dashboard built with Python and Streamlit. It guides you from daily habit check-ins and streak celebrations through habit creation, management, visual progress analytics, and CSV-backed excuse accountability.

---

## Live App & Walkthrough Video

- **Live Deployed App:** [https://habit-tracker-ga.streamlit.app/](https://habit-tracker-ga.streamlit.app/)
- **Video Link:** [Demo Video](https://youtu.be/0QVEaMjWtb0)
- **What the Walkthrough Covers (2-minute tour):**
  1. Landing directly on **Log Habit** (default home page), triggering a 7-day streak `st.balloons()` celebration on *Drink Water*, and logging a **Not Done** habit with the inline excuse prompt.
  2. Creating a new habit on **Add Habit** with validation and preview.
  3. Editing, adding, or deleting habits in the interactive table and uploading/downloading CSVs on **Manage Habits**.
  4. Filtering **My Progress** with interactive category checkboxes and inspecting completion rates, bar/pie charts, streaks, and the 30-day attendance heatmap.
  5. Reviewing missed records, on-demand **Excuse History**, and excuse breakdown charts on **Excuse Manager**.

---

## Sequential Page Overview

The app flows sequentially across 5 pages from left-to-right / top-to-bottom in the sidebar:

1. **Log Habit (Default Home)**
   - Opens directly to your daily check-in dashboard with subtle category icons.
   - Clicking **Done** saves the completion to CSV, triggers celebratory `🎉` emoji rain (`streamlit-extras`), and shows your streak. Reaching a 7-day streak milestone (7, 14, 21, ...) triggers congratulatory balloons (`st.balloons()`).
   - Clicking **Not Done** immediately opens an inline excuse prompt to choose a predefined reason or enter a custom one before writing to CSV.
2. **Add Habit**
   - Create a habit with a unique name, category, frequency (`Daily` or `Weekly`), numeric goal, and start date, plus a `.head()` preview table of existing habits.
3. **Manage Habits**
   - Spreadsheet-style **Interactive Table** (`st.data_editor()`) to edit cells, add rows, or delete habits while preserving historical logs on rename.
   - Includes validated CSV upload and UTF-8 CSV download.
4. **My Progress**
   - Interactive category checkboxes and status radio buttons update all metrics and charts live.
   - Includes Overall Completion Rate + progress bar, Done vs. Not Done pie chart, Check-ins by Category bar chart, Current vs. Best Streak bar chart, and a 30-day interactive attendance heatmap (**Green = Attended / Red = Missed / Dark = Not Logged**).
5. **Excuse Manager (Phase 3 Innovation)**
   - Fetches missed check-ins (`Status == "Not Done"`) and logged excuses straight from the active CSV, showing summary KPIs, a `.head(5)` preview, and an on-demand **Excuse History** view.
   - Charts highlight **Most Missed Habits** and **Top Excuse Reasons**.

---

## Libraries Used

The application uses the following Python libraries (matching the imports in `app.py`):

- `streamlit` — Web interface, layout, forms, interactive table, metrics, and 7-day milestone balloons (`st.balloons()`)
- `streamlit-extras` — Fun `🎉` emoji rain (`let_it_rain.rain`) when checking off a daily habit
- `pandas` — CSV loading/saving, filtering, grouping, and `.head()` / `.pivot_table()` summaries
- `numpy` — Fast vectorized status encoding (`np.where`)
- `matplotlib` — Dark-mode figure styling and custom heatmap legend patches
- `seaborn` — 30-day attendance heatmap (`DD-MM` on X-axis, habits on Y-axis)
- `plotly` (`plotly.express`) — Interactive dark-mode pie and bar charts
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
   pip install -r requirements.txt
   ```

4. **Run the updated Streamlit app:**
   ```bash
   streamlit run app.py
   ```

5. Open `http://localhost:8501` in your browser.

---

## Testing `st.balloons()` & Data File

Data is loaded into `st.session_state["habits_df"]` for the active session and stored in `data/test_habits.csv` (`Habit,Category,Frequency,Goal,Start_Date,Date,Status,Excuse`), with CSV upload and UTF-8 download support.

### Quick `st.balloons()` Test Case
1. On **Log Habit**, set **Check-in Date** to `2026-11-20` (*Drink Water* already has a 6-day streak from `2026-11-14` to `2026-11-19`).
2. Click **Done** on **Drink Water** — it hits Day 7 and triggers the milestone banner and `st.balloons()`.
