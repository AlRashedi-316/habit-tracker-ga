# Habit Tracker

A small Streamlit app for logging daily habits, tracking streaks, and looking at why you miss them.

Demo: <YouTube link placeholder>

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run it from the repo root: the app reads `data/Habit.csv` by relative path.

## Features

- **My Progress & Analytics**: log each habit Done or Not Done for a date, see current and best streaks, filter by category and status, and view completion gauge, Done vs Not Done, category, streak, trend charts and a heatmap. A 7-day streak triggers a celebration (balloons) and a streak banner.
- **Add, Edit, Remove & CSV**: add, edit (renames carry through logs) and delete habits, load predefined habits, switch to the sample test dataset, upload a validated CSV, download the current dataset.
- **Missed Habits & Accountability**: record why you missed a habit, browse the excuse history, and see most-missed habits, most common excuses and misses per week.

## Data

Both datasets are long-format CSVs with columns `Habit, Category, Frequency, Goal, Start_Date, Date, Status, Excuse`.

- `data/Habit.csv`: your real data, starts with five predefined habits.
- `data/test_habits.csv`: sample logs for trying the app. Choosing "Test data" in the sidebar reads and writes only this file, never `Habit.csv`.
