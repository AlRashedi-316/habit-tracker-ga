# ==============================================================================
# Habit Tracker Application
# Built using Python, Pandas, Matplotlib, Seaborn, Plotly, and Streamlit
# Concepts applied from our Python, Control Flow, EDA, and Data Viz modules
# ==============================================================================

# Libraries taught in our Python and Data Science course modules
import streamlit as st           # Streamlit library for building the web dashboard
import pandas as pd              # Pandas for dataframe manipulation (read_csv, groupby, pivot_table)
import numpy as np               # Numpy for numeric arrays and np.where conditions
import matplotlib.pyplot as plt  # Matplotlib for plotting and dark mode styling
import seaborn as sns            # Seaborn for heatmap visualization
import plotly.express as px      # Plotly Express for interactive visual charts
import datetime as dt            # Datetime for managing calendar dates and streaks

# Required columns for our habit tracker CSV dataset
required_column_names = [
    "Habit", "Category", "Frequency", "Goal", "Start_Date", "Date", "Status", "Excuse"
]

# Habit categories and frequencies as practiced in our data types / lists exercises
habit_category_choices = [
    "Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"
]
frequency_type_choices = ["Daily", "Weekly"]

# Predefined starter habits list of dictionaries (from Python dictionaries & lists lesson)
starter_habits_catalog = [
    {"Habit": "Drink Water", "Category": "Health", "Frequency": "Daily", "Goal": 8},
    {"Habit": "Exercise", "Category": "Fitness", "Frequency": "Daily", "Goal": 1},
    {"Habit": "Read", "Category": "Learning", "Frequency": "Daily", "Goal": 1},
    {"Habit": "Meditate", "Category": "Mindfulness", "Frequency": "Daily", "Goal": 1},
    {"Habit": "Sleep Early", "Category": "Health", "Frequency": "Daily", "Goal": 1},
]

# Color mapping dictionary for habit completion status
status_color_scheme = {"Done": "#2e9e5b", "Not Done": "#d9534f"}


# ==============================================================================
# Helper functions for data loading & saving (Error handling and Pandas file I/O)
# ==============================================================================

# Helper to determine whether we are using the test dataset or actual dataset
def fetch_target_file_path():
    # checking streamlit session state for the selected dataset
    if st.session_state.get("dataset_selection") == "Test data":
        return "data/test_habits.csv"
    return "data/Habit.csv"


# Function to load the CSV file into a pandas dataframe
def load_habit_data():
    chosen_file_path = fetch_target_file_path()
    try:
        # read csv with pandas as learned in Pandas EDA unit
        loaded_table = pd.read_csv(chosen_file_path, dtype=str)
        loaded_table = loaded_table.fillna("")
        
        # make sure every required column is present in the table
        for column_title in required_column_names:
            if column_title not in loaded_table.columns:
                loaded_table[column_title] = ""
                
        return loaded_table[required_column_names]
    except FileNotFoundError:
        # Error handling as covered in Errorhandling.ipynb
        st.warning(f"File {chosen_file_path} not found. Creating a new one upon first save.")
        return pd.DataFrame(columns=required_column_names)
    except Exception as general_error:
        # Catch other read exceptions and alert the user
        st.error(f"Error loading {chosen_file_path}: {general_error}")
        return pd.DataFrame(columns=required_column_names)


# Function to save our dataframe back to CSV
def save_habit_data(data_table_to_save):
    chosen_file_path = fetch_target_file_path()
    try:
        data_table_to_save.to_csv(chosen_file_path, index=False)
        return True
    except Exception as write_error:
        st.error(f"Could not save data to {chosen_file_path}: {write_error}")
        return False


# Function to extract unique habit definitions (without duplicate daily log rows)
def get_habit_definitions(current_habit_data):
    if current_habit_data.empty:
        return pd.DataFrame(columns=["Habit", "Category", "Frequency", "Goal", "Start_Date"])
    # drop duplicate habit names so we only see each unique habit
    distinct_habits = current_habit_data.drop_duplicates(subset=["Habit"])
    return distinct_habits[["Habit", "Category", "Frequency", "Goal", "Start_Date"]].reset_index(drop=True)


# Function to validate habit name (non-empty and not already taken)
def validate_habit_title(candidate_name, existing_data_table, current_editing_name=None):
    clean_candidate = candidate_name.strip()
    if not clean_candidate:
        return "Habit name cannot be empty."
    
    # list comprehension to check case-insensitive names from our Python lists lesson
    existing_lower_names = [
        single_name.lower()
        for single_name in existing_data_table["Habit"].unique()
        if single_name != current_editing_name
    ]
    if clean_candidate.lower() in existing_lower_names:
        return f"A habit named '{clean_candidate}' already exists!"
    return None


# ==============================================================================
# Streak calculations (Python loops & date math)
# ==============================================================================

# Function to calculate consecutive completed days for a habit
def compute_habit_streaks(habit_records_table, target_habit_name, reference_today_date):
    # filter rows where status is Done and date is not empty
    completed_habit_logs = habit_records_table[
        (habit_records_table["Habit"] == target_habit_name)
        & (habit_records_table["Status"] == "Done")
        & (habit_records_table["Date"] != "")
    ]
    if completed_habit_logs.empty:
        return 0, 0
    
    # parse date strings to date objects using pandas to_datetime
    sorted_unique_dates = (
        pd.to_datetime(completed_habit_logs["Date"])
        .dt.date.drop_duplicates()
        .sort_values()
        .tolist()
    )
    
    current_streak_count = 0
    longest_streak_record = 0
    running_streak_counter = 0
    previous_logged_date = None
    
    # loop through sorted dates using for loop (control flow lesson)
    for logged_day in sorted_unique_dates:
        if previous_logged_date is not None and (logged_day - previous_logged_date).days == 1:
            running_streak_counter += 1
        else:
            running_streak_counter = 1
            
        if running_streak_counter > longest_streak_record:
            longest_streak_record = running_streak_counter
            
        previous_logged_date = logged_day
        
    # check if streak is still active (logged today or yesterday)
    if sorted_unique_dates and (reference_today_date - sorted_unique_dates[-1]).days <= 1:
        current_streak_count = running_streak_counter
    else:
        current_streak_count = 0
        
    return current_streak_count, longest_streak_record


# ==============================================================================
# Add / Update logs (Pandas concatenation and row replacement)
# ==============================================================================

# Function to add or update a daily log entry
def record_habit_log(source_habit_table, habit_to_log, selected_calendar_date, status_outcome, excuse_text=""):
    formatted_date_string = str(selected_calendar_date)
    
    # find definition details for this habit
    matched_habit_definition = source_habit_table[source_habit_table["Habit"] == habit_to_log]
    if matched_habit_definition.empty:
        return source_habit_table
    base_habit_info = matched_habit_definition.iloc[0]
    
    # dictionary for the new check-in row
    fresh_log_dictionary = {
        "Habit": habit_to_log,
        "Category": base_habit_info["Category"],
        "Frequency": base_habit_info["Frequency"],
        "Goal": str(base_habit_info["Goal"]),
        "Start_Date": base_habit_info["Start_Date"],
        "Date": formatted_date_string,
        "Status": status_outcome,
        "Excuse": excuse_text,
    }
    
    # filter out old placeholder or duplicate log for this day
    remaining_records = source_habit_table[
        ~(
            (source_habit_table["Habit"] == habit_to_log)
            & (
                (source_habit_table["Date"] == formatted_date_string)
                | (source_habit_table["Date"] == "")
            )
        )
    ]
    
    # concat new entry with remaining records (from Pandas data merging lesson)
    updated_habit_table = pd.concat(
        [remaining_records, pd.DataFrame([fresh_log_dictionary])],
        ignore_index=True
    )
    return updated_habit_table


# ==============================================================================
# PAGE 1: ADD HABIT
# ==============================================================================

def render_add_habit_page():
    st.subheader("Create a New Habit")
    working_habit_data = load_habit_data()
    
    # Streamlit form for entering new habit information
    with st.form("new_habit_entry_form", clear_on_submit=True):
        typed_habit_name = st.text_input("Name")
        chosen_frequency = st.selectbox("Frequency", frequency_type_choices)
        numeric_target_goal = st.number_input(
            "Goal (times per period)", min_value=1, max_value=1000, value=1, step=1
        )
        chosen_category = st.selectbox("Category", habit_category_choices)
        picked_start_date = st.date_input("Start date", value=dt.date.today())
        
        form_submit_button = st.form_submit_button("Accept")
        
        if form_submit_button:
            validation_error = validate_habit_title(typed_habit_name, working_habit_data)
            if validation_error:
                st.error(validation_error)
            else:
                # create new habit row dictionary
                new_habit_row = {
                    "Habit": typed_habit_name.strip(),
                    "Category": chosen_category,
                    "Frequency": chosen_frequency,
                    "Goal": str(int(numeric_target_goal)),
                    "Start_Date": str(picked_start_date),
                    "Date": "",
                    "Status": "",
                    "Excuse": "",
                }
                expanded_habit_data = pd.concat(
                    [working_habit_data, pd.DataFrame([new_habit_row])],
                    ignore_index=True
                )
                if save_habit_data(expanded_habit_data):
                    st.success(f"Added '{typed_habit_name.strip()}' successfully! Go to Log Habit to start tracking.")


# ==============================================================================
# PAGE 2: LOG HABIT (Buttons, Streaks, and 7-Day Balloon Celebrations)
# ==============================================================================

def render_log_habit_page():
    working_habit_data = load_habit_data()
    
    # Streamlit reward celebration with balloons if 7-day milestone reached
    if "celebration_reward_message" in st.session_state:
        st.success(st.session_state.pop("celebration_reward_message"))
        st.balloons()
        
    unique_habits_catalog = get_habit_definitions(working_habit_data)
    if unique_habits_catalog.empty:
        st.info("No habits yet. Add one on the Add Habit page or load starter habits in Manage Habits.")
        return
        
    st.subheader("Daily Logger")
    calendar_today = dt.date.today()
    selected_log_date = st.date_input("Date", value=calendar_today, max_value=calendar_today)
    date_query_string = str(selected_log_date)
    
    # filter habits that started on or before the selected date
    eligible_active_habits = unique_habits_catalog[
        unique_habits_catalog["Start_Date"] <= date_query_string
    ]
    
    if eligible_active_habits.empty:
        st.info("No habits are active on this date. Add one on the Add Habit page.")
    else:
        # get today's logged entries from dataframe
        day_logged_records = working_habit_data[working_habit_data["Date"] == date_query_string]
        
        for row_index, single_habit_record in eligible_active_habits.iterrows():
            current_habit_title = single_habit_record["Habit"]
            existing_checkin = day_logged_records[day_logged_records["Habit"] == current_habit_title]
            status_indicator_text = ""
            if not existing_checkin.empty:
                status_indicator_text = f" ({existing_checkin.iloc[0]['Status']})"
                
            col_habit_title, col_done_action, col_notdone_action = st.columns([3, 1, 1])
            col_habit_title.write(f"**{current_habit_title}**{status_indicator_text}")
            
            # Button for marking Done
            if col_done_action.button("✅ Done", key=f"mark_done_{current_habit_title}"):
                modified_table = record_habit_log(
                    working_habit_data, current_habit_title, selected_log_date, "Done"
                )
                if save_habit_data(modified_table):
                    # compute streak to check for 7-day milestone celebration
                    active_streak, _ = compute_habit_streaks(
                        modified_table, current_habit_title, dt.date.today()
                    )
                    if active_streak > 0 and active_streak % 7 == 0:
                        st.session_state["celebration_reward_message"] = (
                            f"🔥 Congratulations! {active_streak}-day streak on '{current_habit_title}'! Keep it going!"
                        )
                    st.rerun()
                    
            # Button for marking Not Done
            if col_notdone_action.button("❌ Not Done", key=f"mark_notdone_{current_habit_title}"):
                modified_table = record_habit_log(
                    working_habit_data, current_habit_title, selected_log_date, "Not Done"
                )
                if save_habit_data(modified_table):
                    st.rerun()
                    
    # Streaks & Milestones section
    st.subheader("Streaks & Milestones")
    streak_rows_accumulator = []
    for habit_name_item in unique_habits_catalog["Habit"]:
        cur_streak, max_streak = compute_habit_streaks(
            working_habit_data, habit_name_item, calendar_today
        )
        streak_rows_accumulator.append({
            "Habit": habit_name_item,
            "Current": cur_streak,
            "Best": max_streak,
        })
    streak_summary_table = pd.DataFrame(streak_rows_accumulator)
    
    # Milestone banner for habits with 7 or more consecutive days
    achieved_milestone_habits = streak_summary_table[
        streak_summary_table["Current"] >= 7
    ]["Habit"].tolist()
    if achieved_milestone_habits:
        st.success(f"🔥 7+ day streak milestone achieved: {', '.join(achieved_milestone_habits)}")
        
    metrics_display_columns = st.columns(4)
    for col_counter, habit_streak_row in streak_summary_table.iterrows():
        metrics_display_columns[col_counter % 4].metric(
            habit_streak_row["Habit"],
            f"{habit_streak_row['Current']} days",
            f"best {habit_streak_row['Best']}",
            delta_color="off",
        )


# ==============================================================================
# PAGE 3: MY PROGRESS & ANALYTICS (with DARKMODE Heatmap & Plotly Charts)
# ==============================================================================

# Helper function to render 30-day attendance heatmap in DARKMODE using Matplotlib & Seaborn
def render_darkmode_attendance_heatmap(filtered_habit_logs):
    # filter logs to only the last 30 days
    maximum_logged_date = pd.to_datetime(filtered_habit_logs["Date"]).max()
    cutoff_threshold_date = maximum_logged_date - pd.Timedelta(days=30)
    recent_activity_logs = filtered_habit_logs[
        pd.to_datetime(filtered_habit_logs["Date"]) > cutoff_threshold_date
    ].copy()
    
    if recent_activity_logs.empty:
        return
        
    # np.where from numpy lesson to assign 1 for Done and 0 for Not Done
    recent_activity_logs["score_value"] = np.where(
        recent_activity_logs["Status"] == "Done", 1, 0
    )
    
    # pivot table as learned in Pandas EDA
    attendance_pivot_grid = recent_activity_logs.pivot_table(
        index="Habit",
        columns="Date",
        values="score_value",
        aggfunc="max",
    )
    # clean up column headers to display MM-DD
    attendance_pivot_grid.columns = [str(col_date_header)[5:] for col_date_header in attendance_pivot_grid.columns]
    
    # Set darkmode styling as taught in the data visualization unit (plt.style.use('dark_background'))
    plt.style.use('dark_background')
    heatmap_figure, heatmap_axes = plt.subplots(
        figsize=(10, max(2.5, 0.5 * len(attendance_pivot_grid) + 1.2))
    )
    
    # Seaborn heatmap with dark theme colors: red for missed, green for completed
    sns.heatmap(
        attendance_pivot_grid,
        cmap=[status_color_scheme["Not Done"], status_color_scheme["Done"]],
        vmin=0,
        vmax=1,
        cbar=False,
        linewidths=0.5,
        linecolor="#1f2328",
        ax=heatmap_axes,
    )
    
    heatmap_axes.set_title(
        "30-Day Attendance Grid (Dark Mode: Green = Done, Red = Missed)",
        color="white",
        fontsize=12,
        pad=10,
    )
    heatmap_axes.set_xlabel("Logged Date (MM-DD)", color="white")
    heatmap_axes.set_ylabel("")
    heatmap_axes.tick_params(colors="white", labelsize=9)
    heatmap_figure.patch.set_facecolor('#0e1117')  # Streamlit dark theme background color
    heatmap_axes.set_facecolor('#0e1117')
    
    # Streamlit display of matplotlib figure
    st.pyplot(heatmap_figure)
    plt.close(heatmap_figure)
    plt.style.use('default')  # reset style back


def render_progress_page():
    working_habit_data = load_habit_data()
    unique_habits_catalog = get_habit_definitions(working_habit_data)
    if unique_habits_catalog.empty:
        st.info("No habits yet. Add one on the Add Habit page or load starter habits in Manage Habits.")
        return
        
    st.subheader("Analytics & Trends")
    
    # Filter selection columns
    filter_left_col, filter_right_col = st.columns(2)
    selected_categories_list = filter_left_col.multiselect(
        "Categories", habit_category_choices, default=habit_category_choices
    )
    selected_status_filter = filter_right_col.radio(
        "Show records", ["All", "Done", "Not Done"], horizontal=True
    )
    
    # Filter out empty dates
    all_logged_records = working_habit_data[working_habit_data["Date"] != ""]
    category_filtered_records = all_logged_records[
        all_logged_records["Category"].isin(selected_categories_list)
    ]
    
    if selected_status_filter != "All":
        active_display_records = category_filtered_records[
            category_filtered_records["Status"] == selected_status_filter
        ]
    else:
        active_display_records = category_filtered_records
        
    if active_display_records.empty:
        st.info("No log records match these filters yet. Log your habits in Log Habit.")
        return
        
    # Top metrics and summary row
    metric_col_left, metric_col_right = st.columns(2)
    
    # Calculate overall completion rate
    total_completed_count = (category_filtered_records["Status"] == "Done").sum()
    total_eligible_logs = len(category_filtered_records)
    overall_completion_percentage = (
        (total_completed_count / total_eligible_logs * 100)
        if total_eligible_logs > 0
        else 0
    )
    
    with metric_col_left:
        st.metric(
            "Overall Completion Rate",
            f"{round(overall_completion_percentage, 1)}%",
            f"{total_completed_count} done out of {total_eligible_logs} logs",
        )
        # Streamlit progress bar component
        st.progress(min(max(overall_completion_percentage / 100, 0.0), 1.0))
        
    # Pie chart of status distribution using Plotly Express with dark template
    status_counts_summary = category_filtered_records["Status"].value_counts().reset_index()
    status_counts_summary.columns = ["Status", "Count"]
    
    status_pie_figure = px.pie(
        status_counts_summary,
        names="Status",
        values="Count",
        color="Status",
        color_discrete_map=status_color_scheme,
        title="Done vs Not Done",
        template="plotly_dark",
    )
    with metric_col_right:
        st.plotly_chart(status_pie_figure, use_container_width=True)
        
    # Grouped bar chart by category (Pandas groupby + Plotly Express)
    category_grouped_summary = (
        active_display_records.groupby(["Category", "Status"])
        .size()
        .reset_index(name="Count")
    )
    category_bar_figure = px.bar(
        category_grouped_summary,
        x="Category",
        y="Count",
        color="Status",
        barmode="group",
        color_discrete_map=status_color_scheme,
        title="Records by category",
        template="plotly_dark",
    )
    st.plotly_chart(category_bar_figure, use_container_width=True)
    
    # Streaks comparison chart
    calendar_today = dt.date.today()
    streaks_comparison_data = []
    filtered_habits_subset = unique_habits_catalog[
        unique_habits_catalog["Category"].isin(selected_categories_list)
    ]
    for single_title in filtered_habits_subset["Habit"]:
        streak_now, streak_top = compute_habit_streaks(
            working_habit_data, single_title, calendar_today
        )
        streaks_comparison_data.append({
            "Habit": single_title,
            "Current": streak_now,
            "Best": streak_top,
        })
    comparison_table = pd.DataFrame(streaks_comparison_data)
    if not comparison_table.empty:
        melted_comparison_table = comparison_table.melt(
            id_vars="Habit", var_name="Type", value_name="Days"
        )
        streaks_bar_figure = px.bar(
            melted_comparison_table,
            x="Habit",
            y="Days",
            color="Type",
            barmode="group",
            title="Current vs best streak",
            template="plotly_dark",
        )
        st.plotly_chart(streaks_bar_figure, use_container_width=True)
        
    # Daily attendance trend line chart
    daily_attendance_summary = (
        active_display_records.groupby(["Date", "Status"])
        .size()
        .reset_index(name="Count")
        .sort_values("Date")
    )
    daily_line_figure = px.line(
        daily_attendance_summary,
        x="Date",
        y="Count",
        color="Status",
        markers=True,
        color_discrete_map=status_color_scheme,
        title="Daily attendance trend",
        template="plotly_dark",
    )
    st.plotly_chart(daily_line_figure, use_container_width=True)
    
    # 30-Day Attendance Heatmap in Dark Mode
    render_darkmode_attendance_heatmap(active_display_records)
    
    with st.expander("Log records table"):
        st.dataframe(
            active_display_records.sort_values("Date", ascending=False),
            hide_index=True,
        )


# ==============================================================================
# PAGE 4: MANAGE HABITS & CSV IMPORT/EXPORT
# ==============================================================================

def render_manage_habits_page():
    working_habit_data = load_habit_data()
    unique_habits_catalog = get_habit_definitions(working_habit_data)
    
    st.subheader("Edit or Remove a Habit")
    if unique_habits_catalog.empty:
        st.info("No habits to edit yet.")
    else:
        chosen_habit_to_edit = st.selectbox("Habit", unique_habits_catalog["Habit"])
        active_habit_info_row = unique_habits_catalog[
            unique_habits_catalog["Habit"] == chosen_habit_to_edit
        ].iloc[0]
        
        # Form to edit habit details
        with st.form("modify_habit_form"):
            edited_name_input = st.text_input("Name", value=chosen_habit_to_edit)
            edited_frequency_selection = st.selectbox(
                "Frequency",
                frequency_type_choices,
                index=frequency_type_choices.index(active_habit_info_row["Frequency"]),
            )
            
            # safe conversion of goal to integer
            try:
                numeric_goal_value = int(active_habit_info_row["Goal"])
            except Exception:
                numeric_goal_value = 1
                
            edited_goal_input = st.number_input(
                "Goal (times per period)",
                min_value=1,
                max_value=1000,
                value=numeric_goal_value,
                step=1,
            )
            edited_category_selection = st.selectbox(
                "Category",
                habit_category_choices,
                index=habit_category_choices.index(active_habit_info_row["Category"]),
            )
            
            try:
                parsed_start_date_value = dt.date.fromisoformat(active_habit_info_row["Start_Date"])
            except Exception:
                parsed_start_date_value = dt.date.today()
                
            edited_start_date_input = st.date_input("Start date", value=parsed_start_date_value)
            
            save_changes_button = st.form_submit_button("Save changes")
            if save_changes_button:
                validation_alert = validate_habit_title(
                    edited_name_input,
                    working_habit_data,
                    current_editing_name=chosen_habit_to_edit,
                )
                if validation_alert:
                    st.error(validation_alert)
                else:
                    refreshed_habit_table = working_habit_data.copy()
                    matching_filter_mask = refreshed_habit_table["Habit"] == chosen_habit_to_edit
                    refreshed_habit_table.loc[matching_filter_mask, "Habit"] = edited_name_input.strip()
                    refreshed_habit_table.loc[matching_filter_mask, "Frequency"] = edited_frequency_selection
                    refreshed_habit_table.loc[matching_filter_mask, "Goal"] = str(int(edited_goal_input))
                    refreshed_habit_table.loc[matching_filter_mask, "Category"] = edited_category_selection
                    refreshed_habit_table.loc[matching_filter_mask, "Start_Date"] = str(edited_start_date_input)
                    
                    if save_habit_data(refreshed_habit_table):
                        st.toast(f"Updated '{edited_name_input.strip()}'!")
                        st.rerun()
                        
        # Delete habit button
        if st.button("Delete habit and all its logs"):
            remaining_habits_table = working_habit_data[
                working_habit_data["Habit"] != chosen_habit_to_edit
            ]
            if save_habit_data(remaining_habits_table):
                st.toast(f"Deleted '{chosen_habit_to_edit}'!")
                st.rerun()
                
    st.subheader("CSV & Predefined Habits")
    
    # Button to load starter habits
    if st.button("Load predefined habits"):
        existing_habits_set = set(working_habit_data["Habit"].str.lower())
        newly_added_rows = []
        for starter_dict in starter_habits_catalog:
            if starter_dict["Habit"].lower() not in existing_habits_set:
                newly_added_rows.append({
                    "Habit": starter_dict["Habit"],
                    "Category": starter_dict["Category"],
                    "Frequency": starter_dict["Frequency"],
                    "Goal": str(starter_dict["Goal"]),
                    "Start_Date": str(dt.date.today()),
                    "Date": "",
                    "Status": "",
                    "Excuse": "",
                })
        if not newly_added_rows:
            st.info("All predefined habits are already added!")
        else:
            merged_starter_table = pd.concat(
                [working_habit_data, pd.DataFrame(newly_added_rows)],
                ignore_index=True
            )
            if save_habit_data(merged_starter_table):
                st.rerun()
                
    # Button to switch to test dataset
    if st.button("Load sample test dataset"):
        st.session_state["dataset_selection"] = "Test data"
        st.rerun()
        
    # File uploader for CSV
    incoming_csv_file = st.file_uploader(
        "Upload CSV (replaces active dataset after validation)", type="csv"
    )
    if incoming_csv_file is not None:
        try:
            parsed_uploaded_table = pd.read_csv(incoming_csv_file, dtype=str).fillna("")
            if list(parsed_uploaded_table.columns) != required_column_names:
                st.error(f"Columns must be exactly: {', '.join(required_column_names)}")
            elif (parsed_uploaded_table["Habit"].str.strip() == "").any():
                st.error("Habit column cannot contain empty names.")
            else:
                st.success(
                    f"File is valid: {len(parsed_uploaded_table)} rows, "
                    f"{parsed_uploaded_table['Habit'].nunique()} habits."
                )
                if st.button("Replace active dataset with uploaded file"):
                    if save_habit_data(parsed_uploaded_table):
                        st.rerun()
        except Exception as upload_read_error:
            st.error(f"Upload rejected: {upload_read_error}")
            
    # Download dataset button
    st.download_button(
        "Download current dataset",
        data=working_habit_data.to_csv(index=False),
        file_name="habits.csv",
        mime="text/csv",
    )


# ==============================================================================
# PAGE 5: EXCUSE MANAGER (Accountability & Reason Tracking)
# ==============================================================================

def render_excuse_manager_page():
    working_habit_data = load_habit_data()
    unique_habits_catalog = get_habit_definitions(working_habit_data)
    
    st.subheader("Log a Missed Habit")
    if unique_habits_catalog.empty:
        st.info("No habits yet. Add one on the Add Habit page.")
    else:
        with st.form("missed_habit_excuse_form", clear_on_submit=True):
            selected_missed_habit = st.selectbox("Habit", unique_habits_catalog["Habit"])
            missed_date_selection = st.date_input(
                "Date missed", value=dt.date.today(), max_value=dt.date.today()
            )
            typed_excuse_reason = st.text_input("Reason")
            record_excuse_submit_btn = st.form_submit_button("Save excuse")
            
            if record_excuse_submit_btn:
                habit_start_date_string = unique_habits_catalog[
                    unique_habits_catalog["Habit"] == selected_missed_habit
                ]["Start_Date"].iloc[0]
                
                if not typed_excuse_reason.strip():
                    st.error("Please enter a reason.")
                elif str(missed_date_selection) < habit_start_date_string:
                    st.error(f"'{selected_missed_habit}' starts on {habit_start_date_string}; pick a later date.")
                else:
                    updated_missed_table = record_habit_log(
                        working_habit_data,
                        selected_missed_habit,
                        missed_date_selection,
                        "Not Done",
                        excuse_text=typed_excuse_reason.strip(),
                    )
                    if save_habit_data(updated_missed_table):
                        st.success("Excuse saved!")
                        working_habit_data = load_habit_data()
                        
    # Filter records that are marked Not Done and have a date
    recorded_misses_table = working_habit_data[
        (working_habit_data["Status"] == "Not Done")
        & (working_habit_data["Date"] != "")
    ]
    if recorded_misses_table.empty:
        st.info("No missed habits recorded yet.")
        return
        
    # Table of excuse history
    excuses_history_table = recorded_misses_table[recorded_misses_table["Excuse"] != ""]
    st.subheader("Excuse History")
    if excuses_history_table.empty:
        st.info("No excuses recorded yet.")
    else:
        st.dataframe(
            excuses_history_table[["Date", "Habit", "Excuse"]].sort_values("Date", ascending=False),
            hide_index=True,
        )
        
    # Bar chart: Most frequently missed habits (value_counts as taught in Pandas)
    habit_misses_counts = recorded_misses_table["Habit"].value_counts().reset_index()
    habit_misses_counts.columns = ["Habit", "Misses"]
    frequent_misses_figure = px.bar(
        habit_misses_counts,
        x="Habit",
        y="Misses",
        title="Most frequently missed habits",
        template="plotly_dark",
    )
    st.plotly_chart(frequent_misses_figure, use_container_width=True)
    
    # Bar chart: Most common excuses
    if not excuses_history_table.empty:
        common_excuses_counts = excuses_history_table["Excuse"].value_counts().reset_index()
        common_excuses_counts.columns = ["Excuse", "Count"]
        common_excuses_figure = px.bar(
            common_excuses_counts,
            x="Excuse",
            y="Count",
            title="Most common excuses",
            template="plotly_dark",
        )
        st.plotly_chart(common_excuses_figure, use_container_width=True)
        
    # Line chart: Weekly trend of misses
    try:
        weekly_trend_table = recorded_misses_table.copy()
        weekly_trend_table["Week"] = (
            pd.to_datetime(weekly_trend_table["Date"]).dt.to_period("W").dt.start_time
        )
        weekly_grouped_counts = (
            weekly_trend_table.groupby("Week").size().reset_index(name="Misses")
        )
        weekly_misses_line_figure = px.line(
            weekly_grouped_counts,
            x="Week",
            y="Misses",
            markers=True,
            title="Misses per week",
            template="plotly_dark",
        )
        st.plotly_chart(weekly_misses_line_figure, use_container_width=True)
    except Exception as weekly_calculation_error:
        st.write("Could not calculate weekly trend:", weekly_calculation_error)


# ==============================================================================
# Main app routing & entry point (Streamlit sidebar navigation & control flow)
# ==============================================================================

def main():
    # Streamlit page layout setup
    st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")
    
    # Sidebar dataset selector
    st.sidebar.radio("Dataset", ["Actual data", "Test data"], key="dataset_selection")
    active_dataset_file = fetch_target_file_path()
    st.sidebar.caption(f"Reading and writing: {active_dataset_file}")
    
    # Sidebar page navigation
    navigation_options_list = [
        "Add Habit", "Log Habit", "My Progress", "Manage Habits", "Excuse Manager"
    ]
    chosen_navigation_page = st.sidebar.radio("Navigate", navigation_options_list)
    
    # Routing with if/elif/else structure as learned in Python control flow
    if chosen_navigation_page == "Add Habit":
        st.title("Add a Habit")
        render_add_habit_page()
    elif chosen_navigation_page == "Log Habit":
        st.title("Log Habit")
        render_log_habit_page()
    elif chosen_navigation_page == "My Progress":
        st.title("My Progress & Analytics")
        render_progress_page()
    elif chosen_navigation_page == "Manage Habits":
        st.title("Edit, Remove & CSV")
        render_manage_habits_page()
    elif chosen_navigation_page == "Excuse Manager":
        st.title("Missed Habits & Accountability")
        render_excuse_manager_page()


if __name__ == "__main__":
    main()
