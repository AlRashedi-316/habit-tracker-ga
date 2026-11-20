# Habit Tracker
# Built with Streamlit, Pandas, NumPy, Matplotlib, Seaborn, Plotly Express, and datetime

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import datetime as dt

# Configure browser tab title, icon, and wide page layout (must run first)
st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")


# --- Constants & Configuration ---

# Exact 8 columns stored in our long-format CSV files
columns = [
    "Habit",
    "Category",
    "Frequency",
    "Goal",
    "Start_Date",
    "Date",
    "Status",
    "Excuse",
]

# Dropdown and filter options used across the app
categories = ["Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"]
frequencies = ["Daily", "Weekly"]
predefined_excuses = ["Forgot", "Too tired", "Sick", "Ran out of time", "Bad weather"]

# Subtle category icons for daily check-in rows
category_icons = {
    "Health": "💧",
    "Fitness": "🏃",
    "Learning": "📖",
    "Mindfulness": "🧘",
    "Productivity": "⚡",
    "Other": "📌",
}

# Shared chart color palette: green for completed, red for missed
status_colors = {
    "Done": "#2e9e5b",
    "Not Done": "#d9534f",
}

# Sequential navigation order starting on the default Log Habit landing page
pages = ["Log Habit", "Add Habit", "Manage Habits", "My Progress", "Excuse Manager"]


# --- Data & Helper Functions ---

# Return the active CSV path based on the sidebar dataset selector
def get_file():
    if st.session_state.get("dataset") == "Test data":
        return "data/test_habits.csv"
    return "data/Habit.csv"


# Read the active CSV into a pandas DataFrame and guarantee the 8 expected columns
def load_data():
    file_path = get_file()
    try:
        # Read all columns as strings so blank cells and dates stay consistent
        tracker_table = pd.read_csv(file_path, dtype=str)
        # Replace missing values with empty strings to simplify text filtering
        tracker_table = tracker_table.fillna("")

        # Add any missing expected columns if the CSV is incomplete
        for column_name in columns:
            if column_name not in tracker_table.columns:
                tracker_table[column_name] = ""

        # Return columns in standard order
        return tracker_table[columns]

    except FileNotFoundError:
        # Friendly fallback if the CSV file has not been created yet
        st.warning(f"File '{file_path}' not found. Starting with an empty tracker.")
        return pd.DataFrame(columns=columns)

    except Exception as error:
        # Catch unexpected read errors without crashing the app
        st.error(f"Error loading {file_path}: {error}")
        return pd.DataFrame(columns=columns)


# Save the DataFrame into session state first, then persist to the local CSV file
def save_data(habits_table):
    clean_table = habits_table[columns].reset_index(drop=True).copy()
    # Always keep the active session DataFrame up to date across reruns
    st.session_state["habits_df"] = clean_table
    # Bump editor version so st.data_editor reflects updates made elsewhere
    st.session_state["table_editor_version"] = (
        st.session_state.get("table_editor_version", 0) + 1
    )

    file_path = get_file()
    try:
        clean_table.to_csv(file_path, index=False)
    except Exception as error:
        # Keep session state working even if the hosting environment blocks disk writes
        st.warning(
            f"Saved changes in this session, but could not write to '{file_path}': {error}. "
            "Use Download CSV in Manage Habits to keep a local backup."
        )
    return True


# Extract one metadata row per unique habit definition
def get_habits(habits_table):
    habit_columns = ["Habit", "Category", "Frequency", "Goal", "Start_Date"]
    if habits_table.empty:
        return pd.DataFrame(columns=habit_columns)

    # Keep the first occurrence of each habit name to build the master list
    unique_habits = habits_table.drop_duplicates(subset=["Habit"])
    return unique_habits[habit_columns].reset_index(drop=True)


# Validate that a habit name is non-empty and not already taken
def check_name(habit_name, habits_table, editing_habit=None):
    clean_name = habit_name.strip()

    # Reject blank names
    if not clean_name:
        return "Habit name cannot be empty."

    # Compare lowercase names while allowing the habit currently being edited
    taken_names = [
        existing_habit.lower()
        for existing_habit in habits_table["Habit"].unique()
        if existing_habit != editing_habit
    ]
    if clean_name.lower() in taken_names:
        return f"A habit named '{clean_name}' already exists."

    return None


# Calculate current streak (up to reference_date) and all-time best streak for one habit
def get_streaks(habits_table, habit_name, reference_date):
    # Filter only completed check-ins that have a non-empty date
    done_records = habits_table[
        (habits_table["Habit"] == habit_name)
        & (habits_table["Status"] == "Done")
        & (habits_table["Date"] != "")
    ]
    if done_records.empty:
        return 0, 0

    # Parse dates safely, drop invalid strings, remove duplicates, and sort oldest -> newest
    parsed_dates = pd.to_datetime(done_records["Date"], errors="coerce").dropna()
    if parsed_dates.empty:
        return 0, 0
    sorted_dates = parsed_dates.dt.date.drop_duplicates().sort_values().tolist()

    # Walk through all completed dates to find the longest consecutive run
    best_streak = 0
    run_count = 0
    previous_date = None
    for logged_day in sorted_dates:
        if previous_date is not None and (logged_day - previous_date).days == 1:
            run_count += 1
        else:
            run_count = 1
        if run_count > best_streak:
            best_streak = run_count
        previous_date = logged_day

    # Keep only dates up to reference_date so streak checks match the selected check-in day
    dates_up_to_reference = [
        done_date for done_date in sorted_dates if done_date <= reference_date
    ]
    current_streak = 0

    # Streak is active if completed on reference_date or the day before reference_date
    if dates_up_to_reference and (reference_date - dates_up_to_reference[-1]).days <= 1:
        current_streak = 1
        # Count backwards while consecutive days differ by exactly 1 day
        for day_index in range(len(dates_up_to_reference) - 2, -1, -1):
            if (
                dates_up_to_reference[day_index + 1]
                - dates_up_to_reference[day_index]
            ).days == 1:
                current_streak += 1
            else:
                break

    return current_streak, best_streak


# Add or overwrite a habit log for a specific date and save any excuse text
def add_log(habits_table, habit_name, log_date, status, excuse=""):
    date_text = str(log_date)

    # Look up the habit's Category, Frequency, Goal, and Start_Date from existing rows
    matched_rows = habits_table[habits_table["Habit"] == habit_name]
    if matched_rows.empty:
        return habits_table
    habit_info = matched_rows.iloc[0]

    # Build the new long-format row dictionary
    new_entry = {
        "Habit": habit_name,
        "Category": habit_info["Category"],
        "Frequency": habit_info["Frequency"],
        "Goal": str(habit_info["Goal"]),
        "Start_Date": habit_info["Start_Date"],
        "Date": date_text,
        "Status": status,
        "Excuse": excuse,
    }

    # Remove any prior log for this habit on this date, plus any blank placeholder row
    filtered_table = habits_table[
        ~(
            (habits_table["Habit"] == habit_name)
            & ((habits_table["Date"] == date_text) | (habits_table["Date"] == ""))
        )
    ]

    # Append the new row using pd.concat and reset row indexing
    updated_table = pd.concat(
        [filtered_table, pd.DataFrame([new_entry])], ignore_index=True
    )
    return updated_table


# Validate edits from st.data_editor and apply additions, updates, and deletions safely
def apply_table_edits(
    habits_table, edited_habits, original_names, deleted_positions=None
):
    validation_errors = []
    seen_habit_names = set()
    cleaned_rows = []
    deleted_set = set(deleted_positions or [])

    # Exclude deleted row positions so a newly added row reusing an index never inherits old logs
    active_original_names = {
        original_index: original_habit
        for position, (original_index, original_habit) in enumerate(
            original_names.items()
        )
        if position not in deleted_set
    }

    # Validate each row returned by the data editor before modifying any data
    for row_position, (row_index, row_data) in enumerate(
        edited_habits.iterrows(), start=1
    ):
        # Convert potentially missing cells to clean stripped strings
        raw_habit = row_data.get("Habit", "")
        clean_habit = "" if pd.isna(raw_habit) else str(raw_habit).strip()

        raw_category = row_data.get("Category", "")
        clean_category = "" if pd.isna(raw_category) else str(raw_category).strip()

        raw_frequency = row_data.get("Frequency", "")
        clean_frequency = "" if pd.isna(raw_frequency) else str(raw_frequency).strip()

        # Parse numeric goal and start date safely (invalid inputs turn into NaN / NaT)
        raw_goal = row_data.get("Goal", "")
        goal_number = pd.to_numeric(raw_goal, errors="coerce")

        raw_start_date = row_data.get("Start_Date", "")
        parsed_start = (
            pd.NaT
            if pd.isna(raw_start_date) or str(raw_start_date).strip() == ""
            else pd.to_datetime(raw_start_date, errors="coerce")
        )

        # Reject blank habit names or duplicates (case-insensitive)
        if not clean_habit:
            validation_errors.append(f"Row {row_position}: Habit name cannot be empty.")
        elif clean_habit.lower() in seen_habit_names:
            validation_errors.append(
                f"Row {row_position}: Duplicate habit name '{clean_habit}'."
            )
        else:
            seen_habit_names.add(clean_habit.lower())

        # Make sure dropdown columns match allowed Category and Frequency options
        if clean_category not in categories:
            validation_errors.append(
                f"Row {row_position}: Please choose a valid Category."
            )

        if clean_frequency not in frequencies:
            validation_errors.append(
                f"Row {row_position}: Please choose a valid Frequency."
            )

        # Require Goal to be a whole number from 1 to 1000
        if (
            pd.isna(goal_number)
            or (goal_number % 1) != 0
            or goal_number < 1
            or goal_number > 1000
        ):
            validation_errors.append(
                f"Row {row_position}: Goal must be a whole number between 1 and 1000."
            )

        # Require a valid date for Start_Date
        if pd.isna(parsed_start):
            validation_errors.append(
                f"Row {row_position}: Please enter a valid Start Date."
            )

        # Store normalized values when the row passes all checks
        if not validation_errors:
            cleaned_rows.append(
                {
                    "row_index": row_index,
                    "Habit": clean_habit,
                    "Category": clean_category,
                    "Frequency": clean_frequency,
                    "Goal": str(int(goal_number)),
                    "Start_Date": parsed_start.strftime("%Y-%m-%d"),
                }
            )

    # Stop early and return all collected error messages if any row was invalid
    if validation_errors:
        return None, validation_errors

    # Rebuild the full long-format table so existing check-in logs stay attached to updated habits
    rebuilt_frames = []
    for clean_row in cleaned_rows:
        row_index = clean_row["row_index"]
        # Existing rows keep all their historical Date/Status/Excuse logs with updated metadata
        if row_index in active_original_names:
            previous_name = active_original_names[row_index]
            matching_logs = habits_table[
                habits_table["Habit"] == previous_name
            ].copy()
            if not matching_logs.empty:
                matching_logs["Habit"] = clean_row["Habit"]
                matching_logs["Category"] = clean_row["Category"]
                matching_logs["Frequency"] = clean_row["Frequency"]
                matching_logs["Goal"] = clean_row["Goal"]
                matching_logs["Start_Date"] = clean_row["Start_Date"]
                rebuilt_frames.append(matching_logs)
                continue

        # Brand-new habits added directly inside the table start with one empty log row
        rebuilt_frames.append(
            pd.DataFrame(
                [
                    {
                        "Habit": clean_row["Habit"],
                        "Category": clean_row["Category"],
                        "Frequency": clean_row["Frequency"],
                        "Goal": clean_row["Goal"],
                        "Start_Date": clean_row["Start_Date"],
                        "Date": "",
                        "Status": "",
                        "Excuse": "",
                    }
                ]
            )
        )

    # Return an empty schema DataFrame if all rows were removed
    if not rebuilt_frames:
        return pd.DataFrame(columns=columns), []

    updated_table = pd.concat(rebuilt_frames, ignore_index=True)
    return updated_table[columns], []


# Draw a reliable 30-day dark-mode attendance heatmap with a visual color legend
def show_heatmap(records):
    # Work on a copy and parse Date safely so malformed values never break the pivot
    heatmap_records = records.copy()
    heatmap_records["parsed_date"] = pd.to_datetime(
        heatmap_records["Date"], errors="coerce"
    )
    heatmap_records = heatmap_records.dropna(subset=["parsed_date"])
    heatmap_records = heatmap_records[
        heatmap_records["Status"].isin(["Done", "Not Done"])
    ]

    if heatmap_records.empty:
        st.info(
            "No dated check-in records are available for the heatmap with the current filters."
        )
        return

    # Use a 30-day inclusive window ending at the most recent logged date
    last_date = heatmap_records["parsed_date"].max()
    start_date = last_date - pd.Timedelta(days=29)
    recent_records = heatmap_records[
        heatmap_records["parsed_date"] >= start_date
    ].copy()

    if recent_records.empty:
        st.info("No check-in records fall inside the 30-day heatmap window.")
        return

    # Convert Status into numeric float values (1.0 = Done, 0.0 = Not Done)
    recent_records["status_code"] = np.where(
        recent_records["Status"] == "Done", 1.0, 0.0
    )

    # Pivot into a Habit x Date grid, keeping the highest status if duplicate dates exist
    attendance_grid = recent_records.pivot_table(
        index="Habit", columns="parsed_date", values="status_code", aggfunc="max"
    )

    # Guard against empty grids on edge-case filtered inputs
    if (
        attendance_grid.empty
        or attendance_grid.shape[0] == 0
        or attendance_grid.shape[1] == 0
    ):
        st.info("Not enough data to draw the attendance heatmap.")
        return

    # Sort date columns chronologically and format labels as MM-DD
    attendance_grid = attendance_grid.sort_index(axis=1)
    attendance_grid.columns = [
        date_column.strftime("%m-%d") for date_column in attendance_grid.columns
    ]

    # Size the figure dynamically based on number of dates and habits
    figure_width = max(8.0, 0.42 * attendance_grid.shape[1] + 2.2)
    figure_height = max(2.8, 0.55 * attendance_grid.shape[0] + 1.8)
    figure, axis = plt.subplots(figsize=(figure_width, figure_height))

    # Apply dark theme directly on figure and axes without mutating global Matplotlib style
    figure.patch.set_facecolor("#0e1117")
    axis.set_facecolor("#161b22")

    # Draw the binary heatmap (red = Missed / 0, green = Attended / 1)
    sns.heatmap(
        attendance_grid,
        cmap=[status_colors["Not Done"], status_colors["Done"]],
        vmin=0,
        vmax=1,
        cbar=False,
        linewidths=0.6,
        linecolor="#0e1117",
        ax=axis,
    )

    # Create three color-box patches for the custom legend below the grid
    legend_items = [
        # Green box for attended / completed days
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=status_colors["Done"],
            edgecolor="#0e1117",
            label="Attended (Done)",
        ),
        # Red box for missed days
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=status_colors["Not Done"],
            edgecolor="#0e1117",
            label="Missed (Not Done)",
        ),
        # Dark slate box for dates with no logged entry
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor="#161b22",
            edgecolor="#484f58",
            label="Not Logged",
        ),
    ]

    # Format title, axes labels, and rotated MM-DD date labels in crisp white text
    axis.set_title("30-Day Attendance Heatmap", color="white", fontsize=13, pad=12)
    axis.set_xlabel("Date (MM-DD)", color="white", labelpad=8)
    axis.set_ylabel("")
    axis.tick_params(axis="x", colors="white", rotation=45)
    for tick_label in axis.get_xticklabels():
        tick_label.set_horizontalalignment("right")
    axis.tick_params(axis="y", colors="white", rotation=0)

    # Place visual legend below the x-axis label so it never overlaps date ticks
    axis.legend(
        handles=legend_items,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.32),
        ncol=3,
        frameon=False,
        labelcolor="white",
        fontsize=10,
    )

    figure.tight_layout()
    st.pyplot(figure, clear_figure=True)
    plt.close(figure)


# --- Sidebar Controls, Session State Setup & Sequential Routing ---

# Apply one-click dataset switch before creating the radio widget
if st.session_state.get("switch_to_test"):
    st.session_state["dataset"] = "Test data"
    st.session_state["switch_to_test"] = False

st.sidebar.title("📈 Habit Tracker")
selected_dataset = st.sidebar.radio(
    "Dataset", ["Actual data", "Test data"], key="dataset"
)
st.sidebar.caption(f"Active file: `{get_file()}`")

# Default to index 0 ("Log Habit") so the app opens straight on the daily check-in dashboard
selected_page = st.sidebar.radio("Navigation", pages, index=0)

# Initialize st.session_state["habits_df"] once per session or when switching datasets
if (
    "habits_df" not in st.session_state
    or st.session_state.get("loaded_dataset") != selected_dataset
):
    st.session_state["habits_df"] = load_data()
    st.session_state["loaded_dataset"] = selected_dataset
    st.session_state["table_editor_version"] = (
        st.session_state.get("table_editor_version", 0) + 1
    )

# Read active habits and logs from session state throughout the run
habits_data = st.session_state["habits_df"]
habit_list = get_habits(habits_data)


# ==============================================================================
# PAGE 1: LOG HABIT (DEFAULT HOME / DAILY CHECK-INS)
# ==============================================================================
if selected_page == "Log Habit":
    st.title("✅ Log Habit")
    st.caption("Daily check-ins, live streak tracking, and quick accountability.")

    # Show 7-day milestone reward with celebratory balloons when earned
    if "reward" in st.session_state:
        st.success(st.session_state.pop("reward"))
        st.balloons()

    # Show responsive confirmation banner + toast after any check-in action
    if "log_feedback" in st.session_state:
        feedback_level, feedback_message = st.session_state.pop("log_feedback")
        if feedback_level == "success":
            st.success(feedback_message)
        else:
            st.info(feedback_message)
        st.toast(feedback_message)

    # Welcome state when the active dataset has no habits yet
    if habit_list.empty:
        st.info(
            "Your tracker is currently empty. Add your first habit on **Add Habit**, "
            "or preview the app with sample test data."
        )
        if st.button("🧪 Preview with Test Data"):
            st.session_state["switch_to_test"] = True
            st.rerun()
    else:
        st.subheader("Daily Check-In")
        today = dt.date.today()
        # Prevent logging future dates by capping date_input at today
        picked_date = st.date_input("Check-in Date", value=today, max_value=today)
        date_text = str(picked_date)

        # Keep only habits that have started on or before the selected date
        active_habits = habit_list[habit_list["Start_Date"] <= date_text]

        if active_habits.empty:
            st.info(
                "No habits are active on this date yet. Check the Start Date or add a habit on **Add Habit**."
            )
        else:
            # Slice all logs matching the selected check-in date
            day_logs = habits_data[habits_data["Date"] == date_text]

            # Count completed habits for today's summary progress bar
            completed_today = sum(
                1
                for habit_name in active_habits["Habit"]
                if not day_logs[
                    (day_logs["Habit"] == habit_name)
                    & (day_logs["Status"] == "Done")
                ].empty
            )
            total_active = len(active_habits)
            st.write(
                f"**Today's Progress:** {completed_today} of {total_active} completed"
            )
            st.progress(completed_today / total_active)

            # Render one check-in row per active habit
            for row_index, habit_row in active_habits.iterrows():
                habit_name = habit_row["Habit"]
                category_icon = category_icons.get(habit_row["Category"], "📌")
                existing_log = day_logs[day_logs["Habit"] == habit_name]
                current_streak, unused_best = get_streaks(
                    habits_data, habit_name, picked_date
                )

                # Show Completed (+ streak), Missed (+ excuse), or Pending status next to habit
                if not existing_log.empty:
                    logged_status = existing_log.iloc[0]["Status"]
                    logged_excuse = existing_log.iloc[0]["Excuse"]
                    if logged_status == "Done":
                        streak_note = (
                            f" • 🔥 {current_streak}-day streak"
                            if current_streak > 0
                            else ""
                        )
                        status_label = f":green[Completed]{streak_note}"
                    else:
                        excuse_note = f" — *{logged_excuse}*" if logged_excuse else ""
                        status_label = f":red[Missed]{excuse_note}"
                else:
                    status_label = ":gray[Pending]"

                # Split each row into habit info, Done button, and Not Done button
                info_column, done_column, not_done_column = st.columns([3.5, 1, 1])
                with info_column:
                    st.markdown(f"{category_icon} **{habit_name}** — {status_label}")
                    st.caption(
                        f"{habit_row['Category']} • {habit_row['Frequency']} • Goal: {habit_row['Goal']}"
                    )

                # Clicking Done saves completion to session state + CSV and checks 7-day milestones
                if done_column.button(
                    "✅ Done", key=f"done_{habit_name}_{date_text}", width="stretch"
                ):
                    # Close any open inline excuse prompt for this habit first
                    if (
                        st.session_state.get("pending_excuse", {}).get("habit")
                        == habit_name
                    ):
                        st.session_state.pop("pending_excuse", None)

                    updated_table = add_log(
                        habits_data, habit_name, picked_date, "Done", excuse=""
                    )
                    if save_data(updated_table):
                        # Recalculate streak after saving to detect 7-day milestones (7, 14, 21, ...)
                        new_streak, unused_best = get_streaks(
                            updated_table, habit_name, picked_date
                        )
                        if new_streak > 0 and new_streak % 7 == 0:
                            st.session_state["reward"] = (
                                f"🎉 Milestone reached! {new_streak}-day streak on '{habit_name}'!"
                            )
                        else:
                            day_word = "day" if new_streak == 1 else "days"
                            st.session_state["log_feedback"] = (
                                "success",
                                f"Nice work! Completed '{habit_name}' for {date_text} "
                                f"(Current streak: {new_streak} {day_word}).",
                            )
                        st.rerun()

                # Clicking Not Done opens an inline excuse prompt before saving to CSV
                if not_done_column.button(
                    "❌ Not Done",
                    key=f"notdone_{habit_name}_{date_text}",
                    width="stretch",
                ):
                    st.session_state["pending_excuse"] = {
                        "habit": habit_name,
                        "date": date_text,
                    }
                    st.rerun()

                # Render the inline excuse prompt directly below the chosen habit
                pending_excuse = st.session_state.get("pending_excuse")
                if pending_excuse == {"habit": habit_name, "date": date_text}:
                    with st.container(border=True):
                        st.write(
                            f"📝 Why was **{habit_name}** missed on **{date_text}**?"
                        )
                        # Let user choose a common excuse or type a custom reason
                        excuse_choice = st.selectbox(
                            "Choose a reason",
                            predefined_excuses + ["Other (custom)"],
                            key=f"excuse_choice_{habit_name}_{date_text}",
                        )
                        custom_reason = ""
                        if excuse_choice == "Other (custom)":
                            custom_reason = st.text_input(
                                "Type your custom reason",
                                placeholder="e.g. Traveling, family event",
                                key=f"excuse_custom_{habit_name}_{date_text}",
                            )

                        save_column, skip_column, cancel_column = st.columns([2, 2, 1])

                        # Save Miss & Excuse: validate custom text if chosen, then save Not Done + reason
                        if save_column.button(
                            "Save Miss & Excuse",
                            type="primary",
                            key=f"save_excuse_{habit_name}_{date_text}",
                            width="stretch",
                        ):
                            final_reason = (
                                custom_reason.strip()
                                if excuse_choice == "Other (custom)"
                                else excuse_choice
                            )
                            if not final_reason:
                                st.warning(
                                    "Please type a custom reason or click Skip Excuse."
                                )
                            else:
                                updated_table = add_log(
                                    habits_data,
                                    habit_name,
                                    picked_date,
                                    "Not Done",
                                    excuse=final_reason,
                                )
                                if save_data(updated_table):
                                    st.session_state.pop("pending_excuse", None)
                                    st.session_state["log_feedback"] = (
                                        "info",
                                        f"Logged '{habit_name}' as Not Done for {date_text} "
                                        f"(Reason: {final_reason}).",
                                    )
                                    st.rerun()

                        # Skip Excuse: save Not Done with an empty Excuse field
                        if skip_column.button(
                            "Skip Excuse",
                            key=f"skip_excuse_{habit_name}_{date_text}",
                            width="stretch",
                        ):
                            updated_table = add_log(
                                habits_data,
                                habit_name,
                                picked_date,
                                "Not Done",
                                excuse="",
                            )
                            if save_data(updated_table):
                                st.session_state.pop("pending_excuse", None)
                                st.session_state["log_feedback"] = (
                                    "info",
                                    f"Logged '{habit_name}' as Not Done for {date_text} "
                                    "(No excuse added).",
                                )
                                st.rerun()

                        # Cancel: close the inline prompt without writing anything
                        if cancel_column.button(
                            "Cancel",
                            key=f"cancel_excuse_{habit_name}_{date_text}",
                            width="stretch",
                        ):
                            st.session_state.pop("pending_excuse", None)
                            st.rerun()

        # --- Section: Streaks & Milestones Summary Strip ---
        st.divider()
        st.subheader("🔥 Streaks & Milestones")

        # Compute current and best streaks for every habit as of picked_date
        streak_rows = []
        for habit_name in habit_list["Habit"]:
            current_streak, best_streak = get_streaks(
                habits_data, habit_name, picked_date
            )
            streak_rows.append(
                {
                    "Habit": habit_name,
                    "Current": current_streak,
                    "Best": best_streak,
                }
            )
        streak_table = pd.DataFrame(streak_rows)

        # Highlight any habits currently at 7 or more consecutive days
        milestone_habits = streak_table[streak_table["Current"] >= 7]["Habit"].tolist()
        if milestone_habits:
            st.success(
                f"🔥 7+ day streak milestone active: {', '.join(milestone_habits)}"
            )

        # Display streak metric cards in a 4-column grid
        metric_columns = st.columns(4)
        for card_index, streak_row in streak_table.iterrows():
            metric_columns[card_index % 4].metric(
                streak_row["Habit"],
                f"{streak_row['Current']} days",
                f"Best: {streak_row['Best']} days",
                delta_color="off",
            )


# ==============================================================================
# PAGE 2: ADD HABIT
# ==============================================================================
elif selected_page == "Add Habit":
    st.title("➕ Add Habit")
    st.caption("Create a new habit and start tracking it on Log Habit.")

    # Use st.form so Streamlit only runs validation when the submit button is clicked
    with st.form("add_form", clear_on_submit=True):
        name_input = st.text_input("Habit Name", placeholder="e.g. Morning Walk")
        category_column, frequency_column = st.columns(2)
        category_input = category_column.selectbox("Category", categories)
        frequency_input = frequency_column.selectbox("Frequency", frequencies)

        goal_column, start_date_column = st.columns(2)
        goal_input = goal_column.number_input(
            "Goal (times per period)", min_value=1, max_value=1000, value=1, step=1
        )
        start_input = start_date_column.date_input("Start Date", value=dt.date.today())

        submit_button = st.form_submit_button("Add Habit", type="primary")

        if submit_button:
            # Check that the habit name is not blank and does not already exist
            name_error = check_name(name_input, habits_data)
            if name_error:
                st.error(name_error)
            else:
                clean_habit = name_input.strip()
                # Create a new habit row with blank Date/Status/Excuse until logged
                new_habit = {
                    "Habit": clean_habit,
                    "Category": category_input,
                    "Frequency": frequency_input,
                    "Goal": str(int(goal_input)),
                    "Start_Date": str(start_input),
                    "Date": "",
                    "Status": "",
                    "Excuse": "",
                }
                new_table = pd.concat(
                    [habits_data, pd.DataFrame([new_habit])], ignore_index=True
                )
                if save_data(new_table):
                    st.success(
                        f"Added '{clean_habit}'! Head to **Log Habit** to record check-ins."
                    )
                    # Refresh local references so the preview table below updates right away
                    habits_data = st.session_state["habits_df"]
                    habit_list = get_habits(habits_data)

    # Preview current habits using a clean .head() table view
    if not habit_list.empty:
        st.divider()
        st.subheader("Current Habits Preview")
        st.dataframe(habit_list.head(10), hide_index=True, width="stretch")


# ==============================================================================
# PAGE 3: MANAGE HABITS (DROPDOWN EDITOR, DATA EDITOR & CSV TOOLS)
# ==============================================================================
elif selected_page == "Manage Habits":
    st.title("⚙️ Manage Habits")
    st.caption(
        "Edit or delete habits individually or in the interactive table, and manage CSV data."
    )

    if "manage_feedback" in st.session_state:
        feedback_message = st.session_state.pop("manage_feedback")
        st.success(feedback_message)
        st.toast(feedback_message)

    dropdown_tab, table_tab = st.tabs(["Edit by Habit", "Interactive Table"])

    # --- Tab 1: Sequential Habit-First Dropdown Editor ---
    with dropdown_tab:
        st.subheader("Edit or Delete a Habit")
        if habit_list.empty:
            st.info(
                "No habits to manage yet. Add one on **Add Habit** or use the **Interactive Table** tab."
            )
        else:
            # Prompt the user to choose a habit first before revealing details and actions
            chosen_habit = st.selectbox(
                "Select a habit to manage",
                options=habit_list["Habit"].tolist(),
                index=None,
                placeholder="Choose a habit...",
            )

            # Hide edit/delete widgets until a specific habit is picked from the dropdown
            if chosen_habit is None:
                st.info(
                    "Select a habit from the dropdown above to inspect its details, edit it, or delete it."
                )
            else:
                selected_habit_row = habit_list[
                    habit_list["Habit"] == chosen_habit
                ].iloc[0]
                logged_day_count = int(
                    (
                        (habits_data["Habit"] == chosen_habit)
                        & (habits_data["Date"] != "")
                    ).sum()
                )

                # Quick summary strip for the selected habit
                summary_columns = st.columns(4)
                summary_columns[0].metric("Category", selected_habit_row["Category"])
                summary_columns[1].metric("Frequency", selected_habit_row["Frequency"])
                summary_columns[2].metric("Goal", selected_habit_row["Goal"])
                summary_columns[3].metric("Logged Days", logged_day_count)
                st.caption(f"Start Date: `{selected_habit_row['Start_Date']}`")

                # Edit form pre-filled with the selected habit's current values
                with st.form("edit_form"):
                    new_name = st.text_input("Name", value=chosen_habit)

                    # Fall back safely to index 0 if a CSV value is outside the standard list
                    frequency_index = (
                        frequencies.index(selected_habit_row["Frequency"])
                        if selected_habit_row["Frequency"] in frequencies
                        else 0
                    )
                    new_frequency = st.selectbox(
                        "Frequency", frequencies, index=frequency_index
                    )

                    # Clamp Goal inside 1..1000 in case an uploaded CSV has unexpected text
                    try:
                        current_goal = max(
                            1, min(1000, int(float(selected_habit_row["Goal"])))
                        )
                    except Exception:
                        current_goal = 1
                    new_goal = st.number_input(
                        "Goal (times per period)",
                        min_value=1,
                        max_value=1000,
                        value=current_goal,
                        step=1,
                    )

                    category_index = (
                        categories.index(selected_habit_row["Category"])
                        if selected_habit_row["Category"] in categories
                        else 0
                    )
                    new_category = st.selectbox(
                        "Category", categories, index=category_index
                    )

                    try:
                        start_date_value = dt.date.fromisoformat(
                            selected_habit_row["Start_Date"]
                        )
                    except Exception:
                        start_date_value = dt.date.today()
                    new_start_date = st.date_input("Start Date", value=start_date_value)

                    save_changes = st.form_submit_button("Save Changes", type="primary")
                    if save_changes:
                        # Validate new name while allowing the habit to keep its own name
                        name_error = check_name(
                            new_name, habits_data, editing_habit=chosen_habit
                        )
                        if name_error:
                            st.error(name_error)
                        else:
                            clean_new_name = new_name.strip()
                            updated_table = habits_data.copy()
                            # Update metadata across all historical log rows for this habit
                            habit_mask = updated_table["Habit"] == chosen_habit
                            updated_table.loc[habit_mask, "Habit"] = clean_new_name
                            updated_table.loc[habit_mask, "Frequency"] = new_frequency
                            updated_table.loc[habit_mask, "Goal"] = str(int(new_goal))
                            updated_table.loc[habit_mask, "Category"] = new_category
                            updated_table.loc[habit_mask, "Start_Date"] = str(
                                new_start_date
                            )
                            if save_data(updated_table):
                                st.session_state["manage_feedback"] = (
                                    f"Updated '{clean_new_name}'!"
                                )
                                st.rerun()

                # Remove the habit and all of its daily logs when confirmed by button click
                if st.button(f"🗑️ Delete '{chosen_habit}' and all its logs"):
                    remaining_table = habits_data[habits_data["Habit"] != chosen_habit]
                    if save_data(remaining_table):
                        st.session_state["manage_feedback"] = (
                            f"Deleted '{chosen_habit}'."
                        )
                        st.rerun()

    # --- Tab 2: Interactive Table Editor (st.data_editor) ---
    with table_tab:
        st.subheader("Interactive Habits Table")
        st.caption(
            "Edit cells directly, add new rows at the bottom, or select rows and press Delete. "
            "Click Save Table Changes when finished."
        )

        # Prepare typed columns so st.data_editor dropdowns, numbers, and dates work cleanly
        if habit_list.empty:
            # Create an empty typed template when no habits exist yet
            editable_habits = pd.DataFrame(
                {
                    "Habit": pd.Series(dtype="object"),
                    "Category": pd.Series(dtype="object"),
                    "Frequency": pd.Series(dtype="object"),
                    "Goal": pd.Series(dtype="int64"),
                    "Start_Date": pd.Series(dtype="object"),
                }
            )
        else:
            editable_habits = habit_list.copy()
            editable_habits["Goal"] = (
                pd.to_numeric(editable_habits["Goal"], errors="coerce")
                .fillna(1)
                .clip(1, 1000)
                .astype(int)
            )
            editable_habits["Start_Date"] = pd.to_datetime(
                editable_habits["Start_Date"], errors="coerce"
            ).dt.date

        # Track original habit names by row index so renames keep their check-in history
        original_names = dict(zip(editable_habits.index, editable_habits["Habit"]))
        editor_version = st.session_state.get("table_editor_version", 0)

        # Render spreadsheet-style editor with column validation hints
        edited_habits = st.data_editor(
            editable_habits,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"habits_table_editor_{editor_version}",
            column_config={
                "Habit": st.column_config.TextColumn("Habit", required=True),
                "Category": st.column_config.SelectboxColumn(
                    "Category", options=categories, required=True
                ),
                "Frequency": st.column_config.SelectboxColumn(
                    "Frequency", options=frequencies, required=True
                ),
                "Goal": st.column_config.NumberColumn(
                    "Goal", min_value=1, max_value=1000, step=1, required=True
                ),
                "Start_Date": st.column_config.DateColumn(
                    "Start Date", format="YYYY-MM-DD", required=True
                ),
            },
        )

        # Validate every modified/added row and update session state + CSV on save
        if st.button("💾 Save Table Changes", type="primary"):
            editor_state = st.session_state.get(
                f"habits_table_editor_{editor_version}", {}
            )
            deleted_positions = editor_state.get("deleted_rows", [])
            updated_table, validation_errors = apply_table_edits(
                habits_data, edited_habits, original_names, deleted_positions
            )
            if validation_errors:
                for error_message in validation_errors:
                    st.error(error_message)
            elif save_data(updated_table):
                st.session_state["manage_feedback"] = "Saved interactive table changes!"
                st.rerun()

    # --- Sample Data Switching & CSV Upload / Download Tools ---
    st.divider()
    st.subheader("CSV & Sample Data Tools")

    # Set session flag and rerun so sidebar dataset switches cleanly before widget creation
    if st.button("🧪 Switch to Test Data"):
        st.session_state["switch_to_test"] = True
        st.rerun()

    # Validate uploaded CSV schema and values before allowing replacement
    uploaded_file = st.file_uploader(
        "Upload CSV (replaces active dataset after validation)", type="csv"
    )
    if uploaded_file is not None:
        try:
            uploaded_table = pd.read_csv(uploaded_file, dtype=str).fillna("")
            goal_numbers = (
                pd.to_numeric(uploaded_table["Goal"], errors="coerce")
                if "Goal" in uploaded_table.columns
                else pd.Series(dtype=float)
            )

            # Enforce exact 8 columns, non-empty Habit names, and whole-number Goals (1-1000)
            if list(uploaded_table.columns) != columns:
                st.error(f"Columns must be exactly: {', '.join(columns)}")
            elif (uploaded_table["Habit"].str.strip() == "").any():
                st.error("Habit column cannot contain empty names.")
            elif (
                goal_numbers.isna().any()
                or ((goal_numbers % 1) != 0).any()
                or (goal_numbers < 1).any()
                or (goal_numbers > 1000).any()
            ):
                st.error("Goal column must contain whole numbers between 1 and 1000.")
            else:
                st.success(
                    f"File is valid: {len(uploaded_table)} rows across {uploaded_table['Habit'].nunique()} habits."
                )
                if st.button(
                    "Replace active dataset with uploaded CSV", type="primary"
                ):
                    if save_data(uploaded_table):
                        st.session_state["manage_feedback"] = (
                            "Replaced active dataset with uploaded CSV."
                        )
                        st.rerun()
        except Exception as error:
            st.error(f"Upload rejected: {error}")

    # Encode active DataFrame as UTF-8 CSV bytes for local download
    csv_bytes = habits_data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download current dataset",
        data=csv_bytes,
        file_name="habits.csv",
        mime="text/csv",
    )


# ==============================================================================
# PAGE 4: MY PROGRESS (CHECKBOX FILTERS, TRENDS & RELIABLE HEATMAP)
# ==============================================================================
elif selected_page == "My Progress":
    st.title("📊 My Progress")
    st.caption(
        "Filter by category and status to inspect completion trends and attendance."
    )

    if habit_list.empty:
        st.info(
            "No habits yet. Add one on **Add Habit** or switch to **Test data** in the sidebar."
        )
    else:
        # Interactive category checkboxes arranged in 3 columns to update all charts live
        st.write("**Filter by Category**")
        checkbox_columns = st.columns(3)
        selected_categories = []
        for category_index, category_name in enumerate(categories):
            category_icon = category_icons.get(category_name, "")
            if checkbox_columns[category_index % 3].checkbox(
                f"{category_icon} {category_name}",
                value=True,
                key=f"cat_cb_{category_name}",
            ):
                selected_categories.append(category_name)

        # Radio button to show All logs, only Done, or only Not Done
        chosen_status = st.radio(
            "Show records", ["All", "Done", "Not Done"], horizontal=True
        )

        # Keep only dated check-in rows, then filter by selected categories and status
        logged_records = habits_data[habits_data["Date"] != ""].copy()
        category_records = logged_records[
            logged_records["Category"].isin(selected_categories)
        ]

        if chosen_status != "All":
            filtered_records = category_records[
                category_records["Status"] == chosen_status
            ]
        else:
            filtered_records = category_records

        if not selected_categories:
            st.info("Select at least one category checkbox above to view your progress.")
        elif filtered_records.empty:
            st.info("No logged check-ins match these filters yet.")
        else:
            # --- Row 1: Overall Completion Rate & Done vs Not Done Pie Chart ---
            rate_column, pie_column = st.columns(2)
            done_count = int((category_records["Status"] == "Done").sum())
            total_count = len(category_records)
            completion_rate = (done_count / total_count * 100) if total_count > 0 else 0.0

            with rate_column:
                st.metric(
                    "Overall Completion Rate",
                    f"{round(completion_rate, 1)}%",
                    f"{done_count} done out of {total_count} logs",
                )
                # Clamp progress between 0.0 and 1.0 as required by st.progress
                st.progress(min(max(completion_rate / 100.0, 0.0), 1.0))

            # Count Done vs Not Done rows for the static composition pie chart
            status_counts = category_records["Status"].value_counts().reset_index()
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
            with pie_column:
                st.plotly_chart(pie_chart, width="stretch")

            # --- Row 2: Check-ins by Category (Grouped Column Chart) ---
            by_category = (
                filtered_records.groupby(["Category", "Status"])
                .size()
                .reset_index(name="Count")
            )
            category_bar_chart = px.bar(
                by_category,
                x="Category",
                y="Count",
                color="Status",
                barmode="group",
                color_discrete_map=status_colors,
                title="Check-ins by Category",
                template="plotly_dark",
            )
            st.plotly_chart(category_bar_chart, width="stretch")

            # --- Row 3: Current vs Best Streak per Filtered Habit ---
            today = dt.date.today()
            filtered_habits = habit_list[
                habit_list["Category"].isin(selected_categories)
            ]
            streaks_list = []
            for habit_name in filtered_habits["Habit"]:
                current_streak, best_streak = get_streaks(
                    habits_data, habit_name, today
                )
                streaks_list.append(
                    {
                        "Habit": habit_name,
                        "Current": current_streak,
                        "Best": best_streak,
                    }
                )
            streak_table = pd.DataFrame(streaks_list)
            if not streak_table.empty:
                # Reshape wide columns (Current, Best) into long format for grouped bars
                melted_streaks = streak_table.melt(
                    id_vars="Habit", var_name="Type", value_name="Days"
                )
                streak_bar_chart = px.bar(
                    melted_streaks,
                    x="Habit",
                    y="Days",
                    color="Type",
                    barmode="group",
                    title="Current vs Best Streak",
                    template="plotly_dark",
                )
                st.plotly_chart(streak_bar_chart, width="stretch")

            # --- Row 4: Daily Attendance Trend Line Chart ---
            trend_records = filtered_records.copy()
            # Drop malformed date strings before grouping and sorting chronologically
            trend_records["parsed_date"] = pd.to_datetime(
                trend_records["Date"], errors="coerce"
            )
            trend_records = trend_records.dropna(subset=["parsed_date"])
            if not trend_records.empty:
                daily_trend = (
                    trend_records.groupby(["Date", "Status"])
                    .size()
                    .reset_index(name="Count")
                    .sort_values("Date")
                )
                line_chart = px.line(
                    daily_trend,
                    x="Date",
                    y="Count",
                    color="Status",
                    markers=True,
                    color_discrete_map=status_colors,
                    title="Daily Attendance Trend",
                    template="plotly_dark",
                )
                st.plotly_chart(line_chart, width="stretch")

            # --- Row 5: Reliable 30-Day Attendance Heatmap ---
            st.subheader("30-Day Attendance Grid")
            show_heatmap(filtered_records)

            # Full filtered records table on demand
            with st.expander("View filtered log records"):
                st.dataframe(
                    filtered_records.sort_values("Date", ascending=False),
                    hide_index=True,
                    width="stretch",
                )


# ==============================================================================
# PAGE 5: EXCUSE MANAGER (CSV HISTORY, HABIT INSPECTION & STORYTELLING CHARTS)
# ==============================================================================
elif selected_page == "Excuse Manager":
    st.title("📝 Excuse Manager")
    st.caption(
        "Review missed habits and logged excuses from your active records, update reasons per habit, and spot patterns over time."
    )

    if "excuse_feedback" in st.session_state:
        feedback_message = st.session_state.pop("excuse_feedback")
        st.success(feedback_message)
        st.toast(feedback_message)

    # Pull all missed check-in rows from the active session DataFrame
    missed_records = habits_data[
        (habits_data["Status"] == "Not Done") & (habits_data["Date"] != "")
    ].copy()

    # Sort newest missed dates to the top for clean inspection
    missed_sorted = missed_records.sort_values("Date", ascending=False).copy()

    # Replace empty excuses with a readable placeholder for display tables
    missed_sorted["Display_Excuse"] = missed_sorted["Excuse"].replace(
        "", "No excuse logged"
    )

    # Filter non-empty written excuses for excuse-specific counts and charts
    excuse_only = missed_sorted[missed_sorted["Excuse"].str.strip() != ""].copy()

    # --- Step A: Missed Habits Summary & .head() Preview ---
    st.subheader("Recent Missed Habits & Excuses")

    if missed_sorted.empty:
        st.info("No missed habits (`Not Done`) are recorded yet.")
    else:
        # Find the most frequently missed habit and most common written excuse
        top_habit = missed_sorted["Habit"].value_counts().index[0]
        top_habit_count = int(missed_sorted["Habit"].value_counts().iloc[0])
        if not excuse_only.empty:
            top_reason = excuse_only["Excuse"].value_counts().index[0]
            top_reason_count = int(excuse_only["Excuse"].value_counts().iloc[0])
        else:
            top_reason = "None logged"
            top_reason_count = 0

        # Display 3 summary KPI cards side by side
        total_missed_column, top_habit_column, top_excuse_column = st.columns(3)
        total_missed_column.metric("Total Missed Check-ins", len(missed_sorted))
        top_habit_column.metric(
            "Most Missed Habit", top_habit, f"{top_habit_count} misses", delta_color="off"
        )
        top_excuse_column.metric(
            "Top Excuse Reason",
            top_reason,
            f"{top_reason_count} times" if top_reason_count else "0 logged",
            delta_color="off",
        )

        # Show a clean .head(5) preview of the latest missed records and their excuses
        preview_table = (
            missed_sorted[["Date", "Habit", "Category", "Display_Excuse"]]
            .rename(columns={"Display_Excuse": "Excuse"})
            .head(5)
        )
        st.write("**Latest 5 Missed Records (`.head()` preview):**")
        st.dataframe(preview_table, hide_index=True, width="stretch")

        # Toggle full Excuse History table on demand so the page stays uncluttered by default
        if st.checkbox("View full Excuse History", value=False):
            history_filter = st.radio(
                "History rows",
                ["All missed records", "Only records with excuses"],
                horizontal=True,
            )
            history_source = (
                excuse_only
                if history_filter == "Only records with excuses"
                else missed_sorted
            )
            if history_source.empty:
                st.info("No rows match that filter.")
            else:
                history_table = history_source[
                    ["Date", "Habit", "Category", "Display_Excuse"]
                ].rename(columns={"Display_Excuse": "Excuse"})
                st.dataframe(history_table, hide_index=True, width="stretch")

    # --- Step B: Habit-First Selection, Missed Dates & Excuse Update ---
    st.divider()
    st.subheader("Inspect a Habit & Log / Update an Excuse")

    if habit_list.empty:
        st.info("No habits yet. Add one on **Add Habit** first.")
    else:
        # Select the habit first before showing its missed dates and excuse form
        selected_habit = st.selectbox(
            "Select a habit to inspect missed dates or add/update an excuse",
            options=habit_list["Habit"].tolist(),
            index=None,
            placeholder="Choose a habit...",
        )

        if selected_habit is None:
            st.info(
                "Choose a habit above to see its missed dates and log or update an excuse."
            )
        else:
            # Filter missed records down to only the chosen habit
            habit_misses = missed_sorted[missed_sorted["Habit"] == selected_habit]
            st.write(
                f"**{selected_habit}** has **{len(habit_misses)}** missed check-in(s) in `{get_file()}`."
            )

            # Show recent missed dates for this habit plus an optional full-history toggle
            if not habit_misses.empty:
                habit_miss_table = habit_misses[["Date", "Display_Excuse"]].rename(
                    columns={"Display_Excuse": "Excuse"}
                )
                st.dataframe(
                    habit_miss_table.head(5), hide_index=True, width="stretch"
                )
                if len(habit_miss_table) > 5 and st.checkbox(
                    f"Show all {len(habit_miss_table)} missed dates for '{selected_habit}'"
                ):
                    st.dataframe(habit_miss_table, hide_index=True, width="stretch")

            # Container to attach or update an excuse on a selected date
            with st.container(border=True):
                st.write(f"Log or update a missed date for **{selected_habit}**")
                missed_day = st.date_input(
                    "Date missed",
                    value=dt.date.today(),
                    max_value=dt.date.today(),
                    key=f"excuse_date_{selected_habit}",
                )
                reason_choice = st.selectbox(
                    "Reason",
                    predefined_excuses + ["Other (custom)"],
                    key=f"excuse_reason_{selected_habit}",
                )
                # Reveal a text input only when the user selects Other (custom)
                custom_excuse = ""
                if reason_choice == "Other (custom)":
                    custom_excuse = st.text_input(
                        "Custom reason",
                        placeholder="e.g. Felt sick, busy at work",
                        key=f"excuse_custom_{selected_habit}",
                    )

                if st.button(
                    "Save Excuse to CSV",
                    type="primary",
                    key=f"excuse_save_{selected_habit}",
                ):
                    final_excuse = (
                        custom_excuse.strip()
                        if reason_choice == "Other (custom)"
                        else reason_choice
                    )
                    start_date_text = habit_list[habit_list["Habit"] == selected_habit][
                        "Start_Date"
                    ].iloc[0]

                    # Validate that a reason is provided and the date is on or after Start_Date
                    if not final_excuse:
                        st.error("Please enter a reason.")
                    elif str(missed_day) < start_date_text:
                        st.error(
                            f"'{selected_habit}' starts on {start_date_text}; pick a later date."
                        )
                    else:
                        # Save as Not Done with the chosen excuse into session state + CSV
                        updated_table = add_log(
                            habits_data,
                            selected_habit,
                            missed_day,
                            "Not Done",
                            excuse=final_excuse,
                        )
                        if save_data(updated_table):
                            st.session_state["excuse_feedback"] = (
                                f"Saved excuse '{final_excuse}' for '{selected_habit}' on {missed_day}."
                            )
                            st.rerun()

    # --- Step C: Storytelling Charts ---
    if not missed_sorted.empty:
        st.divider()
        st.subheader("📈 Missed Habits Storytelling & Patterns")

        missed_chart_column, excuse_chart_column = st.columns(2)

        # Chart 1: Which habits are missed most often (grouped by Habit & Category)
        missed_by_habit = (
            missed_sorted.groupby(["Habit", "Category"])
            .size()
            .reset_index(name="Misses")
            .sort_values("Misses", ascending=False)
        )
        missed_habit_chart = px.bar(
            missed_by_habit,
            x="Habit",
            y="Misses",
            color="Category",
            title="Which Habits Are Missed Most Often?",
            template="plotly_dark",
        )
        missed_chart_column.plotly_chart(missed_habit_chart, width="stretch")

        # Chart 2: Top excuse reasons from non-empty written excuses
        with excuse_chart_column:
            if not excuse_only.empty:
                reason_counts = excuse_only["Excuse"].value_counts().reset_index()
                reason_counts.columns = ["Excuse", "Count"]
                reasons_chart = px.bar(
                    reason_counts,
                    x="Excuse",
                    y="Count",
                    title="Top Excuse Reasons",
                    template="plotly_dark",
                    color_discrete_sequence=[status_colors["Not Done"]],
                )
                st.plotly_chart(reasons_chart, width="stretch")
            else:
                st.info("No written excuses logged yet to rank top reasons.")

        weekly_chart_column, weekday_chart_column = st.columns(2)

        # Chart 3: Weekly trend of missed habits over time
        with weekly_chart_column:
            try:
                weekly_records = missed_sorted.copy()
                weekly_records["parsed_date"] = pd.to_datetime(
                    weekly_records["Date"], errors="coerce"
                )
                weekly_records = weekly_records.dropna(subset=["parsed_date"])
                # Group each missed date into its week starting Monday
                weekly_records["Week"] = (
                    weekly_records["parsed_date"].dt.to_period("W").dt.start_time
                )
                weekly_counts = (
                    weekly_records.groupby("Week")
                    .size()
                    .reset_index(name="Misses")
                    .sort_values("Week")
                )
                weekly_chart = px.line(
                    weekly_counts,
                    x="Week",
                    y="Misses",
                    markers=True,
                    title="Missed Habits Over Time (Weekly Trend)",
                    template="plotly_dark",
                    color_discrete_sequence=[status_colors["Not Done"]],
                )
                st.plotly_chart(weekly_chart, width="stretch")
            except Exception as error:
                st.write("Could not calculate weekly trend:", error)

        # Chart 4: Missed habits by day of the week (Monday through Sunday)
        with weekday_chart_column:
            try:
                weekday_records = missed_sorted.copy()
                weekday_records["parsed_date"] = pd.to_datetime(
                    weekday_records["Date"], errors="coerce"
                )
                weekday_records = weekday_records.dropna(subset=["parsed_date"])
                weekday_records["Day"] = weekday_records["parsed_date"].dt.day_name()
                day_order = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                # Reindex so every weekday appears in Monday -> Sunday order even with 0 misses
                day_counts = (
                    weekday_records["Day"]
                    .value_counts()
                    .reindex(day_order, fill_value=0)
                    .reset_index()
                )
                day_counts.columns = ["Day", "Misses"]
                weekday_chart = px.bar(
                    day_counts,
                    x="Day",
                    y="Misses",
                    title="Missed Habits by Day of Week",
                    template="plotly_dark",
                    color_discrete_sequence=["#f0ad4e"],
                )
                st.plotly_chart(weekday_chart, width="stretch")
            except Exception as error:
                st.write("Could not calculate day-of-week pattern:", error)
