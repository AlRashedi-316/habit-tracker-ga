# Habit Tracker App (app.py)
# A Streamlit + Pandas app to add habits, log check-ins, track streaks, and manage excuses.

import datetime as dt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import seaborn as sns
import streamlit as st
from streamlit_extras.let_it_rain import rain

# Configure the browser tab and wide page layout (must be the first Streamlit call)
st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")

# --- App Constants & Dropdown Options ---
DATA_FILE = "data/test_habits.csv"
COLUMNS = ["Habit", "Category", "Frequency", "Goal", "Start_Date", "Date", "Status", "Excuse"]
HABIT_COLUMNS = COLUMNS[:5]
CATEGORIES = ["Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"]
FREQUENCIES = ["Daily", "Weekly"]
EXCUSE_OPTIONS = ["No excuse", "Forgot", "Too tired", "Sick", "Ran out of time", "Bad weather", "Other (custom)"]
CATEGORY_ICONS = {"Health": "💧", "Fitness": "🏃", "Learning": "📖", "Mindfulness": "🧘", "Productivity": "⚡", "Other": "📌"}
STATUS_COLORS = {"Done": "#2e9e5b", "Not Done": "#d9534f"}
PAGES = ["Log Habit", "Add Habit", "Manage Habits", "My Progress", "Excuse Manager"]


# --- Data & Helper Functions ---

# Load the CSV file as strings so empty cells and dates stay clean
def load_data():
    try:
        return pd.read_csv(DATA_FILE, dtype=str).fillna("").reindex(columns=COLUMNS, fill_value="")
    except Exception as error:
        st.warning(f"Could not load '{DATA_FILE}' ({error}). Starting empty.")
        return pd.DataFrame(columns=COLUMNS)


# Save updated habits into session_state and write back to the CSV file
def save_data(updated_df):
    clean_df = updated_df[COLUMNS].reset_index(drop=True).copy()
    st.session_state["habits_df"] = clean_df
    st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
    try:
        clean_df.to_csv(DATA_FILE, index=False)
    except Exception as error:
        st.warning(f"Saved in session, but CSV write failed: {error}")


# Return one row per unique habit without repeated daily check-in logs
def get_unique_habits(habits_df):
    return habits_df.drop_duplicates(subset=["Habit"])[HABIT_COLUMNS].reset_index(drop=True)


# Count consecutive Done dates to compute (current_streak, best_streak)
def get_streaks(habits_df, habit_name, reference_date):
    done_logs = habits_df[(habits_df["Habit"] == habit_name) & (habits_df["Status"] == "Done") & (habits_df["Date"] != "")]
    done_dates = pd.to_datetime(done_logs["Date"], errors="coerce").dropna().dt.date.drop_duplicates().sort_values().tolist()
    if not done_dates:
        return 0, 0

    # Walk forward through all Done dates to find the longest streak ever
    best_streak = running_count = 0
    for index, logged_day in enumerate(done_dates):
        running_count = running_count + 1 if index > 0 and (logged_day - done_dates[index - 1]).days == 1 else 1
        best_streak = max(best_streak, running_count)

    # Walk backward from reference_date to count the active streak (today or yesterday keeps it alive)
    past_dates = [day for day in done_dates if day <= reference_date]
    current_streak = 1 if past_dates and (reference_date - past_dates[-1]).days <= 1 else 0
    for index in range(len(past_dates) - 2, -1, -1):
        if not current_streak or (past_dates[index + 1] - past_dates[index]).days != 1:
            break
        current_streak += 1
    return current_streak, best_streak


# Build a summary DataFrame of Current and Best streaks for a list of habits
def get_streak_table(habits_df, habit_names, reference_date):
    return pd.DataFrame([{"Habit": name, "Current": cur, "Best": best} for name in habit_names for cur, best in [get_streaks(habits_df, name, reference_date)]])


# Add or overwrite a habit's check-in on log_date and remove any blank placeholder row
def add_log(habits_df, habit_name, log_date, status, excuse=""):
    matching_rows = habits_df[habits_df["Habit"] == habit_name]
    if matching_rows.empty:
        return habits_df
    habit_info, date_text = matching_rows.iloc[0], str(log_date)
    new_entry = {**{col: str(habit_info[col]) for col in HABIT_COLUMNS}, "Date": date_text, "Status": status, "Excuse": excuse}
    keep_mask = ~((habits_df["Habit"] == habit_name) & ((habits_df["Date"] == date_text) | (habits_df["Date"] == "")))
    return pd.concat([habits_df[keep_mask], pd.DataFrame([new_entry])], ignore_index=True)


# Validate interactive table edits and preserve historical logs when a habit is renamed
def apply_table_edits(habits_df, edited_df, original_names, deleted_positions=None):
    errors, seen_names, cleaned_rows = [], set(), []
    active_originals = {row_id: name for pos, (row_id, name) in enumerate(original_names.items()) if pos not in set(deleted_positions or [])}

    for row_number, (row_id, row_data) in enumerate(edited_df.iterrows(), start=1):
        clean_row = row_data.fillna("")
        habit_name, category, frequency = str(clean_row.get("Habit", "")).strip(), str(clean_row.get("Category", "")).strip(), str(clean_row.get("Frequency", "")).strip()
        goal_number, start_date = pd.to_numeric(row_data.get("Goal"), errors="coerce"), pd.to_datetime(row_data.get("Start_Date"), errors="coerce")

        if not habit_name or habit_name.lower() in seen_names:
            errors.append(f"Row {row_number}: Habit name must be non-empty and unique.")
        seen_names.add(habit_name.lower())
        if category not in CATEGORIES or frequency not in FREQUENCIES or pd.isna(goal_number) or goal_number % 1 != 0 or not (1 <= goal_number <= 1000) or pd.isna(start_date):
            errors.append(f"Row {row_number}: Check Category, Frequency, Goal (1-1000), and Start Date.")
        elif not errors:
            cleaned_rows.append((row_id, [habit_name, category, frequency, str(int(goal_number)), start_date.strftime("%Y-%m-%d")]))

    if errors:
        return None, errors

    # Rebuild the full table so renamed habits keep their past daily check-ins
    rebuilt_frames = []
    for row_id, values in cleaned_rows:
        existing_logs = habits_df[habits_df["Habit"] == active_originals[row_id]].copy() if row_id in active_originals else pd.DataFrame()
        if not existing_logs.empty:
            for column, value in zip(HABIT_COLUMNS, values):
                existing_logs[column] = value
            rebuilt_frames.append(existing_logs)
        else:
            rebuilt_frames.append(pd.DataFrame([{**dict(zip(HABIT_COLUMNS, values)), "Date": "", "Status": "", "Excuse": ""}]))
    return (pd.concat(rebuilt_frames, ignore_index=True)[COLUMNS] if rebuilt_frames else pd.DataFrame(columns=COLUMNS)), []


# Draw a 30-day Habit (Y-axis) x Day-Month (X-axis) attendance heatmap with Seaborn
def show_heatmap(records):
    heatmap_df = records[records["Status"].isin(["Done", "Not Done"])].assign(parsed_date=lambda frame: pd.to_datetime(frame["Date"], errors="coerce")).dropna(subset=["parsed_date"])
    if heatmap_df.empty:
        return st.info("No dated check-in records available for the heatmap.")

    # Keep the most recent 30 days and encode Done = 1, Not Done = 0 using np.where()
    recent_logs = heatmap_df[heatmap_df["parsed_date"] >= heatmap_df["parsed_date"].max() - pd.Timedelta(days=29)].assign(status_code=lambda frame: np.where(frame["Status"] == "Done", 1.0, 0.0))
    attendance_grid = recent_logs.pivot_table(index="Habit", columns="parsed_date", values="status_code", aggfunc="max").sort_index(axis=1)
    attendance_grid.columns = [date_col.strftime("%d-%m") for date_col in attendance_grid.columns]

    # Set dark background and size the figure based on the number of dates and habits
    figure_width, figure_height = max(8.0, 0.42 * attendance_grid.shape[1] + 2.2), max(2.8, 0.55 * attendance_grid.shape[0] + 1.8)
    figure, axis = plt.subplots(figsize=(figure_width, figure_height), facecolor="#0e1117")
    axis.set_facecolor("#161b22")

    # Draw green (Done) and red (Not Done) cells; unlogged days stay dark
    sns.heatmap(attendance_grid, cmap=[STATUS_COLORS["Not Done"], STATUS_COLORS["Done"]], vmin=0, vmax=1, cbar=False, linewidths=0.6, linecolor="#0e1117", ax=axis)
    legend_items = [plt.Rectangle((0, 0), 1, 1, facecolor=fill, edgecolor=edge, label=text) for fill, edge, text in [(STATUS_COLORS["Done"], "#0e1117", "Attended (Done)"), (STATUS_COLORS["Not Done"], "#0e1117", "Missed (Not Done)"), ("#161b22", "#484f58", "Not Logged")]]

    axis.set_title("30-Day Attendance Heatmap", color="white", fontsize=13, pad=12)
    axis.set_xlabel("Date (DD-MM)", color="white", labelpad=8)
    axis.set_ylabel("Habit", color="white", labelpad=8)
    axis.tick_params(axis="x", colors="white", rotation=45)
    axis.tick_params(axis="y", colors="white", rotation=0)
    plt.setp(axis.get_xticklabels(), ha="right")
    axis.legend(handles=legend_items, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False, labelcolor="white", fontsize=10)

    figure.tight_layout()
    st.pyplot(figure, clear_figure=True)
    plt.close(figure)


# --- Sidebar Navigation & Session State Setup ---
st.sidebar.title("📈 Habit Tracker")
selected_page = st.sidebar.radio("Navigation", PAGES, index=0)

# Load CSV once into st.session_state so edits persist across reruns
if "habits_df" not in st.session_state:
    st.session_state["habits_df"] = load_data()
habits_df = st.session_state["habits_df"]
unique_habits = get_unique_habits(habits_df)

# Show feedback banner and celebration animation after button clicks
if "flash" in st.session_state:
    flash_level, flash_message = st.session_state.pop("flash")
    if flash_level == "info":
        st.info(flash_message)
    else:
        st.success(flash_message)
    if flash_level == "reward":
        st.balloons()
    elif flash_level == "done":
        rain(emoji="🎉", font_size=48, falling_speed=4, animation_length=1)
    else:
        st.toast(flash_message)


# ==============================================================================
# PAGE 1: LOG HABIT (DAILY CHECK-INS & STREAK MILESTONES)
# ==============================================================================
if selected_page == "Log Habit":
    st.title("✅ Log Habit")
    if unique_habits.empty:
        st.info("No habits yet. Add your first habit on **Add Habit**.")
    else:
        # Cap the date picker at today so users cannot log future dates
        picked_date = st.date_input("Check-in Date", value=dt.date.today(), max_value=dt.date.today())
        date_text = str(picked_date)
        active_habits = unique_habits[unique_habits["Start_Date"] <= date_text]

        if active_habits.empty:
            st.info("No habits are active on this date yet.")
        else:
            # Show today's completion count and progress bar
            day_logs = habits_df[habits_df["Date"] == date_text]
            done_today = day_logs[(day_logs["Habit"].isin(active_habits["Habit"])) & (day_logs["Status"] == "Done")]["Habit"].nunique()
            st.write(f"**Today's Progress:** {done_today} of {len(active_habits)} completed")
            st.progress(done_today / len(active_habits))

            # Render one check-in row per active habit
            for _, habit_row in active_habits.iterrows():
                habit_name = habit_row["Habit"]
                existing_log = day_logs[day_logs["Habit"] == habit_name]
                current_streak, _ = get_streaks(habits_df, habit_name, picked_date)
                logged_status, logged_excuse = (existing_log.iloc[0]["Status"], existing_log.iloc[0]["Excuse"]) if not existing_log.empty else ("", "")

                if logged_status == "Done":
                    status_badge = ":green[Completed]" + (f" • 🔥 {current_streak}-day streak" if current_streak > 0 else "")
                elif logged_status == "Not Done":
                    status_badge = ":red[Missed]" + (f" — *{logged_excuse}*" if logged_excuse else "")
                else:
                    status_badge = ":gray[Pending]"

                info_col, done_col, miss_col = st.columns([3.5, 1, 1])
                info_col.markdown(f"{CATEGORY_ICONS.get(habit_row['Category'], '📌')} **{habit_name}** — {status_badge}")
                info_col.caption(f"{habit_row['Category']} • {habit_row['Frequency']} • Goal: {habit_row['Goal']}")

                # Done button: triggers st.balloons() on 7-day milestones, or emoji rain on any normal check-in
                if done_col.button("✅ Done", key=f"done_{habit_name}_{date_text}", width="stretch"):
                    st.session_state.pop("pending_excuse", None)
                    updated_df = add_log(habits_df, habit_name, picked_date, "Done")
                    save_data(updated_df)
                    new_streak, _ = get_streaks(updated_df, habit_name, picked_date)
                    if new_streak > 0 and new_streak % 7 == 0:
                        st.session_state["flash"] = ("reward", f"🎉 Milestone reached! {new_streak} days in a row on '{habit_name}'!")
                    else:
                        day_word = "day" if new_streak == 1 else "days"
                        st.session_state["flash"] = ("done", f"Great job! You completed '{habit_name}' — {new_streak} {day_word} in a row!")
                    st.rerun()

                # Not Done button: opens an inline excuse prompt below this habit
                if miss_col.button("❌ Not Done", key=f"miss_{habit_name}_{date_text}", width="stretch"):
                    st.session_state["pending_excuse"] = {"habit": habit_name, "date": date_text}
                    st.rerun()

                if st.session_state.get("pending_excuse") == {"habit": habit_name, "date": date_text}:
                    with st.container(border=True):
                        chosen_reason = st.selectbox(f"Why was {habit_name} missed?", EXCUSE_OPTIONS, key=f"exc_{habit_name}_{date_text}")
                        custom_reason = st.text_input("Custom reason", key=f"cust_{habit_name}_{date_text}") if chosen_reason == "Other (custom)" else ""
                        save_col, cancel_col = st.columns(2)
                        if save_col.button("Save Miss", type="primary", key=f"save_exc_{habit_name}_{date_text}", width="stretch"):
                            final_reason = "" if chosen_reason == "No excuse" else (custom_reason.strip() if chosen_reason == "Other (custom)" else chosen_reason)
                            if chosen_reason == "Other (custom)" and not final_reason:
                                st.warning("Type a custom reason or choose 'No excuse'.")
                            else:
                                save_data(add_log(habits_df, habit_name, picked_date, "Not Done", excuse=final_reason))
                                st.session_state.pop("pending_excuse", None)
                                st.session_state["flash"] = ("info", f"Logged '{habit_name}' as Not Done ({final_reason or 'No excuse'}).")
                                st.rerun()
                        if cancel_col.button("Cancel", key=f"cancel_exc_{habit_name}_{date_text}", width="stretch"):
                            st.session_state.pop("pending_excuse", None)
                            st.rerun()

        # Summary strip of current and best streaks for every habit
        st.divider()
        st.subheader("🔥 Streaks & Milestones")
        streak_table = get_streak_table(habits_df, unique_habits["Habit"], picked_date)
        if milestone_habits := streak_table[streak_table["Current"] >= 7]["Habit"].tolist():
            st.success(f"🔥 7+ day streak milestone active: {', '.join(milestone_habits)}")
        for start_index in range(0, len(streak_table), 4):
            for card_col, (_, streak_row) in zip(st.columns(4), streak_table.iloc[start_index : start_index + 4].iterrows()):
                card_col.metric(streak_row["Habit"], f"{streak_row['Current']} days")
                card_col.caption(f"Best: {streak_row['Best']} days")


# ==============================================================================
# PAGE 2: ADD HABIT
# ==============================================================================
elif selected_page == "Add Habit":
    st.title("➕ Add Habit")
    with st.form("add_habit_form", clear_on_submit=True):
        habit_name_input = st.text_input("Habit Name", placeholder="e.g. Morning Walk")
        category_col, frequency_col = st.columns(2)
        category_input, frequency_input = category_col.selectbox("Category", CATEGORIES), frequency_col.selectbox("Frequency", FREQUENCIES)
        goal_col, start_date_col = st.columns(2)
        goal_input, start_date_input = goal_col.number_input("Goal (times per period)", 1, 1000, 1, 1), start_date_col.date_input("Start Date", value=dt.date.today())

        if st.form_submit_button("Add Habit", type="primary"):
            clean_name = habit_name_input.strip()
            if not clean_name or clean_name.lower() in {existing.lower() for existing in habits_df["Habit"].unique()}:
                st.error("Habit name must be non-empty and unique.")
            else:
                new_habit = {"Habit": clean_name, "Category": category_input, "Frequency": frequency_input, "Goal": str(int(goal_input)), "Start_Date": str(start_date_input), "Date": "", "Status": "", "Excuse": ""}
                save_data(pd.concat([habits_df, pd.DataFrame([new_habit])], ignore_index=True))
                st.success(f"Added '{clean_name}'! Go to **Log Habit** to check in.")
                unique_habits = get_unique_habits(st.session_state["habits_df"])

    # Preview up to 10 existing habits below the form
    if not unique_habits.empty:
        st.subheader("Current Habits")
        st.dataframe(unique_habits.head(10), hide_index=True, width="stretch")


# ==============================================================================
# PAGE 3: MANAGE HABITS (INTERACTIVE TABLE + CSV UPLOAD / DOWNLOAD)
# ==============================================================================
elif selected_page == "Manage Habits":
    st.title("⚙️ Manage Habits")
    st.caption("Edit cells, add rows at the bottom, or select rows and press Delete. Click Save when done.")

    # Prepare typed columns so st.data_editor shows dropdowns, number inputs, and date pickers
    editable_df = unique_habits.copy() if not unique_habits.empty else pd.DataFrame({col: pd.Series(dtype="int64" if col == "Goal" else "object") for col in HABIT_COLUMNS})
    if not editable_df.empty:
        editable_df["Goal"] = pd.to_numeric(editable_df["Goal"], errors="coerce").fillna(1).clip(1, 1000).astype(int)
        editable_df["Start_Date"] = pd.to_datetime(editable_df["Start_Date"], errors="coerce").dt.date

    original_names, editor_version = dict(zip(editable_df.index, editable_df["Habit"])), st.session_state.get("editor_version", 0)
    column_settings = {
        "Habit": st.column_config.TextColumn("Habit", required=True), "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, required=True),
        "Frequency": st.column_config.SelectboxColumn("Frequency", options=FREQUENCIES, required=True), "Goal": st.column_config.NumberColumn("Goal", min_value=1, max_value=1000, step=1, required=True),
        "Start_Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD", required=True),
    }
    edited_df = st.data_editor(editable_df, num_rows="dynamic", hide_index=True, width="stretch", key=f"editor_{editor_version}", column_config=column_settings)

    if st.button("💾 Save Table Changes", type="primary"):
        updated_df, validation_errors = apply_table_edits(habits_df, edited_df, original_names, st.session_state.get(f"editor_{editor_version}", {}).get("deleted_rows", []))
        if validation_errors:
            st.error("\n".join(validation_errors))
        else:
            save_data(updated_df)
            st.session_state["flash"] = ("success", "Saved table changes!")
            st.rerun()

    # CSV upload with schema/value validation + UTF-8 CSV download
    st.divider()
    st.subheader("CSV Data Tools")
    if uploaded_file := st.file_uploader("Upload CSV (replaces active dataset after validation)", type="csv"):
        try:
            uploaded_df = pd.read_csv(uploaded_file, dtype=str).fillna("")
            goal_values = pd.to_numeric(uploaded_df["Goal"], errors="coerce") if "Goal" in uploaded_df.columns else pd.Series(dtype=float)
            if list(uploaded_df.columns) != COLUMNS:
                st.error(f"Columns must be: {', '.join(COLUMNS)}")
            elif (uploaded_df["Habit"].str.strip() == "").any() or goal_values.isna().any() or (goal_values % 1 != 0).any() or (goal_values < 1).any() or (goal_values > 1000).any():
                st.error("Habit names cannot be empty and Goal must be whole numbers (1-1000).")
            else:
                st.success(f"Valid CSV: {len(uploaded_df)} rows across {uploaded_df['Habit'].nunique()} habits.")
                if st.button("Replace active dataset with uploaded CSV", type="primary"):
                    save_data(uploaded_df)
                    st.session_state["flash"] = ("success", "Replaced active dataset with uploaded CSV.")
                    st.rerun()
        except Exception as error:
            st.error(f"Upload rejected: {error}")

    st.download_button("⬇️ Download current dataset", habits_df.to_csv(index=False).encode("utf-8"), "habits.csv", "text/csv")


# ==============================================================================
# PAGE 4: MY PROGRESS (COMPLETION RATE, STREAKS & CHARTS)
# ==============================================================================
elif selected_page == "My Progress":
    st.title("📊 My Progress")
    if unique_habits.empty:
        st.info("No habits yet. Add one on **Add Habit**.")
    else:
        # Interactive category checkboxes and status filter update every chart live
        checkbox_cols = st.columns(3)
        selected_categories = [category for idx, category in enumerate(CATEGORIES) if checkbox_cols[idx % 3].checkbox(f"{CATEGORY_ICONS[category]} {category}", value=True, key=f"cb_{category}")]
        status_filter = st.radio("Show records", ["All", "Done", "Not Done"], horizontal=True)

        category_logs = habits_df[(habits_df["Date"] != "") & (habits_df["Category"].isin(selected_categories))]
        filtered_logs = category_logs if status_filter == "All" else category_logs[category_logs["Status"] == status_filter]

        if not selected_categories or filtered_logs.empty:
            st.info("No logged check-ins match these filters yet.")
        else:
            # Overall completion rate + Done vs Not Done pie chart
            rate_col, pie_col = st.columns(2)
            completion_rate = (category_logs["Status"] == "Done").mean() * 100
            rate_col.metric("Overall Completion Rate", f"{completion_rate:.1f}%")
            rate_col.progress(completion_rate / 100.0)
            pie_col.plotly_chart(px.pie(category_logs["Status"].value_counts().reset_index(name="Count"), names="Status", values="Count", color="Status", color_discrete_map=STATUS_COLORS, title="Done vs Not Done", template="plotly_dark"), width="stretch")

            # Grouped bar chart of check-ins by category
            st.plotly_chart(px.bar(filtered_logs.groupby(["Category", "Status"]).size().reset_index(name="Count"), x="Category", y="Count", color="Status", barmode="group", color_discrete_map=STATUS_COLORS, title="Check-ins by Category", template="plotly_dark"), width="stretch")

            # Grouped bar chart comparing Current vs Best streaks for selected categories
            streak_table = get_streak_table(habits_df, unique_habits[unique_habits["Category"].isin(selected_categories)]["Habit"], dt.date.today())
            if not streak_table.empty:
                st.plotly_chart(px.bar(streak_table.melt(id_vars="Habit", var_name="Type", value_name="Days"), x="Habit", y="Days", color="Type", barmode="group", title="Current vs Best Streak", template="plotly_dark"), width="stretch")

            # 30-day attendance heatmap
            show_heatmap(filtered_logs)


# ==============================================================================
# PAGE 5: EXCUSE MANAGER (PHASE 3 INNOVATION)
# ==============================================================================
elif selected_page == "Excuse Manager":
    st.title("📝 Excuse Manager")
    missed_logs = habits_df[(habits_df["Status"] == "Not Done") & (habits_df["Date"] != "")].sort_values("Date", ascending=False).copy()
    if missed_logs.empty:
        st.info("No missed habits (`Not Done`) recorded yet.")
    else:
        missed_logs["Excuse"] = missed_logs["Excuse"].replace("", "No excuse logged")
        written_excuses = missed_logs[missed_logs["Excuse"] != "No excuse logged"]
        most_missed, top_excuses = missed_logs["Habit"].value_counts(), written_excuses["Excuse"].value_counts()

        # Three KPI summary cards
        total_col, top_habit_col, top_excuse_col = st.columns(3)
        total_col.metric("Total Missed Check-ins", len(missed_logs))
        top_habit_col.metric("Most Missed Habit", most_missed.index[0], f"{int(most_missed.iloc[0])} misses", delta_color="off")
        top_excuse_col.metric("Top Excuse Reason", top_excuses.index[0] if not top_excuses.empty else "None", f"{int(top_excuses.iloc[0])} times" if not top_excuses.empty else "0 logged", delta_color="off")

        # Preview latest 5 missed logs, with a checkbox to expand full history
        st.dataframe(missed_logs[["Date", "Habit", "Category", "Excuse"]].head(None if st.checkbox("View full Excuse History") else 5), hide_index=True, width="stretch")

        # Side-by-side bar charts of most missed habits and top excuse reasons
        habit_chart_col, excuse_chart_col = st.columns(2)
        habit_chart_col.plotly_chart(px.bar(missed_logs.groupby(["Habit", "Category"]).size().reset_index(name="Misses").sort_values("Misses", ascending=False), x="Habit", y="Misses", color="Category", title="Most Missed Habits", template="plotly_dark"), width="stretch")
        if not written_excuses.empty:
            excuse_chart_col.plotly_chart(px.bar(top_excuses.reset_index(name="Count"), x="Excuse", y="Count", title="Top Excuse Reasons", template="plotly_dark", color_discrete_sequence=[STATUS_COLORS["Not Done"]]), width="stretch")
        else:
            excuse_chart_col.info("No written excuses logged yet.")
