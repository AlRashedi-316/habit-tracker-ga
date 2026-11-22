# Habit Tracker App (app.py)
# A Streamlit + Pandas app to add habits, log daily check-ins, track streaks, and manage excuses.

import datetime as dt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import seaborn as sns
import streamlit as st

st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")

# --- Constants & Configuration ---
DATA_FILE = "data/test_habits.csv"
COLUMNS = ["Habit", "Category", "Frequency", "Goal", "Start_Date", "Date", "Status", "Excuse"]
HABIT_COLS = ["Habit", "Category", "Frequency", "Goal", "Start_Date"]
CATEGORIES = ["Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"]
FREQUENCIES = ["Daily", "Weekly"]
PREDEFINED_EXCUSES = ["Forgot", "Too tired", "Sick", "Ran out of time", "Bad weather"]
CATEGORY_ICONS = {
    "Health": "💧",
    "Fitness": "🏃",
    "Learning": "📖",
    "Mindfulness": "🧘",
    "Productivity": "⚡",
    "Other": "📌",
}
STATUS_COLORS = {"Done": "#2e9e5b", "Not Done": "#d9534f"}
PAGES = ["Log Habit", "Add Habit", "Manage Habits", "My Progress", "Excuse Manager"]


# --- Data & Helper Functions ---
def load_data():
    """Load the CSV file into a pandas DataFrame with clean string values."""
    try:
        df = pd.read_csv(DATA_FILE, dtype=str).fillna("")
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[COLUMNS]
    except FileNotFoundError:
        st.warning(f"File '{DATA_FILE}' not found. Starting with an empty tracker.")
        return pd.DataFrame(columns=COLUMNS)
    except Exception as error:
        st.error(f"Error loading {DATA_FILE}: {error}")
        return pd.DataFrame(columns=COLUMNS)


def save_data(df):
    """Save the DataFrame to session state and write it back to the CSV file."""
    clean_df = df[COLUMNS].reset_index(drop=True).copy()
    st.session_state["habits_df"] = clean_df
    st.session_state["editor_ver"] = st.session_state.get("editor_ver", 0) + 1
    try:
        clean_df.to_csv(DATA_FILE, index=False)
    except Exception as error:
        st.warning(f"Saved in session, but could not write to '{DATA_FILE}': {error}. Use Download CSV to back up.")
    return True


def get_habits(df):
    """Return one row per unique habit using drop_duplicates()."""
    if df.empty:
        return pd.DataFrame(columns=HABIT_COLS)
    return df.drop_duplicates(subset=["Habit"])[HABIT_COLS].reset_index(drop=True)


def check_name(name, df, editing_habit=None):
    """Validate that a habit name is not blank or a duplicate (case-insensitive)."""
    clean = name.strip()
    if not clean:
        return "Habit name cannot be empty."
    taken = {h.lower() for h in df["Habit"].unique() if h != editing_habit}
    if clean.lower() in taken:
        return f"A habit named '{clean}' already exists."
    return None


def get_streaks(df, habit_name, reference_date):
    """Calculate (current_streak, best_streak) from consecutive Done dates."""
    done = df[(df["Habit"] == habit_name) & (df["Status"] == "Done") & (df["Date"] != "")]
    dates = pd.to_datetime(done["Date"], errors="coerce").dropna().dt.date.drop_duplicates().sort_values().tolist()
    if not dates:
        return 0, 0

    best = run = 0
    prev = None
    for day in dates:
        run = run + 1 if prev is not None and (day - prev).days == 1 else 1
        best = max(best, run)
        prev = day

    # Current streak stays alive if completed on reference_date or the day before
    past_dates = [d for d in dates if d <= reference_date]
    current = 0
    if past_dates and (reference_date - past_dates[-1]).days <= 1:
        current = 1
        for i in range(len(past_dates) - 2, -1, -1):
            if (past_dates[i + 1] - past_dates[i]).days == 1:
                current += 1
            else:
                break
    return current, best


def get_streak_table(df, habit_names, reference_date):
    """Build a DataFrame of current and best streaks for each habit."""
    rows = []
    for habit in habit_names:
        current, best = get_streaks(df, habit, reference_date)
        rows.append({"Habit": habit, "Current": current, "Best": best})
    return pd.DataFrame(rows)


def add_log(df, habit_name, log_date, status, excuse=""):
    """Add or update a check-in row and remove any blank placeholder row."""
    matches = df[df["Habit"] == habit_name]
    if matches.empty:
        return df
    info = matches.iloc[0]
    date_text = str(log_date)
    new_row = {
        "Habit": habit_name,
        "Category": info["Category"],
        "Frequency": info["Frequency"],
        "Goal": str(info["Goal"]),
        "Start_Date": info["Start_Date"],
        "Date": date_text,
        "Status": status,
        "Excuse": excuse,
    }
    keep_mask = ~((df["Habit"] == habit_name) & ((df["Date"] == date_text) | (df["Date"] == "")))
    return pd.concat([df[keep_mask], pd.DataFrame([new_row])], ignore_index=True)


def apply_table_edits(df, edited_df, original_names, deleted_positions=None):
    """Validate st.data_editor rows and keep historical logs when habits are renamed."""
    errors, seen, cleaned = [], set(), []
    deleted = set(deleted_positions or [])
    active_originals = {
        idx: name for pos, (idx, name) in enumerate(original_names.items()) if pos not in deleted
    }

    for pos, (row_idx, row) in enumerate(edited_df.iterrows(), start=1):
        habit = "" if pd.isna(row.get("Habit")) else str(row["Habit"]).strip()
        cat = "" if pd.isna(row.get("Category")) else str(row["Category"]).strip()
        freq = "" if pd.isna(row.get("Frequency")) else str(row["Frequency"]).strip()
        goal = pd.to_numeric(row.get("Goal"), errors="coerce")
        raw_start = row.get("Start_Date")
        start = pd.NaT if pd.isna(raw_start) or str(raw_start).strip() == "" else pd.to_datetime(raw_start, errors="coerce")

        if not habit:
            errors.append(f"Row {pos}: Habit name cannot be empty.")
        elif habit.lower() in seen:
            errors.append(f"Row {pos}: Duplicate habit name '{habit}'.")
        else:
            seen.add(habit.lower())

        if cat not in CATEGORIES:
            errors.append(f"Row {pos}: Please choose a valid Category.")
        if freq not in FREQUENCIES:
            errors.append(f"Row {pos}: Please choose a valid Frequency.")
        if pd.isna(goal) or goal % 1 != 0 or not (1 <= goal <= 1000):
            errors.append(f"Row {pos}: Goal must be a whole number between 1 and 1000.")
        if pd.isna(start):
            errors.append(f"Row {pos}: Please enter a valid Start Date.")

        if not errors:
            cleaned.append({
                "idx": row_idx,
                "Habit": habit,
                "Category": cat,
                "Frequency": freq,
                "Goal": str(int(goal)),
                "Start_Date": start.strftime("%Y-%m-%d"),
            })

    if errors:
        return None, errors

    # Rebuild full table so edited/renamed habits preserve their existing check-in history
    frames = []
    for item in cleaned:
        if item["idx"] in active_originals:
            logs = df[df["Habit"] == active_originals[item["idx"]]].copy()
            if not logs.empty:
                for col in HABIT_COLS:
                    logs[col] = item[col]
                frames.append(logs)
                continue
        new_row = {col: item[col] for col in HABIT_COLS}
        new_row.update({"Date": "", "Status": "", "Excuse": ""})
        frames.append(pd.DataFrame([new_row]))

    if not frames:
        return pd.DataFrame(columns=COLUMNS), []
    return pd.concat(frames, ignore_index=True)[COLUMNS], []


def show_heatmap(records):
    """Plot a 30-day Habit x Date attendance heatmap using pivot_table() and Seaborn."""
    hm = records.copy()
    hm["parsed_date"] = pd.to_datetime(hm["Date"], errors="coerce")
    hm = hm.dropna(subset=["parsed_date"])
    hm = hm[hm["Status"].isin(["Done", "Not Done"])]
    if hm.empty:
        st.info("No dated check-in records are available for the heatmap with the current filters.")
        return

    start_date = hm["parsed_date"].max() - pd.Timedelta(days=29)
    recent = hm[hm["parsed_date"] >= start_date].copy()
    if recent.empty:
        st.info("No check-in records fall inside the 30-day heatmap window.")
        return

    # Encode Done = 1.0, Not Done = 0.0 with np.where(), then pivot into a 2D matrix
    recent["status_code"] = np.where(recent["Status"] == "Done", 1.0, 0.0)
    grid = recent.pivot_table(index="Habit", columns="parsed_date", values="status_code", aggfunc="max")
    if grid.empty:
        st.info("Not enough data to draw the attendance heatmap.")
        return

    grid = grid.sort_index(axis=1)
    grid.columns = [d.strftime("%m-%d") for d in grid.columns]

    fig_w = max(8.0, 0.42 * grid.shape[1] + 2.2)
    fig_h = max(2.8, 0.55 * grid.shape[0] + 1.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#161b22")

    sns.heatmap(
        grid,
        cmap=[STATUS_COLORS["Not Done"], STATUS_COLORS["Done"]],
        vmin=0,
        vmax=1,
        cbar=False,
        linewidths=0.6,
        linecolor="#0e1117",
        ax=ax,
    )

    legend_specs = [
        (STATUS_COLORS["Done"], "#0e1117", "Attended (Done)"),
        (STATUS_COLORS["Not Done"], "#0e1117", "Missed (Not Done)"),
        ("#161b22", "#484f58", "Not Logged"),
    ]
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=fc, edgecolor=ec, label=lbl) for fc, ec, lbl in legend_specs]

    ax.set_title("30-Day Attendance Heatmap", color="white", fontsize=13, pad=12)
    ax.set_xlabel("Date (MM-DD)", color="white", labelpad=8)
    ax.set_ylabel("")
    ax.tick_params(axis="x", colors="white", rotation=45)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    ax.tick_params(axis="y", colors="white", rotation=0)
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False, labelcolor="white", fontsize=10)

    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)


# --- Sidebar & Session State Setup ---
st.sidebar.title("📈 Habit Tracker")
selected_page = st.sidebar.radio("Navigation", PAGES, index=0)

if "habits_df" not in st.session_state:
    st.session_state["habits_df"] = load_data()

habits_data = st.session_state["habits_df"]
habit_list = get_habits(habits_data)


# ==============================================================================
# PAGE 1: LOG HABIT (DEFAULT HOME / DAILY CHECK-INS)
# ==============================================================================
if selected_page == "Log Habit":
    st.title("✅ Log Habit")
    st.caption("Daily check-ins, live streak tracking, and quick accountability.")

    if "reward" in st.session_state:
        st.success(st.session_state.pop("reward"))
        st.balloons()

    if "log_feedback" in st.session_state:
        level, msg = st.session_state.pop("log_feedback")
        if level == "success":
            st.success(msg)
        else:
            st.info(msg)
        st.toast(msg)

    if habit_list.empty:
        st.info("Your tracker is currently empty. Add your first habit on **Add Habit**.")
    else:
        st.subheader("Daily Check-In")
        today = dt.date.today()
        picked_date = st.date_input("Check-in Date", value=today, max_value=today)
        date_text = str(picked_date)
        active_habits = habit_list[habit_list["Start_Date"] <= date_text]

        if active_habits.empty:
            st.info("No habits are active on this date yet. Check the Start Date or add a habit on **Add Habit**.")
        else:
            day_logs = habits_data[habits_data["Date"] == date_text]
            done_today = day_logs[(day_logs["Habit"].isin(active_habits["Habit"])) & (day_logs["Status"] == "Done")]["Habit"].nunique()
            total_active = len(active_habits)
            st.write(f"**Today's Progress:** {done_today} of {total_active} completed")
            st.progress(done_today / total_active)

            for _, habit_row in active_habits.iterrows():
                habit_name = habit_row["Habit"]
                icon = CATEGORY_ICONS.get(habit_row["Category"], "📌")
                existing = day_logs[day_logs["Habit"] == habit_name]
                current_streak, _ = get_streaks(habits_data, habit_name, picked_date)

                if not existing.empty:
                    status = existing.iloc[0]["Status"]
                    excuse = existing.iloc[0]["Excuse"]
                    if status == "Done":
                        streak_note = f" • 🔥 {current_streak}-day streak" if current_streak > 0 else ""
                        status_label = f":green[Completed]{streak_note}"
                    else:
                        excuse_note = f" — *{excuse}*" if excuse else ""
                        status_label = f":red[Missed]{excuse_note}"
                else:
                    status_label = ":gray[Pending]"

                info_col, done_col, miss_col = st.columns([3.5, 1, 1])
                with info_col:
                    st.markdown(f"{icon} **{habit_name}** — {status_label}")
                    st.caption(f"{habit_row['Category']} • {habit_row['Frequency']} • Goal: {habit_row['Goal']}")

                if done_col.button("✅ Done", key=f"done_{habit_name}_{date_text}", width="stretch"):
                    if st.session_state.get("pending_excuse", {}).get("habit") == habit_name:
                        st.session_state.pop("pending_excuse", None)
                    updated = add_log(habits_data, habit_name, picked_date, "Done")
                    if save_data(updated):
                        new_streak, _ = get_streaks(updated, habit_name, picked_date)
                        if new_streak > 0 and new_streak % 7 == 0:
                            st.session_state["reward"] = f"🎉 Milestone reached! {new_streak}-day streak on '{habit_name}'!"
                        else:
                            unit = "day" if new_streak == 1 else "days"
                            st.session_state["log_feedback"] = (
                                "success",
                                f"Nice work! Completed '{habit_name}' for {date_text} (Current streak: {new_streak} {unit}).",
                            )
                        st.rerun()

                if miss_col.button("❌ Not Done", key=f"notdone_{habit_name}_{date_text}", width="stretch"):
                    st.session_state["pending_excuse"] = {"habit": habit_name, "date": date_text}
                    st.rerun()

                # Inline excuse prompt right below the missed habit
                if st.session_state.get("pending_excuse") == {"habit": habit_name, "date": date_text}:
                    with st.container(border=True):
                        st.write(f"📝 Why was **{habit_name}** missed on **{date_text}**?")
                        choice = st.selectbox("Choose a reason", PREDEFINED_EXCUSES + ["Other (custom)"], key=f"exc_choice_{habit_name}_{date_text}")
                        custom = st.text_input("Type your custom reason", placeholder="e.g. Traveling, family event", key=f"exc_custom_{habit_name}_{date_text}") if choice == "Other (custom)" else ""

                        save_col, skip_col, cancel_col = st.columns([2, 2, 1])
                        if save_col.button("Save Miss & Excuse", type="primary", key=f"save_exc_{habit_name}_{date_text}", width="stretch"):
                            reason = custom.strip() if choice == "Other (custom)" else choice
                            if not reason:
                                st.warning("Please type a custom reason or click Skip Excuse.")
                            elif save_data(add_log(habits_data, habit_name, picked_date, "Not Done", excuse=reason)):
                                st.session_state.pop("pending_excuse", None)
                                st.session_state["log_feedback"] = ("info", f"Logged '{habit_name}' as Not Done for {date_text} (Reason: {reason}).")
                                st.rerun()

                        if skip_col.button("Skip Excuse", key=f"skip_exc_{habit_name}_{date_text}", width="stretch"):
                            if save_data(add_log(habits_data, habit_name, picked_date, "Not Done")):
                                st.session_state.pop("pending_excuse", None)
                                st.session_state["log_feedback"] = ("info", f"Logged '{habit_name}' as Not Done for {date_text} (No excuse added).")
                                st.rerun()

                        if cancel_col.button("Cancel", key=f"cancel_exc_{habit_name}_{date_text}", width="stretch"):
                            st.session_state.pop("pending_excuse", None)
                            st.rerun()

        # --- Streaks & Milestones ---
        st.divider()
        st.subheader("🔥 Streaks & Milestones")
        streak_table = get_streak_table(habits_data, habit_list["Habit"], picked_date)

        milestones = streak_table[streak_table["Current"] >= 7]["Habit"].tolist()
        if milestones:
            st.success(f"🔥 7+ day streak milestone active: {', '.join(milestones)}")

        for start in range(0, len(streak_table), 4):
            cols = st.columns(4)
            for col, (_, row) in zip(cols, streak_table.iloc[start : start + 4].iterrows()):
                col.metric(row["Habit"], f"{row['Current']} days")
                col.caption(f"Best: {row['Best']} days")


# ==============================================================================
# PAGE 2: ADD HABIT
# ==============================================================================
elif selected_page == "Add Habit":
    st.title("➕ Add Habit")
    st.caption("Create a new habit and start tracking it on Log Habit.")

    with st.form("add_form", clear_on_submit=True):
        name_input = st.text_input("Habit Name", placeholder="e.g. Morning Walk")
        cat_col, freq_col = st.columns(2)
        cat_input = cat_col.selectbox("Category", CATEGORIES)
        freq_input = freq_col.selectbox("Frequency", FREQUENCIES)

        goal_col, start_col = st.columns(2)
        goal_input = goal_col.number_input("Goal (times per period)", min_value=1, max_value=1000, value=1, step=1)
        start_input = start_col.date_input("Start Date", value=dt.date.today())

        if st.form_submit_button("Add Habit", type="primary"):
            error = check_name(name_input, habits_data)
            if error:
                st.error(error)
            else:
                clean = name_input.strip()
                new_habit = {
                    "Habit": clean,
                    "Category": cat_input,
                    "Frequency": freq_input,
                    "Goal": str(int(goal_input)),
                    "Start_Date": str(start_input),
                    "Date": "",
                    "Status": "",
                    "Excuse": "",
                }
                if save_data(pd.concat([habits_data, pd.DataFrame([new_habit])], ignore_index=True)):
                    st.success(f"Added '{clean}'! Head to **Log Habit** to record check-ins.")
                    habits_data = st.session_state["habits_df"]
                    habit_list = get_habits(habits_data)

    if not habit_list.empty:
        st.divider()
        st.subheader("Current Habits Preview")
        st.dataframe(habit_list.head(10), hide_index=True, width="stretch")


# ==============================================================================
# PAGE 3: MANAGE HABITS
# ==============================================================================
elif selected_page == "Manage Habits":
    st.title("⚙️ Manage Habits")
    st.caption("Edit or delete habits individually or in the interactive table, and manage CSV data.")

    if "manage_feedback" in st.session_state:
        msg = st.session_state.pop("manage_feedback")
        st.success(msg)
        st.toast(msg)

    dropdown_tab, table_tab = st.tabs(["Edit by Habit", "Interactive Table"])

    with dropdown_tab:
        st.subheader("Edit or Delete a Habit")
        if habit_list.empty:
            st.info("No habits to manage yet. Add one on **Add Habit** or use the **Interactive Table** tab.")
        else:
            chosen = st.selectbox("Select a habit to manage", options=habit_list["Habit"].tolist(), index=None, placeholder="Choose a habit...")
            if chosen is None:
                st.info("Select a habit from the dropdown above to inspect its details, edit it, or delete it.")
            else:
                row = habit_list[habit_list["Habit"] == chosen].iloc[0]
                logged_days = int(((habits_data["Habit"] == chosen) & (habits_data["Date"] != "")).sum())

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Category", row["Category"])
                c2.metric("Frequency", row["Frequency"])
                c3.metric("Goal", row["Goal"])
                c4.metric("Logged Days", logged_days)
                st.caption(f"Start Date: `{row['Start_Date']}`")

                with st.form("edit_form"):
                    new_name = st.text_input("Name", value=chosen)
                    freq_idx = FREQUENCIES.index(row["Frequency"]) if row["Frequency"] in FREQUENCIES else 0
                    new_freq = st.selectbox("Frequency", FREQUENCIES, index=freq_idx)
                    try:
                        goal_val = max(1, min(1000, int(float(row["Goal"]))))
                    except Exception:
                        goal_val = 1
                    new_goal = st.number_input("Goal (times per period)", min_value=1, max_value=1000, value=goal_val, step=1)
                    cat_idx = CATEGORIES.index(row["Category"]) if row["Category"] in CATEGORIES else 0
                    new_cat = st.selectbox("Category", CATEGORIES, index=cat_idx)
                    try:
                        start_val = dt.date.fromisoformat(row["Start_Date"])
                    except Exception:
                        start_val = dt.date.today()
                    new_start = st.date_input("Start Date", value=start_val)

                    if st.form_submit_button("Save Changes", type="primary"):
                        error = check_name(new_name, habits_data, editing_habit=chosen)
                        if error:
                            st.error(error)
                        else:
                            clean = new_name.strip()
                            updated = habits_data.copy()
                            mask = updated["Habit"] == chosen
                            new_values = [clean, new_cat, new_freq, str(int(new_goal)), str(new_start)]
                            for col, val in zip(HABIT_COLS, new_values):
                                updated.loc[mask, col] = val
                            if save_data(updated):
                                st.session_state["manage_feedback"] = f"Updated '{clean}'!"
                                st.rerun()

                if st.button(f"🗑️ Delete '{chosen}' and all its logs"):
                    if save_data(habits_data[habits_data["Habit"] != chosen]):
                        st.session_state["manage_feedback"] = f"Deleted '{chosen}'."
                        st.rerun()

    with table_tab:
        st.subheader("Interactive Habits Table")
        st.caption("Edit cells directly, add new rows at the bottom, or select rows and press Delete. Click Save Table Changes when finished.")

        if habit_list.empty:
            editable = pd.DataFrame({c: pd.Series(dtype="int64" if c == "Goal" else "object") for c in HABIT_COLS})
        else:
            editable = habit_list.copy()
            editable["Goal"] = pd.to_numeric(editable["Goal"], errors="coerce").fillna(1).clip(1, 1000).astype(int)
            editable["Start_Date"] = pd.to_datetime(editable["Start_Date"], errors="coerce").dt.date

        original_names = dict(zip(editable.index, editable["Habit"]))
        ver = st.session_state.get("editor_ver", 0)
        edited = st.data_editor(
            editable,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"habits_editor_{ver}",
            column_config={
                "Habit": st.column_config.TextColumn("Habit", required=True),
                "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, required=True),
                "Frequency": st.column_config.SelectboxColumn("Frequency", options=FREQUENCIES, required=True),
                "Goal": st.column_config.NumberColumn("Goal", min_value=1, max_value=1000, step=1, required=True),
                "Start_Date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD", required=True),
            },
        )

        if st.button("💾 Save Table Changes", type="primary"):
            deleted_pos = st.session_state.get(f"habits_editor_{ver}", {}).get("deleted_rows", [])
            updated, errors = apply_table_edits(habits_data, edited, original_names, deleted_pos)
            if errors:
                for err in errors:
                    st.error(err)
            elif save_data(updated):
                st.session_state["manage_feedback"] = "Saved interactive table changes!"
                st.rerun()

    # --- CSV Upload & Download Tools ---
    st.divider()
    st.subheader("CSV Data Tools")
    uploaded_file = st.file_uploader("Upload CSV (replaces active dataset after validation)", type="csv")
    if uploaded_file is not None:
        try:
            uploaded = pd.read_csv(uploaded_file, dtype=str).fillna("")
            goals = pd.to_numeric(uploaded["Goal"], errors="coerce") if "Goal" in uploaded.columns else pd.Series(dtype=float)

            if list(uploaded.columns) != COLUMNS:
                st.error(f"Columns must be exactly: {', '.join(COLUMNS)}")
            elif (uploaded["Habit"].str.strip() == "").any():
                st.error("Habit column cannot contain empty names.")
            elif goals.isna().any() or (goals % 1 != 0).any() or (goals < 1).any() or (goals > 1000).any():
                st.error("Goal column must contain whole numbers between 1 and 1000.")
            else:
                st.success(f"File is valid: {len(uploaded)} rows across {uploaded['Habit'].nunique()} habits.")
                if st.button("Replace active dataset with uploaded CSV", type="primary"):
                    if save_data(uploaded):
                        st.session_state["manage_feedback"] = "Replaced active dataset with uploaded CSV."
                        st.rerun()
        except Exception as error:
            st.error(f"Upload rejected: {error}")

    st.download_button(
        label="⬇️ Download current dataset",
        data=habits_data.to_csv(index=False).encode("utf-8"),
        file_name="habits.csv",
        mime="text/csv",
    )


# ==============================================================================
# PAGE 4: MY PROGRESS
# ==============================================================================
elif selected_page == "My Progress":
    st.title("📊 My Progress")
    st.caption("Filter by category and status to inspect completion trends and attendance.")

    if habit_list.empty:
        st.info("No habits yet. Add one on **Add Habit**.")
    else:
        st.write("**Filter by Category**")
        cb_cols = st.columns(3)
        selected_cats = [
            cat for i, cat in enumerate(CATEGORIES)
            if cb_cols[i % 3].checkbox(f"{CATEGORY_ICONS.get(cat, '')} {cat}", value=True, key=f"cat_cb_{cat}")
        ]
        chosen_status = st.radio("Show records", ["All", "Done", "Not Done"], horizontal=True)

        logged = habits_data[habits_data["Date"] != ""].copy()
        cat_records = logged[logged["Category"].isin(selected_cats)]
        filtered = cat_records if chosen_status == "All" else cat_records[cat_records["Status"] == chosen_status]

        if not selected_cats:
            st.info("Select at least one category checkbox above to view your progress.")
        elif filtered.empty:
            st.info("No logged check-ins match these filters yet.")
        else:
            # --- Overall Completion Rate & Pie Chart ---
            rate_col, pie_col = st.columns(2)
            done_count = int((cat_records["Status"] == "Done").sum())
            total_count = len(cat_records)
            rate = (done_count / total_count * 100) if total_count > 0 else 0.0

            with rate_col:
                st.metric("Overall Completion Rate", f"{rate:.1f}%")
                st.progress(min(max(rate / 100.0, 0.0), 1.0))

            status_counts = cat_records["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            pie_fig = px.pie(
                status_counts, names="Status", values="Count", color="Status",
                color_discrete_map=STATUS_COLORS, title="Done vs Not Done", template="plotly_dark",
            )
            pie_col.plotly_chart(pie_fig, width="stretch")

            # --- Check-ins by Category (Column Chart) ---
            by_cat = filtered.groupby(["Category", "Status"]).size().reset_index(name="Count")
            cat_fig = px.bar(
                by_cat, x="Category", y="Count", color="Status", barmode="group",
                color_discrete_map=STATUS_COLORS, title="Check-ins by Category", template="plotly_dark",
            )
            st.plotly_chart(cat_fig, width="stretch")

            # --- Current vs Best Streak (Column Chart) ---
            today = dt.date.today()
            filtered_habits = habit_list[habit_list["Category"].isin(selected_cats)]
            streak_df = get_streak_table(habits_data, filtered_habits["Habit"], today)
            if not streak_df.empty:
                melted = streak_df.melt(id_vars="Habit", var_name="Type", value_name="Days")
                streak_fig = px.bar(melted, x="Habit", y="Days", color="Type", barmode="group", title="Current vs Best Streak", template="plotly_dark")
                st.plotly_chart(streak_fig, width="stretch")

            # --- Daily Attendance Trend (Line Chart) ---
            trend = filtered.copy()
            trend["parsed_date"] = pd.to_datetime(trend["Date"], errors="coerce")
            trend = trend.dropna(subset=["parsed_date"])
            if not trend.empty:
                daily = trend.groupby(["Date", "Status"]).size().reset_index(name="Count").sort_values("Date")
                line_fig = px.line(
                    daily, x="Date", y="Count", color="Status", markers=True,
                    color_discrete_map=STATUS_COLORS, title="Daily Attendance Trend", template="plotly_dark",
                )
                st.plotly_chart(line_fig, width="stretch")

            # --- 30-Day Attendance Heatmap ---
            st.subheader("30-Day Attendance Grid")
            show_heatmap(filtered)

            with st.expander("View filtered log records"):
                st.dataframe(filtered.sort_values("Date", ascending=False), hide_index=True, width="stretch")


# ==============================================================================
# PAGE 5: EXCUSE MANAGER
# ==============================================================================
elif selected_page == "Excuse Manager":
    st.title("📝 Excuse Manager")
    st.caption("Review missed habits and logged excuses from your active records, update reasons per habit, and spot patterns over time.")

    if "excuse_feedback" in st.session_state:
        msg = st.session_state.pop("excuse_feedback")
        st.success(msg)
        st.toast(msg)

    missed = habits_data[(habits_data["Status"] == "Not Done") & (habits_data["Date"] != "")].sort_values("Date", ascending=False).copy()
    missed["Display_Excuse"] = missed["Excuse"].replace("", "No excuse logged")
    excuse_only = missed[missed["Excuse"].str.strip() != ""].copy()

    # --- Summary & Preview ---
    st.subheader("Recent Missed Habits & Excuses")
    if missed.empty:
        st.info("No missed habits (`Not Done`) are recorded yet.")
    else:
        habit_counts = missed["Habit"].value_counts()
        top_habit, top_habit_count = habit_counts.index[0], int(habit_counts.iloc[0])
        if not excuse_only.empty:
            exc_counts = excuse_only["Excuse"].value_counts()
            top_reason, top_reason_count = exc_counts.index[0], int(exc_counts.iloc[0])
        else:
            top_reason, top_reason_count = "None logged", 0

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Missed Check-ins", len(missed))
        k2.metric("Most Missed Habit", top_habit, f"{top_habit_count} misses", delta_color="off")
        k3.metric("Top Excuse Reason", top_reason, f"{top_reason_count} times" if top_reason_count else "0 logged", delta_color="off")

        preview = missed[["Date", "Habit", "Category", "Display_Excuse"]].rename(columns={"Display_Excuse": "Excuse"}).head(5)
        st.write("**Latest 5 Missed Records (`.head()` preview):**")
        st.dataframe(preview, hide_index=True, width="stretch")

        if st.checkbox("View full Excuse History", value=False):
            hist_filter = st.radio("History rows", ["All missed records", "Only records with excuses"], horizontal=True)
            source = excuse_only if hist_filter == "Only records with excuses" else missed
            if source.empty:
                st.info("No rows match that filter.")
            else:
                st.dataframe(source[["Date", "Habit", "Category", "Display_Excuse"]].rename(columns={"Display_Excuse": "Excuse"}), hide_index=True, width="stretch")

    # --- Inspect a Habit & Update Excuses ---
    st.divider()
    st.subheader("Inspect a Habit & Log / Update an Excuse")
    if habit_list.empty:
        st.info("No habits yet. Add one on **Add Habit** first.")
    else:
        chosen = st.selectbox("Select a habit to inspect missed dates or add/update an excuse", options=habit_list["Habit"].tolist(), index=None, placeholder="Choose a habit...")
        if chosen is None:
            st.info("Choose a habit above to see its missed dates and log or update an excuse.")
        else:
            habit_misses = missed[missed["Habit"] == chosen]
            st.write(f"**{chosen}** has **{len(habit_misses)}** missed check-in(s).")

            if not habit_misses.empty:
                miss_tbl = habit_misses[["Date", "Display_Excuse"]].rename(columns={"Display_Excuse": "Excuse"})
                st.dataframe(miss_tbl.head(5), hide_index=True, width="stretch")
                if len(miss_tbl) > 5 and st.checkbox(f"Show all {len(miss_tbl)} missed dates for '{chosen}'"):
                    st.dataframe(miss_tbl, hide_index=True, width="stretch")

            with st.container(border=True):
                st.write(f"Log or update a missed date for **{chosen}**")
                missed_day = st.date_input("Date missed", value=dt.date.today(), max_value=dt.date.today(), key=f"exc_date_{chosen}")
                reason_choice = st.selectbox("Reason", PREDEFINED_EXCUSES + ["Other (custom)"], key=f"exc_reason_{chosen}")
                custom_exc = st.text_input("Custom reason", placeholder="e.g. Felt sick, busy at work", key=f"exc_custom_{chosen}") if reason_choice == "Other (custom)" else ""

                if st.button("Save Excuse to CSV", type="primary", key=f"exc_save_{chosen}"):
                    final_exc = custom_exc.strip() if reason_choice == "Other (custom)" else reason_choice
                    start_text = habit_list[habit_list["Habit"] == chosen]["Start_Date"].iloc[0]
                    if not final_exc:
                        st.error("Please enter a reason.")
                    elif str(missed_day) < start_text:
                        st.error(f"'{chosen}' starts on {start_text}; pick a later date.")
                    elif save_data(add_log(habits_data, chosen, missed_day, "Not Done", excuse=final_exc)):
                        st.session_state["excuse_feedback"] = f"Saved excuse '{final_exc}' for '{chosen}' on {missed_day}."
                        st.rerun()

    # --- Storytelling Charts ---
    if not missed.empty:
        st.divider()
        st.subheader("📈 Missed Habits Storytelling & Patterns")
        c1, c2 = st.columns(2)

        by_habit = missed.groupby(["Habit", "Category"]).size().reset_index(name="Misses").sort_values("Misses", ascending=False)
        c1.plotly_chart(
            px.bar(by_habit, x="Habit", y="Misses", color="Category", title="Which Habits Are Missed Most Often?", template="plotly_dark"),
            width="stretch",
        )

        with c2:
            if not excuse_only.empty:
                reason_counts = excuse_only["Excuse"].value_counts().reset_index()
                reason_counts.columns = ["Excuse", "Count"]
                st.plotly_chart(
                    px.bar(reason_counts, x="Excuse", y="Count", title="Top Excuse Reasons", template="plotly_dark", color_discrete_sequence=[STATUS_COLORS["Not Done"]]),
                    width="stretch",
                )
            else:
                st.info("No written excuses logged yet to rank top reasons.")

        c3, c4 = st.columns(2)
        dated_missed = missed.copy()
        dated_missed["parsed_date"] = pd.to_datetime(dated_missed["Date"], errors="coerce")
        dated_missed = dated_missed.dropna(subset=["parsed_date"])

        with c3:
            try:
                dated_missed["Week"] = dated_missed["parsed_date"].dt.to_period("W").dt.start_time
                weekly = dated_missed.groupby("Week").size().reset_index(name="Misses").sort_values("Week")
                st.plotly_chart(
                    px.line(weekly, x="Week", y="Misses", markers=True, title="Missed Habits Over Time (Weekly Trend)", template="plotly_dark", color_discrete_sequence=[STATUS_COLORS["Not Done"]]),
                    width="stretch",
                )
            except Exception as error:
                st.write("Could not calculate weekly trend:", error)

        with c4:
            try:
                day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                day_counts = dated_missed["parsed_date"].dt.day_name().value_counts().reindex(day_order, fill_value=0).reset_index()
                day_counts.columns = ["Day", "Misses"]
                st.plotly_chart(
                    px.bar(day_counts, x="Day", y="Misses", title="Missed Habits by Day of Week", template="plotly_dark", color_discrete_sequence=["#f0ad4e"]),
                    width="stretch",
                )
            except Exception as error:
                st.write("Could not calculate day-of-week pattern:", error)
