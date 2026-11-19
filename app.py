# ==============================================================================
# HABIT TRACKER APP
# Built with: Streamlit, Pandas, Plotly Express, Matplotlib & Seaborn
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. IMPORTS (From our Python & Data Science course modules)
# ------------------------------------------------------------------------------
import streamlit as st           # Web interface widgets and layout
import pandas as pd              # Data tables, CSV loading, filtering, grouping
import numpy as np               # Number calculations (np.where)
import matplotlib.pyplot as plt  # Matplotlib for dark mode plot styles
import seaborn as sns            # Seaborn for drawing the attendance heatmap
import plotly.express as px      # Plotly Express for dark mode interactive charts
import datetime as dt            # Datetime for managing calendar dates and streaks


# ------------------------------------------------------------------------------
# 2. CONFIGURATION & CONSTANTS
# ------------------------------------------------------------------------------
# All 8 columns expected in our CSV file
columns = [
    "Habit",        # Name of the habit (e.g. Drink Water)
    "Category",     # Group (Health, Fitness, etc.)
    "Frequency",    # Daily or Weekly
    "Goal",         # Target count per day/week
    "Start_Date",   # When the habit begins (YYYY-MM-DD)
    "Date",         # Log date for daily check-ins
    "Status",       # Done or Not Done
    "Excuse",       # Reason why it was missed (optional)
]

# Available dropdown options
categories = ["Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"]
frequencies = ["Daily", "Weekly"]

# Predefined starter habits for brand-new users
starter_habits = [
    {"Habit": "Drink Water", "Category": "Health", "Frequency": "Daily", "Goal": 8},
    {"Habit": "Exercise", "Category": "Fitness", "Frequency": "Daily", "Goal": 1},
    {"Habit": "Read", "Category": "Learning", "Frequency": "Daily", "Goal": 1},
    {"Habit": "Meditate", "Category": "Mindfulness", "Frequency": "Daily", "Goal": 1},
    {"Habit": "Sleep Early", "Category": "Health", "Frequency": "Daily", "Goal": 1},
]

# Chart colors: green for completed, red for missed
status_colors = {
    "Done": "#2e9e5b",
    "Not Done": "#d9534f"
}


# ==============================================================================
# 3. HELPER FUNCTIONS (DATA LOADING, SAVING & STREAKS)
# ==============================================================================

# Helper to find which CSV file path to use (Actual vs Test)
def get_file():
    if st.session_state.get("dataset") == "Test data":
        return "data/test_habits.csv"
    return "data/Habit.csv"


# Load data from the CSV file into a pandas dataframe
def load_data():
    file_path = get_file()
    try:
        # Read CSV file using pandas read_csv
        tracker = pd.read_csv(file_path, dtype=str)
        tracker = tracker.fillna("")
        
        # Ensure every required column exists in the dataframe
        for col_name in columns:
            if col_name not in tracker.columns:
                tracker[col_name] = ""
                
        return tracker[columns]
        
    except FileNotFoundError:
        # If the file does not exist yet, show a friendly warning and return an empty table
        st.warning(f"File '{file_path}' not found. Starting with a blank tracker.")
        return pd.DataFrame(columns=columns)
        
    except Exception as error:
        # Catch any other reading error
        st.error(f"Error loading {file_path}: {error}")
        return pd.DataFrame(columns=columns)


# Save the dataframe back to the CSV file
def save_data(table):
    file_path = get_file()
    try:
        table.to_csv(file_path, index=False)
        return True
    except Exception as error:
        st.error(f"Error saving to {file_path}: {error}")
        return False


# Extract unique habits (one row per habit, without the daily logs)
def get_habits(table):
    if table.empty:
        return pd.DataFrame(columns=["Habit", "Category", "Frequency", "Goal", "Start_Date"])
    
    # Drop duplicate habit names to see each habit only once
    unique_habits = table.drop_duplicates(subset=["Habit"])
    return unique_habits[["Habit", "Category", "Frequency", "Goal", "Start_Date"]].reset_index(drop=True)


# Validate that a habit name is not empty and not already taken
def check_name(name, table, editing=None):
    clean_name = name.strip()
    
    # Check if user left the text input empty
    if not clean_name:
        return "Habit name cannot be empty."
        
    # Check if name is already taken (case-insensitive)
    taken_names = [h.lower() for h in table["Habit"].unique() if h != editing]
    if clean_name.lower() in taken_names:
        return f"A habit named '{clean_name}' already exists!"
        
    return None


# Calculate current streak and best streak using for loop over dates
def get_streaks(table, habit_name, today_date):
    # Step 1: Filter rows where this habit was marked as Done
    done_records = table[
        (table["Habit"] == habit_name) & 
        (table["Status"] == "Done") & 
        (table["Date"] != "")
    ]
    if done_records.empty:
        return 0, 0
    
    # Step 2: Get a sorted list of unique completed dates
    dates = pd.to_datetime(done_records["Date"]).dt.date.drop_duplicates().sort_values().tolist()
    
    current_streak = 0
    best_streak = 0
    streak_counter = 0
    prev_date = None
    
    # Step 3: Loop through dates and check if consecutive
    for logged_day in dates:
        if prev_date is not None and (logged_day - prev_date).days == 1:
            streak_counter += 1
        else:
            streak_counter = 1
            
        if streak_counter > best_streak:
            best_streak = streak_counter
            
        prev_date = logged_day
        
    # Step 4: Check if streak is still active (logged today or yesterday)
    if dates and (today_date - dates[-1]).days <= 1:
        current_streak = streak_counter
    else:
        current_streak = 0
        
    return current_streak, best_streak


# Add or update a daily check-in log for a habit
def add_log(table, habit_name, log_date, status, excuse=""):
    date_str = str(log_date)
    
    # Step 1: Find the habit definition details
    matched = table[table["Habit"] == habit_name]
    if matched.empty:
        return table
    habit_info = matched.iloc[0]
    
    # Step 2: Create dictionary for the new log entry
    new_entry = {
        "Habit": habit_name,
        "Category": habit_info["Category"],
        "Frequency": habit_info["Frequency"],
        "Goal": str(habit_info["Goal"]),
        "Start_Date": habit_info["Start_Date"],
        "Date": date_str,
        "Status": status,
        "Excuse": excuse,
    }
    
    # Step 3: Remove any previous log for this habit on this date (or empty placeholder)
    filtered_table = table[
        ~(
            (table["Habit"] == habit_name) & 
            ((table["Date"] == date_str) | (table["Date"] == ""))
        )
    ]
    
    # Step 4: Append the new entry using pd.concat
    updated_table = pd.concat([filtered_table, pd.DataFrame([new_entry])], ignore_index=True)
    return updated_table


# Render 30-day attendance heatmap in dark mode using Seaborn
def show_heatmap(records):
    # Step 1: Filter records to the last 30 logged days
    last_date = pd.to_datetime(records["Date"]).max()
    start_date = last_date - pd.Timedelta(days=30)
    recent = records[pd.to_datetime(records["Date"]) > start_date].copy()
    if recent.empty:
        return
        
    # Step 2: Use np.where (1 for Done, 0 for Not Done)
    recent["val"] = np.where(recent["Status"] == "Done", 1, 0)
    
    # Step 3: Pivot table with habits as rows and dates as columns
    grid = recent.pivot_table(index="Habit", columns="Date", values="val", aggfunc="max")
    grid.columns = [str(c)[5:] for c in grid.columns]  # show MM-DD
    
    # Step 4: Apply dark background style from matplotlib
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, max(2.5, 0.5 * len(grid) + 1.2)))
    
    # Step 5: Draw heatmap with red for missed and green for done
    sns.heatmap(
        grid,
        cmap=[status_colors["Not Done"], status_colors["Done"]],
        vmin=0,
        vmax=1,
        cbar=False,
        linewidths=0.5,
        linecolor="#1f2328",
        ax=ax,
    )
    ax.set_title("30-Day Attendance Grid (Green = Done, Red = Missed)", color="white", fontsize=12, pad=10)
    ax.set_xlabel("Date (MM-DD)", color="white")
    ax.set_ylabel("")
    ax.tick_params(colors="white")
    fig.patch.set_facecolor('#0e1117')
    ax.set_facecolor('#0e1117')
    
    st.pyplot(fig)
    plt.close(fig)
    plt.style.use('default')  # Reset style back to default


# ==============================================================================
# 4. PAGE 1: ADD A HABIT
# ==============================================================================

def page_add():
    st.subheader("Create a New Habit")
    habits_data = load_data()
    
    # Form for adding a new habit
    with st.form("add_form", clear_on_submit=True):
        name_input = st.text_input("Name", placeholder="e.g. Morning Walk")
        freq_input = st.selectbox("Frequency", frequencies)
        goal_input = st.number_input("Goal (times per period)", min_value=1, max_value=1000, value=1, step=1)
        cat_input = st.selectbox("Category", categories)
        start_input = st.date_input("Start date", value=dt.date.today())
        
        submit_btn = st.form_submit_button("Accept")
        
        if submit_btn:
            # Check name validity
            name_error = check_name(name_input, habits_data)
            if name_error:
                st.error(name_error)
            else:
                # Build dictionary for the new habit
                new_habit = {
                    "Habit": name_input.strip(),
                    "Category": cat_input,
                    "Frequency": freq_input,
                    "Goal": str(int(goal_input)),
                    "Start_Date": str(start_input),
                    "Date": "",
                    "Status": "",
                    "Excuse": "",
                }
                new_table = pd.concat([habits_data, pd.DataFrame([new_habit])], ignore_index=True)
                if save_data(new_table):
                    st.success(f"Added '{name_input.strip()}'! Go to Log Habit to start tracking.")


# ==============================================================================
# 5. PAGE 2: LOG HABIT (CHECK-INS & STREAKS)
# ==============================================================================

def page_log():
    habits_data = load_data()
    
    # Reward celebration: balloons when reaching multiples of 7 days
    if "reward" in st.session_state:
        st.success(st.session_state.pop("reward"))
        st.balloons()
        
    habit_list = get_habits(habits_data)
    if habit_list.empty:
        st.info("No habits yet. Add one on the Add Habit page or load starter habits in Manage Habits.")
        return
        
    # --- Section: Daily Logger ---
    st.subheader("Daily Logger")
    today = dt.date.today()
    picked_date = st.date_input("Date", value=today, max_value=today)
    date_str = str(picked_date)
    
    # Filter habits that started on or before the chosen date
    active_habits = habit_list[habit_list["Start_Date"] <= date_str]
    if active_habits.empty:
        st.info("No habits are active on this date. Add one on the Add Habit page.")
    else:
        # Get existing logs for this date
        day_logs = habits_data[habits_data["Date"] == date_str]
        
        for idx, row in active_habits.iterrows():
            habit_name = row["Habit"]
            existing = day_logs[day_logs["Habit"] == habit_name]
            mark = ""
            if not existing.empty:
                mark = f" ({existing.iloc[0]['Status']})"
                
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.write(f"**{habit_name}**{mark}")
            
            # Button: Mark Done
            if col2.button("✅ Done", key=f"done_{habit_name}"):
                updated = add_log(habits_data, habit_name, picked_date, "Done")
                if save_data(updated):
                    # Check streak for 7-day reward
                    cur, _ = get_streaks(updated, habit_name, dt.date.today())
                    if cur > 0 and cur % 7 == 0:
                        st.session_state["reward"] = f"🔥 {cur}-day streak on '{habit_name}'! Great job!"
                    st.rerun()
                    
            # Button: Mark Not Done
            if col3.button("❌ Not Done", key=f"notdone_{habit_name}"):
                updated = add_log(habits_data, habit_name, picked_date, "Not Done")
                if save_data(updated):
                    st.rerun()
                    
    # --- Section: Streaks & Milestones ---
    st.subheader("Streaks & Milestones")
    streak_rows = []
    for h in habit_list["Habit"]:
        c, b = get_streaks(habits_data, h, today)
        streak_rows.append({"Habit": h, "Current": c, "Best": b})
    streak_table = pd.DataFrame(streak_rows)
    
    # Milestone banner for habits with 7 or more consecutive days
    hot_habits = streak_table[streak_table["Current"] >= 7]["Habit"].tolist()
    if hot_habits:
        st.success(f"🔥 7+ day streak milestone achieved: {', '.join(hot_habits)}")
        
    metrics_cols = st.columns(4)
    for i, r in streak_table.iterrows():
        metrics_cols[i % 4].metric(
            r["Habit"],
            f"{r['Current']} days",
            f"best {r['Best']}",
            delta_color="off"
        )


# ==============================================================================
# 6. PAGE 3: MY PROGRESS (CHARTS & DARK MODE HEATMAP)
# ==============================================================================

def page_progress():
    habits_data = load_data()
    habit_list = get_habits(habits_data)
    if habit_list.empty:
        st.info("No habits yet. Add one on the Add Habit page or load starter habits in Manage Habits.")
        return
        
    st.subheader("Analytics & Trends")
    
    # --- Filter Controls ---
    col_cat, col_stat = st.columns(2)
    chosen_cats = col_cat.multiselect("Categories", categories, default=categories)
    chosen_status = col_stat.radio("Show records", ["All", "Done", "Not Done"], horizontal=True)
    
    # Filter log records
    records = habits_data[habits_data["Date"] != ""]
    cat_records = records[records["Category"].isin(chosen_cats)]
    
    if chosen_status != "All":
        filtered_records = cat_records[cat_records["Status"] == chosen_status]
    else:
        filtered_records = cat_records
        
    if filtered_records.empty:
        st.info("No log records match these filters yet. Log your habits in Log Habit.")
        return
        
    # --- Row 1: Overall Completion Rate & Pie Chart ---
    left_col, right_col = st.columns(2)
    
    done_count = (cat_records["Status"] == "Done").sum()
    total_count = len(cat_records)
    rate = (done_count / total_count * 100) if total_count > 0 else 0
    
    with left_col:
        st.metric("Overall Completion Rate", f"{round(rate, 1)}%", f"{done_count} done out of {total_count} logs")
        st.progress(min(max(rate / 100, 0.0), 1.0))
        
    # Pie chart with dark theme
    status_counts = cat_records["Status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    pie_chart = px.pie(
        status_counts,
        names="Status",
        values="Count",
        color="Status",
        color_discrete_map=status_colors,
        title="Done vs Not Done",
        template="plotly_dark",
    )
    with right_col:
        st.plotly_chart(pie_chart, use_container_width=True)
        
    # --- Row 2: Records by Category (Grouped Bar Chart) ---
    by_category = filtered_records.groupby(["Category", "Status"]).size().reset_index(name="Count")
    bar_category = px.bar(
        by_category,
        x="Category",
        y="Count",
        color="Status",
        barmode="group",
        color_discrete_map=status_colors,
        title="Records by category",
        template="plotly_dark",
    )
    st.plotly_chart(bar_category, use_container_width=True)
    
    # --- Row 3: Current vs Best Streak Chart ---
    today = dt.date.today()
    streaks_list = []
    filtered_habits = habit_list[habit_list["Category"].isin(chosen_cats)]
    for h in filtered_habits["Habit"]:
        c, b = get_streaks(habits_data, h, today)
        streaks_list.append({"Habit": h, "Current": c, "Best": b})
    streak_df = pd.DataFrame(streaks_list)
    if not streak_df.empty:
        melted_streaks = streak_df.melt(id_vars="Habit", var_name="Type", value_name="Days")
        streak_bar = px.bar(
            melted_streaks,
            x="Habit",
            y="Days",
            color="Type",
            barmode="group",
            title="Current vs best streak",
            template="plotly_dark",
        )
        st.plotly_chart(streak_bar, use_container_width=True)
        
    # --- Row 4: Daily Attendance Trend (Line Chart) ---
    daily_trend = filtered_records.groupby(["Date", "Status"]).size().reset_index(name="Count").sort_values("Date")
    line_chart = px.line(
        daily_trend,
        x="Date",
        y="Count",
        color="Status",
        markers=True,
        color_discrete_map=status_colors,
        title="Daily attendance trend",
        template="plotly_dark",
    )
    st.plotly_chart(line_chart, use_container_width=True)
    
    # --- Row 5: 30-Day Attendance Heatmap (Dark Mode) ---
    show_heatmap(filtered_records)
    
    # --- Data Table Expander ---
    with st.expander("View log records table"):
        st.dataframe(filtered_records.sort_values("Date", ascending=False), hide_index=True)


# ==============================================================================
# 7. PAGE 4: MANAGE HABITS (EDIT, DELETE & CSV)
# ==============================================================================

def page_manage():
    habits_data = load_data()
    habit_list = get_habits(habits_data)
    
    # --- Section: Edit or Remove a Habit ---
    st.subheader("Edit or Remove a Habit")
    if habit_list.empty:
        st.info("No habits to edit yet.")
    else:
        chosen_habit = st.selectbox("Habit", habit_list["Habit"])
        habit_row = habit_list[habit_list["Habit"] == chosen_habit].iloc[0]
        
        # Form to edit habit details
        with st.form("edit_form"):
            new_name = st.text_input("Name", value=chosen_habit)
            new_freq = st.selectbox("Frequency", frequencies, index=frequencies.index(habit_row["Frequency"]))
            
            try:
                current_goal = int(habit_row["Goal"])
            except Exception:
                current_goal = 1
            new_goal = st.number_input("Goal (times per period)", min_value=1, max_value=1000, value=current_goal, step=1)
            new_cat = st.selectbox("Category", categories, index=categories.index(habit_row["Category"]))
            
            try:
                start_date = dt.date.fromisoformat(habit_row["Start_Date"])
            except Exception:
                start_date = dt.date.today()
            new_start = st.date_input("Start date", value=start_date)
            
            save_changes = st.form_submit_button("Save changes")
            if save_changes:
                name_error = check_name(new_name, habits_data, editing=chosen_habit)
                if name_error:
                    st.error(name_error)
                else:
                    updated = habits_data.copy()
                    mask = updated["Habit"] == chosen_habit
                    updated.loc[mask, "Habit"] = new_name.strip()
                    updated.loc[mask, "Frequency"] = new_freq
                    updated.loc[mask, "Goal"] = str(int(new_goal))
                    updated.loc[mask, "Category"] = new_cat
                    updated.loc[mask, "Start_Date"] = str(new_start)
                    if save_data(updated):
                        st.toast(f"Updated '{new_name.strip()}'!")
                        st.rerun()
                        
        # Button: Delete Habit
        if st.button("Delete habit and all its logs"):
            remaining = habits_data[habits_data["Habit"] != chosen_habit]
            if save_data(remaining):
                st.toast(f"Deleted '{chosen_habit}'!")
                st.rerun()
                
    # --- Section: CSV & Predefined Habits ---
    st.subheader("CSV & Predefined Habits")
    
    # Button: Load Predefined Starter Habits
    if st.button("Load predefined habits"):
        existing_names = set(habits_data["Habit"].str.lower())
        new_items = []
        for starter in starter_habits:
            if starter["Habit"].lower() not in existing_names:
                new_items.append({
                    "Habit": starter["Habit"],
                    "Category": starter["Category"],
                    "Frequency": starter["Frequency"],
                    "Goal": str(starter["Goal"]),
                    "Start_Date": str(dt.date.today()),
                    "Date": "",
                    "Status": "",
                    "Excuse": "",
                })
        if not new_items:
            st.info("All predefined habits are already added!")
        else:
            combined = pd.concat([habits_data, pd.DataFrame(new_items)], ignore_index=True)
            if save_data(combined):
                st.rerun()
                
    # Button: Switch to Sample Test Dataset
    if st.button("Load sample test dataset"):
        st.session_state["dataset"] = "Test data"
        st.rerun()
        
    # File Uploader: Upload CSV to replace active dataset
    uploaded_file = st.file_uploader("Upload CSV (replaces active dataset after validation)", type="csv")
    if uploaded_file is not None:
        try:
            uploaded_df = pd.read_csv(uploaded_file, dtype=str).fillna("")
            if list(uploaded_df.columns) != columns:
                st.error(f"Columns must be exactly: {', '.join(columns)}")
            elif (uploaded_df["Habit"].str.strip() == "").any():
                st.error("Habit column cannot contain empty names.")
            else:
                st.success(f"File is valid: {len(uploaded_df)} rows, {uploaded_df['Habit'].nunique()} habits.")
                if st.button("Replace active dataset with uploaded file"):
                    if save_data(uploaded_df):
                        st.rerun()
        except Exception as error:
            st.error(f"Upload rejected: {error}")
            
    # Download Button: Export current dataset as CSV
    st.download_button(
        "Download current dataset",
        data=habits_data.to_csv(index=False),
        file_name="habits.csv",
        mime="text/csv",
    )


# ==============================================================================
# 8. PAGE 5: EXCUSE MANAGER (ACCOUNTABILITY FOR MISSED HABITS)
# ==============================================================================

def page_excuses():
    habits_data = load_data()
    habit_list = get_habits(habits_data)
    
    # --- Section: Log a Missed Habit Form ---
    st.subheader("Log a Missed Habit")
    if habit_list.empty:
        st.info("No habits yet. Add one on the Add Habit page.")
    else:
        with st.form("excuse_form", clear_on_submit=True):
            chosen_missed = st.selectbox("Habit", habit_list["Habit"])
            missed_day = st.date_input("Date missed", value=dt.date.today(), max_value=dt.date.today())
            reason_text = st.text_input("Reason", placeholder="e.g. Felt sick, busy at work")
            save_excuse = st.form_submit_button("Save excuse")
            
            if save_excuse:
                start_date_str = habit_list[habit_list["Habit"] == chosen_missed]["Start_Date"].iloc[0]
                if not reason_text.strip():
                    st.error("Please enter a reason.")
                elif str(missed_day) < start_date_str:
                    st.error(f"'{chosen_missed}' starts on {start_date_str}; pick a later date.")
                else:
                    updated = add_log(habits_data, chosen_missed, missed_day, "Not Done", excuse=reason_text.strip())
                    if save_data(updated):
                        st.success("Excuse saved!")
                        habits_data = load_data()
                        
    # Filter for all missed records (Status == 'Not Done' and non-empty Date)
    missed_records = habits_data[(habits_data["Status"] == "Not Done") & (habits_data["Date"] != "")]
    if missed_records.empty:
        st.info("No missed habits recorded yet.")
        return
        
    # --- Section: Excuse History Table ---
    excuse_table = missed_records[missed_records["Excuse"] != ""]
    st.subheader("Excuse History")
    if excuse_table.empty:
        st.info("No excuses recorded yet.")
    else:
        st.dataframe(
            excuse_table[["Date", "Habit", "Excuse"]].sort_values("Date", ascending=False),
            hide_index=True,
        )
        
    # --- Chart: Most Frequently Missed Habits ---
    missed_counts = missed_records["Habit"].value_counts().reset_index()
    missed_counts.columns = ["Habit", "Misses"]
    chart_missed = px.bar(
        missed_counts,
        x="Habit",
        y="Misses",
        title="Most frequently missed habits",
        template="plotly_dark",
    )
    st.plotly_chart(chart_missed, use_container_width=True)
    
    # --- Chart: Most Common Excuses ---
    if not excuse_table.empty:
        common_excuses = excuse_table["Excuse"].value_counts().reset_index()
        common_excuses.columns = ["Excuse", "Count"]
        chart_excuses = px.bar(
            common_excuses,
            x="Excuse",
            y="Count",
            title="Most common excuses",
            template="plotly_dark",
        )
        st.plotly_chart(chart_excuses, use_container_width=True)
        
    # --- Chart: Weekly Misses Trend ---
    try:
        weekly = missed_records.copy()
        weekly["Week"] = pd.to_datetime(weekly["Date"]).dt.to_period("W").dt.start_time
        weekly_counts = weekly.groupby("Week").size().reset_index(name="Misses")
        chart_weekly = px.line(
            weekly_counts,
            x="Week",
            y="Misses",
            markers=True,
            title="Misses per week",
            template="plotly_dark",
        )
        st.plotly_chart(chart_weekly, use_container_width=True)
    except Exception as error:
        st.write("Could not calculate weekly trend:", error)


# ==============================================================================
# 9. MAIN APP ENTRY POINT & SIDEBAR ROUTING
# ==============================================================================

def main():
    # Configure the browser tab title and wide layout
    st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")
    
    # --- Sidebar: Dataset Selector (Actual data vs Test data) ---
    st.sidebar.radio("Dataset", ["Actual data", "Test data"], key="dataset")
    active_file = get_file()
    st.sidebar.caption(f"Reading and writing: {active_file}")
    
    # --- Sidebar: 5-Page Navigation ---
    pages = ["Add Habit", "Log Habit", "My Progress", "Manage Habits", "Excuse Manager"]
    page = st.sidebar.radio("Navigate", pages)
    
    # --- Page Routing (Control Flow) ---
    if page == "Add Habit":
        st.title("Add a Habit")
        page_add()
    elif page == "Log Habit":
        st.title("Log Habit")
        page_log()
    elif page == "My Progress":
        st.title("My Progress & Analytics")
        page_progress()
    elif page == "Manage Habits":
        st.title("Edit, Remove & CSV")
        page_manage()
    elif page == "Excuse Manager":
        st.title("Missed Habits & Accountability")
        page_excuses()


# Run the application
if __name__ == "__main__":
    main()
