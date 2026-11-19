import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import datetime as dt

# ---------- constants ----------
REWARD_STREAK_DAYS = 7
DATA_FILE = "data/Habit.csv"
TEST_DATA_FILE = "data/test_habits.csv"

COL_HABIT, COL_CATEGORY, COL_FREQUENCY, COL_GOAL = "Habit", "Category", "Frequency", "Goal"
COL_START, COL_DATE, COL_STATUS, COL_EXCUSE = "Start_Date", "Date", "Status", "Excuse"
COLUMNS = [COL_HABIT, COL_CATEGORY, COL_FREQUENCY, COL_GOAL, COL_START, COL_DATE, COL_STATUS, COL_EXCUSE]
DEFINITION_COLUMNS = COLUMNS[:5]

STATUS_DONE, STATUS_NOT_DONE = "Done", "Not Done"
STATUS_FILTER_ALL = "All"
STATUS_FILTERS = [STATUS_FILTER_ALL, STATUS_DONE, STATUS_NOT_DONE]
STATUS_COLORS = {STATUS_DONE: "#2e9e5b", STATUS_NOT_DONE: "#d9534f"}

HABIT_CATEGORIES = ["Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"]
FREQUENCY_OPTIONS = ["Daily", "Weekly"]
PREDEFINED_HABITS = [
    {COL_HABIT: "Drink Water", COL_CATEGORY: "Health", COL_FREQUENCY: "Daily", COL_GOAL: 8},
    {COL_HABIT: "Exercise", COL_CATEGORY: "Fitness", COL_FREQUENCY: "Daily", COL_GOAL: 1},
    {COL_HABIT: "Read", COL_CATEGORY: "Learning", COL_FREQUENCY: "Daily", COL_GOAL: 1},
    {COL_HABIT: "Meditate", COL_CATEGORY: "Mindfulness", COL_FREQUENCY: "Daily", COL_GOAL: 1},
    {COL_HABIT: "Sleep Early", COL_CATEGORY: "Health", COL_FREQUENCY: "Daily", COL_GOAL: 1},
]

DATASET_ACTUAL, DATASET_TEST = "Actual data", "Test data"
PAGE_DASHBOARD, PAGE_MANAGE, PAGE_EXCUSES = "Dashboard", "Manage Tracker", "Excuse Manager"
PAGE_TITLES = {
    PAGE_DASHBOARD: "My Progress & Analytics",
    PAGE_MANAGE: "Add, Edit, Remove & CSV",
    PAGE_EXCUSES: "Missed Habits & Accountability",
}


# ---------- data layer ----------
def active_file():
    return TEST_DATA_FILE if st.session_state.get("dataset") == DATASET_TEST else DATA_FILE


def empty_frame():
    return pd.DataFrame(columns=COLUMNS)


def validate_frame(df):
    """Return a cleaned copy of df or raise ValueError describing the problem."""
    if list(df.columns) != COLUMNS:
        raise ValueError(f"Columns must be exactly: {', '.join(COLUMNS)}")
    df = df.fillna("").astype(str).reset_index(drop=True)
    for col in (COL_START, COL_DATE):
        filled = df[col] != ""
        parsed = pd.to_datetime(df.loc[filled, col], errors="coerce")
        if parsed.isna().any():
            raise ValueError(f"Invalid dates in column {col} (use YYYY-MM-DD).")
        df.loc[filled, col] = parsed.dt.strftime("%Y-%m-%d")
    if (df[COL_HABIT].str.strip() == "").any() or (df[COL_START] == "").any():
        raise ValueError("Every row needs a Habit name and a Start_Date.")
    goals = pd.to_numeric(df[COL_GOAL], errors="coerce")
    if goals.isna().any() or (goals < 1).any():
        raise ValueError("Goal must be a number of at least 1.")
    df[COL_GOAL] = goals.astype(int).astype(str)
    if not df[COL_STATUS].isin(["", STATUS_DONE, STATUS_NOT_DONE]).all():
        raise ValueError(f"Status must be empty, '{STATUS_DONE}' or '{STATUS_NOT_DONE}'.")
    if not df[COL_CATEGORY].isin(HABIT_CATEGORIES).all() or not df[COL_FREQUENCY].isin(FREQUENCY_OPTIONS).all():
        raise ValueError("Unknown Category or Frequency value.")
    if ((df[COL_DATE] == "") != (df[COL_STATUS] == "")).any():
        raise ValueError("Date and Status must both be filled or both empty.")
    return df


def load_data():
    try:
        return validate_frame(pd.read_csv(active_file(), dtype=str, keep_default_na=False))
    except FileNotFoundError:
        st.warning(f"{active_file()} not found. Starting with an empty tracker; it is created on first save.")
    except ValueError as e:  # includes parser, empty-file and unicode errors
        st.error(f"Could not read {active_file()}: {e}. Showing an empty tracker.")
    except OSError as e:
        st.error(f"Could not open {active_file()}: {e}")
    return empty_frame()


def save_data(df):
    try:
        df.to_csv(active_file(), index=False)
        return True
    except OSError as e:
        st.error(f"Could not save {active_file()}: {e}")
        return False


def habit_defs(df):
    return df.drop_duplicates(COL_HABIT)[DEFINITION_COLUMNS].reset_index(drop=True)


def log_rows(df):
    return df[df[COL_DATE] != ""]


def add_log(df, habit, day, status, excuse=""):
    """Replace the habit's log for that day (and its placeholder row) with a new log."""
    defs = habit_defs(df)
    row = defs[defs[COL_HABIT] == habit].iloc[0].to_dict()
    row.update({COL_DATE: day.isoformat(), COL_STATUS: status, COL_EXCUSE: excuse})
    stale = (df[COL_HABIT] == habit) & df[COL_DATE].isin(["", day.isoformat()])
    return pd.concat([df[~stale], pd.DataFrame([row])[COLUMNS]], ignore_index=True)


def get_streaks(df, habit, today):
    """(current, best) streak of consecutive Done days. Current counts only if last Done is today/yesterday."""
    done = log_rows(df)
    done = done[(done[COL_HABIT] == habit) & (done[COL_STATUS] == STATUS_DONE)]
    days = sorted(set(pd.to_datetime(done[COL_DATE]).dt.date))
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best, prev = max(best, run), d
    current = run if days and (today - days[-1]).days <= 1 else 0
    return current, best


def validate_habit_name(name, df, ignore=None):
    if not name:
        return "Habit name cannot be empty."
    taken = {h.lower() for h in df[COL_HABIT].unique() if h != ignore}
    if name.lower() in taken:
        return f"A habit named '{name}' already exists."
    return None


def placeholder_row(name, category, frequency, goal, start):
    return {COL_HABIT: name, COL_CATEGORY: category, COL_FREQUENCY: frequency, COL_GOAL: str(int(goal)),
            COL_START: start.isoformat(), COL_DATE: "", COL_STATUS: "", COL_EXCUSE: ""}


def show_chart(fig):
    st.plotly_chart(fig, width="stretch")


# ---------- pages ----------
def log_action(df, habit, day, status):
    if not save_data(add_log(df, habit, day, status)):
        return
    if status == STATUS_DONE:
        current, _ = get_streaks(add_log(df, habit, day, status), habit, dt.date.today())
        if current > 0 and current % REWARD_STREAK_DAYS == 0:
            st.session_state["reward"] = f"{current}-day streak on '{habit}'. Keep it going!"
    st.rerun()


def daily_logger(df, habits):
    st.subheader("Daily logger")
    day = st.date_input("Date", value=dt.date.today(), max_value=dt.date.today())
    active = habits[habits[COL_START] <= day.isoformat()]
    if active.empty:
        st.info("No habits are active on this date. Add one in Manage Tracker.")
    logs = log_rows(df)
    for name in active[COL_HABIT]:
        existing = logs[(logs[COL_HABIT] == name) & (logs[COL_DATE] == day.isoformat())][COL_STATUS]
        mark = f" ({existing.iloc[0]})" if len(existing) else ""
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.write(f"**{name}**{mark}")
        if c2.button("✅ Done", key=f"done_{name}"):
            log_action(df, name, day, STATUS_DONE)
        if c3.button("❌ Not Done", key=f"notdone_{name}"):
            log_action(df, name, day, STATUS_NOT_DONE)


def streak_section(df, habits):
    st.subheader("Streaks")
    today = dt.date.today()
    rows = []
    for name in habits[COL_HABIT]:
        current, best = get_streaks(df, name, today)
        rows.append({COL_HABIT: name, "Current": current, "Best": best})
    streaks = pd.DataFrame(rows, columns=[COL_HABIT, "Current", "Best"])
    hot = streaks[streaks["Current"] >= REWARD_STREAK_DAYS][COL_HABIT].tolist()
    if hot:
        st.success(f"{REWARD_STREAK_DAYS}+ day streak: " + ", ".join(hot))
    cols = st.columns(4)
    for i, r in streaks.iterrows():
        cols[i % 4].metric(r[COL_HABIT], f"{r['Current']} days", f"best {r['Best']}", delta_color="off")
    return streaks


def completion_heatmap(logs):
    last_day = pd.to_datetime(logs[COL_DATE]).max()
    recent = logs[pd.to_datetime(logs[COL_DATE]) > last_day - pd.Timedelta(days=30)].copy()
    recent["v"] = np.where(recent[COL_STATUS] == STATUS_DONE, 1, 0)
    grid = recent.pivot_table(index=COL_HABIT, columns=COL_DATE, values="v", aggfunc="max")
    grid.columns = [c[5:] for c in grid.columns]
    fig, ax = plt.subplots(figsize=(10, 0.5 * len(grid) + 1.5))
    sns.heatmap(grid, cmap=[STATUS_COLORS[STATUS_NOT_DONE], STATUS_COLORS[STATUS_DONE]], vmin=0, vmax=1,
                cbar=False, linewidths=0.5, ax=ax)
    ax.set_xlabel("Last 30 logged days (MM-DD): green done, red not done")
    ax.set_ylabel("")
    st.pyplot(fig)
    plt.close(fig)


def charts(df, habits, streaks):
    st.subheader("Analytics")
    c1, c2 = st.columns(2)
    categories = c1.multiselect("Categories", HABIT_CATEGORIES, default=HABIT_CATEGORIES)
    status = c2.radio("Show records", STATUS_FILTERS, horizontal=True)
    cat_logs = log_rows(df)
    cat_logs = cat_logs[cat_logs[COL_CATEGORY].isin(categories)]
    logs = cat_logs if status == STATUS_FILTER_ALL else cat_logs[cat_logs[COL_STATUS] == status]
    if logs.empty:
        st.info("No log records match these filters yet. Log a habit above.")
        return

    left, right = st.columns(2)
    rate = (cat_logs[COL_STATUS] == STATUS_DONE).mean() * 100
    gauge = go.Figure(go.Indicator(mode="gauge+number", value=round(rate, 1), number={"suffix": "%"},
                                   title={"text": "Overall completion rate"},
                                   gauge={"axis": {"range": [0, 100]}, "bar": {"color": STATUS_COLORS[STATUS_DONE]}}))
    with left:
        show_chart(gauge)
    counts = cat_logs[COL_STATUS].value_counts().reset_index()
    counts.columns = [COL_STATUS, "Count"]
    with right:
        show_chart(px.pie(counts, names=COL_STATUS, values="Count", color=COL_STATUS,
                          color_discrete_map=STATUS_COLORS, title="Done vs Not Done"))

    by_cat = logs.groupby([COL_CATEGORY, COL_STATUS]).size().reset_index(name="Count")
    show_chart(px.bar(by_cat, x=COL_CATEGORY, y="Count", color=COL_STATUS, barmode="group",
                      color_discrete_map=STATUS_COLORS, title="Records by category"))

    shown = streaks[streaks[COL_HABIT].isin(habits[habits[COL_CATEGORY].isin(categories)][COL_HABIT])]
    long = shown.melt(id_vars=COL_HABIT, var_name="Type", value_name="Days")
    show_chart(px.bar(long, x=COL_HABIT, y="Days", color="Type", barmode="group", title="Current vs best streak"))

    trend = logs.groupby([COL_DATE, COL_STATUS]).size().reset_index(name="Count").sort_values(COL_DATE)
    show_chart(px.line(trend, x=COL_DATE, y="Count", color=COL_STATUS, markers=True,
                       color_discrete_map=STATUS_COLORS, title="Daily attendance trend"))

    completion_heatmap(logs)
    with st.expander("Log records"):
        st.dataframe(logs.sort_values(COL_DATE, ascending=False), hide_index=True)


def page_dashboard():
    df = load_data()
    reward = st.session_state.pop("reward", None)
    if reward:
        st.success(reward)
        st.balloons()
    habits = habit_defs(df)
    if habits.empty:
        st.info("No habits yet. Add some in Manage Tracker or load the predefined habits.")
        return
    daily_logger(df, habits)
    streaks = streak_section(df, habits)
    charts(df, habits, streaks)


def switch_to_test():
    st.session_state["dataset"] = DATASET_TEST


def csv_section(df):
    st.subheader("CSV & predefined habits")
    if st.button("Load predefined habits"):
        known = {h.lower() for h in df[COL_HABIT]}
        rows = [placeholder_row(h[COL_HABIT], h[COL_CATEGORY], h[COL_FREQUENCY], h[COL_GOAL], dt.date.today())
                for h in PREDEFINED_HABITS if h[COL_HABIT].lower() not in known]
        if not rows:
            st.info("All predefined habits are already present.")
        elif save_data(pd.concat([df, pd.DataFrame(rows)[COLUMNS]], ignore_index=True)):
            st.rerun()
    st.button("Load sample test dataset", on_click=switch_to_test,
              help=f"Switches to the test dataset ({TEST_DATA_FILE}). Your actual data is untouched.")

    uploaded = st.file_uploader("Upload CSV (replaces the active dataset)", type="csv")
    if uploaded is not None:
        try:
            new = validate_frame(pd.read_csv(uploaded, dtype=str, keep_default_na=False))
            st.success(f"File is valid: {len(new)} rows, {new[COL_HABIT].nunique()} habits.")
            if st.button("Replace active dataset with uploaded file") and save_data(new):
                st.rerun()
        except ValueError as e:
            st.error(f"Upload rejected, existing data kept: {e}")
    try:
        st.download_button("Download current dataset", data=df.to_csv(index=False), file_name="habits.csv",
                           mime="text/csv")
    except (ValueError, OSError) as e:
        st.error(f"Could not prepare download: {e}")


def page_manage():
    df = load_data()
    st.subheader("Add a habit")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name")
        frequency = st.selectbox("Frequency", FREQUENCY_OPTIONS)
        goal = st.number_input("Goal (times per period)", min_value=1, value=1, step=1)
        category = st.selectbox("Category", HABIT_CATEGORIES)
        start = st.date_input("Start date", value=dt.date.today())
        if st.form_submit_button("Accept"):
            name = name.strip()
            error = validate_habit_name(name, df)
            if error:
                st.error(error)
            else:
                row = pd.DataFrame([placeholder_row(name, category, frequency, goal, start)])[COLUMNS]
                new = pd.concat([df, row], ignore_index=True)
                if save_data(new):
                    df = new
                    st.success(f"Added '{name}'.")

    st.subheader("Edit or remove a habit")
    habits = habit_defs(df)
    if habits.empty:
        st.info("No habits to edit yet.")
    else:
        habit = st.selectbox("Habit", habits[COL_HABIT])
        cur = habits[habits[COL_HABIT] == habit].iloc[0]
        with st.form("edit_form"):
            name = st.text_input("Name", value=habit, key=f"edit_name_{habit}")
            frequency = st.selectbox("Frequency", FREQUENCY_OPTIONS, index=FREQUENCY_OPTIONS.index(cur[COL_FREQUENCY]),
                                     key=f"edit_freq_{habit}")
            goal = st.number_input("Goal (times per period)", min_value=1, value=int(cur[COL_GOAL]), step=1,
                                   key=f"edit_goal_{habit}")
            category = st.selectbox("Category", HABIT_CATEGORIES, index=HABIT_CATEGORIES.index(cur[COL_CATEGORY]),
                                    key=f"edit_cat_{habit}")
            start = st.date_input("Start date", value=dt.date.fromisoformat(cur[COL_START]), key=f"edit_start_{habit}")
            if st.form_submit_button("Save changes"):
                name = name.strip()
                error = validate_habit_name(name, df, ignore=habit)
                if error:
                    st.error(error)
                else:
                    new = df.copy()
                    mask = new[COL_HABIT] == habit
                    new.loc[mask, COL_FREQUENCY] = frequency
                    new.loc[mask, COL_GOAL] = str(int(goal))
                    new.loc[mask, COL_CATEGORY] = category
                    new.loc[mask, COL_START] = start.isoformat()
                    new.loc[mask, COL_HABIT] = name
                    if save_data(new):
                        st.toast(f"Updated '{name}'.")
                        st.rerun()
        if st.button("Delete habit and all its logs"):
            if save_data(df[df[COL_HABIT] != habit]):
                st.toast(f"Deleted '{habit}'.")
                st.rerun()

    csv_section(df)


def page_excuses():
    df = load_data()
    habits = habit_defs(df)
    st.subheader("Log a missed habit")
    if habits.empty:
        st.info("No habits yet. Add one in Manage Tracker.")
    else:
        with st.form("excuse_form", clear_on_submit=True):
            habit = st.selectbox("Habit", habits[COL_HABIT])
            day = st.date_input("Date missed", value=dt.date.today(), max_value=dt.date.today())
            reason = st.text_input("Reason")
            if st.form_submit_button("Save excuse"):
                start = habits[habits[COL_HABIT] == habit][COL_START].iloc[0]
                if not reason.strip():
                    st.error("Please enter a reason.")
                elif day.isoformat() < start:
                    st.error(f"'{habit}' starts on {start}; pick a later date.")
                elif save_data(add_log(df, habit, day, STATUS_NOT_DONE, reason.strip())):
                    st.success("Excuse saved.")
                    df = load_data()

    missed = log_rows(df)
    missed = missed[missed[COL_STATUS] == STATUS_NOT_DONE]
    if missed.empty:
        st.info("No missed habits recorded yet.")
        return
    excused = missed[missed[COL_EXCUSE] != ""]
    st.subheader("Excuse history")
    if excused.empty:
        st.info("No excuses recorded yet.")
    else:
        st.dataframe(excused[[COL_DATE, COL_HABIT, COL_EXCUSE]].sort_values(COL_DATE, ascending=False),
                     hide_index=True)

    by_habit = missed[COL_HABIT].value_counts().reset_index()
    by_habit.columns = [COL_HABIT, "Misses"]
    show_chart(px.bar(by_habit, x=COL_HABIT, y="Misses", title="Most frequently missed habits"))

    if not excused.empty:
        by_excuse = excused[COL_EXCUSE].value_counts().reset_index()
        by_excuse.columns = [COL_EXCUSE, "Count"]
        show_chart(px.bar(by_excuse, x=COL_EXCUSE, y="Count", title="Most common excuses"))

    weekly = missed.assign(Week=pd.to_datetime(missed[COL_DATE]).dt.to_period("W").dt.start_time)
    weekly = weekly.groupby("Week").size().reset_index(name="Misses")
    show_chart(px.line(weekly, x="Week", y="Misses", markers=True, title="Misses per week"))


def main():
    st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")
    st.sidebar.radio("Dataset", [DATASET_ACTUAL, DATASET_TEST], key="dataset")
    st.sidebar.caption(f"Reading and writing: {active_file()}")
    page = st.sidebar.radio("Navigate", list(PAGE_TITLES))
    st.title(PAGE_TITLES[page])
    {PAGE_DASHBOARD: page_dashboard, PAGE_MANAGE: page_manage, PAGE_EXCUSES: page_excuses}[page]()


main()
