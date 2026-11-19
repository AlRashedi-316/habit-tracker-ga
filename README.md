# Habit Tracker

A simple, clean, and interactive Habit Tracker application built with Python and Streamlit. The application allows users to build positive routines, log daily completions, track streaks with visual celebrations, analyze performance trends, and manage accountability for missed habits.

---

## Demonstration

- **YouTube Video**: [Demonstration Link Placeholder](https://www.youtube.com)

---

## Features

The application features 5 dedicated navigation views:

1. **Add Habit**
   - Create new habits with customizable names, target frequencies (Daily/Weekly), numeric goals, categories (Health, Fitness, Learning, Mindfulness, Productivity, Other), and start dates.

2. **Log Habit**
   - Quick daily check-in with **Done** and **Not Done** buttons for all active habits.
   - Real-time streak tracking displaying consecutive completed days.
   - **Visual Reward System**: Automatically triggers congratulations and celebratory balloons (`st.balloons()`) when reaching 7 consecutive days on any habit.

3. **My Progress**
   - Interactive analytics powered by Plotly and Seaborn.
   - Metric filters for category selection and completion status.
   - Visualizations include overall completion gauge, Done vs. Not Done breakdown, records by category, current vs. best streaks, daily attendance trends, and a 30-day activity heatmap.

4. **Manage Habits**
   - Edit habit details or delete habits and their associated records.
   - CSV import/export loop with strict schema validation.
   - One-click presets: load starter habits or switch to the sample test dataset.

5. **Excuse Manager** *(Phase 3 Innovation)*
   - Dedicated accountability dashboard to track reasons behind missed habits.
   - Displays excuse history, identifying most frequently missed habits and common reasons over time.
   - Visualizes negative trends with a weekly missed habits chart to help users overcome friction and build consistency.

---

## Setup & Running in Streamlit

### Prerequisites
- Python 3.10 or higher installed.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/AlRashedi-316/habit-tracker-ga.git
   cd habit-tracker-ga
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Streamlit app**:
   ```bash
   streamlit run app.py
   ```

5. Open your web browser and navigate to `http://localhost:8501`.

---

## Data Management

The application stores data in standard long-format CSV files under the `data/` directory:

- `data/Habit.csv`: Primary dataset for user habits and daily records.
- `data/test_habits.csv`: Separate sample dataset populated with realistic history for testing and dashboard demonstration.

Use the dataset selector in the sidebar to switch between Actual and Test datasets. Switching to test data never overwrites or alters your actual habit data.
