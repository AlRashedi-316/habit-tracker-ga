# Habit Tracker App (app.py) — Streamlit + Pandas student project
import datetime as dt
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Habit Tracker", page_icon="📈", layout="wide")

DATA_FILE, FREQUENCIES = "data/test_habits.csv", ["Daily", "Weekly"]
COLUMNS = ["Habit", "Category", "Frequency", "Goal", "Start_Date", "Date", "Status", "Excuse"]
HABIT_COLS = COLUMNS[:5]
CATEGORIES = ["Health", "Fitness", "Learning", "Mindfulness", "Productivity", "Other"]
EXCUSES = ["No excuse", "Forgot", "Too tired", "Sick", "Ran out of time", "Bad weather", "Other (custom)"]
ICONS = {"Health": "💧", "Fitness": "🏃", "Learning": "📖", "Mindfulness": "🧘", "Productivity": "⚡", "Other": "📌"}
STATUS_COLORS = {"Done": "#2e9e5b", "Not Done": "#d9534f"}
PAGES = ["Log Habit", "Add Habit", "Manage Habits", "My Progress", "Excuse Manager"]

# --- Data & Helper Functions ---
def load_data():
    try:
        return pd.read_csv(DATA_FILE, dtype=str).fillna("").reindex(columns=COLUMNS, fill_value="")
    except Exception as err:
        st.warning(f"Could not load '{DATA_FILE}' ({err}). Starting empty.")
        return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    clean = df[COLUMNS].reset_index(drop=True).copy()
    st.session_state["habits_df"] = clean
    st.session_state["editor_ver"] = st.session_state.get("editor_ver", 0) + 1
    try:
        clean.to_csv(DATA_FILE, index=False)
    except Exception as err:
        st.warning(f"Saved in session, but CSV write failed: {err}")

def get_habits(df):
    return df.drop_duplicates(subset=["Habit"])[HABIT_COLS].reset_index(drop=True)

def get_streaks(df, habit_name, ref_date):
    done = df[(df["Habit"] == habit_name) & (df["Status"] == "Done") & (df["Date"] != "")]
    dates = pd.to_datetime(done["Date"], errors="coerce").dropna().dt.date.drop_duplicates().sort_values().tolist()
    if not dates:
        return 0, 0
    best = run = 0
    for i, day in enumerate(dates):
        run = run + 1 if i > 0 and (day - dates[i - 1]).days == 1 else 1
        best = max(best, run)
    past = [d for d in dates if d <= ref_date]
    cur = 1 if past and (ref_date - past[-1]).days <= 1 else 0
    for i in range(len(past) - 2, -1, -1):
        if not cur or (past[i + 1] - past[i]).days != 1:
            break
        cur += 1
    return cur, best

def get_streak_table(df, names, ref_date):
    return pd.DataFrame([{"Habit": h, "Current": c, "Best": b} for h in names for c, b in [get_streaks(df, h, ref_date)]])

def add_log(df, habit_name, log_date, status, excuse=""):
    matches = df[df["Habit"] == habit_name]
    if matches.empty:
        return df
    info, date_text = matches.iloc[0], str(log_date)
    new_row = {**{c: str(info[c]) for c in HABIT_COLS}, "Date": date_text, "Status": status, "Excuse": excuse}
    keep = ~((df["Habit"] == habit_name) & ((df["Date"] == date_text) | (df["Date"] == "")))
    return pd.concat([df[keep], pd.DataFrame([new_row])], ignore_index=True)

def apply_table_edits(df, edited_df, orig_names, deleted_pos=None):
    errors, seen, cleaned = [], set(), []
    active_orig = {idx: name for pos, (idx, name) in enumerate(orig_names.items()) if pos not in set(deleted_pos or [])}
    for pos, (row_idx, row) in enumerate(edited_df.iterrows(), start=1):
        r = row.fillna("")
        habit, cat, freq = str(r.get("Habit", "")).strip(), str(r.get("Category", "")).strip(), str(r.get("Frequency", "")).strip()
        goal, start = pd.to_numeric(row.get("Goal"), errors="coerce"), pd.to_datetime(row.get("Start_Date"), errors="coerce")
        if not habit or habit.lower() in seen:
            errors.append(f"Row {pos}: Habit name must be non-empty and unique.")
        seen.add(habit.lower())
        if cat not in CATEGORIES or freq not in FREQUENCIES or pd.isna(goal) or goal % 1 != 0 or not (1 <= goal <= 1000) or pd.isna(start):
            errors.append(f"Row {pos}: Check Category, Frequency, Goal (1-1000), and Start Date.")
        elif not errors:
            cleaned.append((row_idx, [habit, cat, freq, str(int(goal)), start.strftime("%Y-%m-%d")]))
    if errors:
        return None, errors
    frames = []
    for row_idx, vals in cleaned:
        logs = df[df["Habit"] == active_orig[row_idx]].copy() if row_idx in active_orig else pd.DataFrame()
        if not logs.empty:
            for col, val in zip(HABIT_COLS, vals):
                logs[col] = val
            frames.append(logs)
        else:
            frames.append(pd.DataFrame([{**dict(zip(HABIT_COLS, vals)), "Date": "", "Status": "", "Excuse": ""}]))
    return (pd.concat(frames, ignore_index=True)[COLUMNS] if frames else pd.DataFrame(columns=COLUMNS)), []

def show_heatmap(records):
    hm = records[records["Status"].isin(["Done", "Not Done"])].assign(d=lambda x: pd.to_datetime(x["Date"], errors="coerce")).dropna(subset=["d"])
    if hm.empty:
        return st.info("No dated check-in records available for the heatmap.")
    recent = hm[hm["d"] >= hm["d"].max() - pd.Timedelta(days=29)].assign(code=lambda x: np.where(x["Status"] == "Done", 1.0, 0.0))
    grid = recent.pivot_table(index="Habit", columns="d", values="code", aggfunc="max").sort_index(axis=1)
    grid.columns = [d.strftime("%m-%d") for d in grid.columns]
    fig = px.imshow(grid, color_continuous_scale=[[0.0, STATUS_COLORS["Not Done"]], [1.0, STATUS_COLORS["Done"]]], zmin=0, zmax=1, aspect="auto", title="30-Day Attendance Heatmap", template="plotly_dark")
    fig.update_coloraxes(showscale=False).update_traces(xgap=2, ygap=2).update_layout(plot_bgcolor="#161b22", xaxis_title="Date (MM-DD)", yaxis_title="")
    st.plotly_chart(fig, width="stretch")
    st.caption("🟩 Attended (Done)  •  🟥 Missed (Not Done)  •  ⬛ Not Logged")

# --- Sidebar & Session State ---
st.sidebar.title("📈 Habit Tracker")
page = st.sidebar.radio("Navigation", PAGES, index=0)
if "habits_df" not in st.session_state:
    st.session_state["habits_df"] = load_data()
df, habit_list = st.session_state["habits_df"], get_habits(st.session_state["habits_df"])

if "flash" in st.session_state:
    level, msg = st.session_state.pop("flash")
    if level == "info":
        st.info(msg)
    else:
        st.success(msg)
    if level in ("reward", "done"):
        st.balloons()
    else:
        st.toast(msg)

# === PAGE 1: LOG HABIT ===
if page == "Log Habit":
    st.title("✅ Log Habit")
    if habit_list.empty:
        st.info("No habits yet. Add your first habit on **Add Habit**.")
    else:
        picked = st.date_input("Check-in Date", value=dt.date.today(), max_value=dt.date.today())
        date_text = str(picked)
        active = habit_list[habit_list["Start_Date"] <= date_text]
        if active.empty:
            st.info("No habits are active on this date yet.")
        else:
            day_logs = df[df["Date"] == date_text]
            done_today = day_logs[(day_logs["Habit"].isin(active["Habit"])) & (day_logs["Status"] == "Done")]["Habit"].nunique()
            st.write(f"**Today's Progress:** {done_today} of {len(active)} completed")
            st.progress(done_today / len(active))
            for _, hrow in active.iterrows():
                name, existing = hrow["Habit"], day_logs[day_logs["Habit"] == hrow["Habit"]]
                cur, _ = get_streaks(df, name, picked)
                status, exc = (existing.iloc[0]["Status"], existing.iloc[0]["Excuse"]) if not existing.empty else ("", "")
                if status == "Done":
                    badge = ":green[Completed]" + (f" • 🔥 {cur}-day streak" if cur > 0 else "")
                elif status == "Not Done":
                    badge = ":red[Missed]" + (f" — *{exc}*" if exc else "")
                else:
                    badge = ":gray[Pending]"
                c_info, c_done, c_miss = st.columns([3.5, 1, 1])
                c_info.markdown(f"{ICONS.get(hrow['Category'], '📌')} **{name}** — {badge}")
                c_info.caption(f"{hrow['Category']} • {hrow['Frequency']} • Goal: {hrow['Goal']}")
                if c_done.button("✅ Done", key=f"done_{name}_{date_text}", width="stretch"):
                    st.session_state.pop("pending_excuse", None)
                    updated = add_log(df, name, picked, "Done")
                    save_data(updated)
                    streak, _ = get_streaks(updated, name, picked)
                    if streak > 0 and streak % 7 == 0:
                        st.session_state["flash"] = ("reward", f"🎉 Milestone reached! {streak} days in a row on '{name}'!")
                    else:
                        unit = "day" if streak == 1 else "days"
                        st.session_state["flash"] = ("done", f"Great job! You completed '{name}' — {streak} {unit} in a row!")
                    st.rerun()
                if c_miss.button("❌ Not Done", key=f"miss_{name}_{date_text}", width="stretch"):
                    st.session_state["pending_excuse"] = {"habit": name, "date": date_text}
                    st.rerun()
                if st.session_state.get("pending_excuse") == {"habit": name, "date": date_text}:
                    with st.container(border=True):
                        choice = st.selectbox(f"Why was {name} missed?", EXCUSES, key=f"exc_{name}_{date_text}")
                        custom = st.text_input("Custom reason", key=f"cust_{name}_{date_text}") if choice == "Other (custom)" else ""
                        b1, b2 = st.columns(2)
                        if b1.button("Save Miss", type="primary", key=f"save_exc_{name}_{date_text}", width="stretch"):
                            reason = "" if choice == "No excuse" else (custom.strip() if choice == "Other (custom)" else choice)
                            if choice == "Other (custom)" and not reason:
                                st.warning("Type a custom reason or choose 'No excuse'.")
                            else:
                                save_data(add_log(df, name, picked, "Not Done", excuse=reason))
                                st.session_state.pop("pending_excuse", None)
                                st.session_state["flash"] = ("info", f"Logged '{name}' as Not Done ({reason or 'No excuse'}).")
                                st.rerun()
                        if b2.button("Cancel", key=f"cancel_exc_{name}_{date_text}", width="stretch"):
                            st.session_state.pop("pending_excuse", None)
                            st.rerun()
        st.divider()
        st.subheader("🔥 Streaks & Milestones")
        streaks = get_streak_table(df, habit_list["Habit"], picked)
        if active_7 := streaks[streaks["Current"] >= 7]["Habit"].tolist():
            st.success(f"🔥 7+ day streak milestone active: {', '.join(active_7)}")
        for start in range(0, len(streaks), 4):
            for col, (_, row) in zip(st.columns(4), streaks.iloc[start : start + 4].iterrows()):
                col.metric(row["Habit"], f"{row['Current']} days")
                col.caption(f"Best: {row['Best']} days")

# === PAGE 2: ADD HABIT ===
elif page == "Add Habit":
    st.title("➕ Add Habit")
    with st.form("add_form", clear_on_submit=True):
        name_in = st.text_input("Habit Name", placeholder="e.g. Morning Walk")
        c1, c2 = st.columns(2)
        cat_in, freq_in = c1.selectbox("Category", CATEGORIES), c2.selectbox("Frequency", FREQUENCIES)
        c3, c4 = st.columns(2)
        goal_in, start_in = c3.number_input("Goal (times per period)", 1, 1000, 1, 1), c4.date_input("Start Date", value=dt.date.today())
        if st.form_submit_button("Add Habit", type="primary"):
            clean = name_in.strip()
            if not clean or clean.lower() in {h.lower() for h in df["Habit"].unique()}:
                st.error("Habit name must be non-empty and unique.")
            else:
                row = {"Habit": clean, "Category": cat_in, "Frequency": freq_in, "Goal": str(int(goal_in)), "Start_Date": str(start_in), "Date": "", "Status": "", "Excuse": ""}
                save_data(pd.concat([df, pd.DataFrame([row])], ignore_index=True))
                st.success(f"Added '{clean}'! Go to **Log Habit** to check in.")
                habit_list = get_habits(st.session_state["habits_df"])
    if not habit_list.empty:
        st.subheader("Current Habits")
        st.dataframe(habit_list.head(10), hide_index=True, width="stretch")

# === PAGE 3: MANAGE HABITS ===
elif page == "Manage Habits":
    st.title("⚙️ Manage Habits")
    editable = habit_list.copy() if not habit_list.empty else pd.DataFrame({c: pd.Series(dtype="int64" if c == "Goal" else "object") for c in HABIT_COLS})
    if not editable.empty:
        editable["Goal"] = pd.to_numeric(editable["Goal"], errors="coerce").fillna(1).clip(1, 1000).astype(int)
        editable["Start_Date"] = pd.to_datetime(editable["Start_Date"], errors="coerce").dt.date
    orig_names, ver, cc = dict(zip(editable.index, editable["Habit"])), st.session_state.get("editor_ver", 0), st.column_config
    col_cfg = {"Habit": cc.TextColumn("Habit", required=True), "Category": cc.SelectboxColumn("Category", options=CATEGORIES, required=True), "Frequency": cc.SelectboxColumn("Frequency", options=FREQUENCIES, required=True), "Goal": cc.NumberColumn("Goal", min_value=1, max_value=1000, step=1, required=True), "Start_Date": cc.DateColumn("Start Date", format="YYYY-MM-DD", required=True)}
    edited = st.data_editor(editable, num_rows="dynamic", hide_index=True, width="stretch", key=f"editor_{ver}", column_config=col_cfg)
    if st.button("💾 Save Table Changes", type="primary"):
        updated, errs = apply_table_edits(df, edited, orig_names, st.session_state.get(f"editor_{ver}", {}).get("deleted_rows", []))
        if errs:
            st.error("\n".join(errs))
        else:
            save_data(updated)
            st.session_state["flash"] = ("success", "Saved table changes!")
            st.rerun()
    st.divider()
    st.subheader("CSV Data Tools")
    if uploaded_file := st.file_uploader("Upload CSV (replaces active dataset after validation)", type="csv"):
        try:
            up = pd.read_csv(uploaded_file, dtype=str).fillna("")
            goals = pd.to_numeric(up["Goal"], errors="coerce") if "Goal" in up.columns else pd.Series(dtype=float)
            if list(up.columns) != COLUMNS:
                st.error(f"Columns must be: {', '.join(COLUMNS)}")
            elif (up["Habit"].str.strip() == "").any() or goals.isna().any() or (goals % 1 != 0).any() or (goals < 1).any() or (goals > 1000).any():
                st.error("Habit names cannot be empty and Goal must be whole numbers (1-1000).")
            else:
                st.success(f"Valid CSV: {len(up)} rows across {up['Habit'].nunique()} habits.")
                if st.button("Replace active dataset with uploaded CSV", type="primary"):
                    save_data(up)
                    st.session_state["flash"] = ("success", "Replaced active dataset with uploaded CSV.")
                    st.rerun()
        except Exception as err:
            st.error(f"Upload rejected: {err}")
    st.download_button("⬇️ Download current dataset", df.to_csv(index=False).encode("utf-8"), "habits.csv", "text/csv")

# === PAGE 4: MY PROGRESS ===
elif page == "My Progress":
    st.title("📊 My Progress")
    if habit_list.empty:
        st.info("No habits yet. Add one on **Add Habit**.")
    else:
        cb_cols = st.columns(3)
        selected_cats = [c for i, c in enumerate(CATEGORIES) if cb_cols[i % 3].checkbox(f"{ICONS[c]} {c}", value=True, key=f"cb_{c}")]
        status_filter = st.radio("Show records", ["All", "Done", "Not Done"], horizontal=True)
        cat_df = df[(df["Date"] != "") & (df["Category"].isin(selected_cats))]
        filtered = cat_df if status_filter == "All" else cat_df[cat_df["Status"] == status_filter]
        if not selected_cats or filtered.empty:
            st.info("No logged check-ins match these filters yet.")
        else:
            c1, c2 = st.columns(2)
            rate = (cat_df["Status"] == "Done").mean() * 100
            c1.metric("Overall Completion Rate", f"{rate:.1f}%")
            c1.progress(rate / 100.0)
            c2.plotly_chart(px.pie(cat_df["Status"].value_counts().reset_index(name="Count"), names="Status", values="Count", color="Status", color_discrete_map=STATUS_COLORS, title="Done vs Not Done", template="plotly_dark"), width="stretch")
            st.plotly_chart(px.bar(filtered.groupby(["Category", "Status"]).size().reset_index(name="Count"), x="Category", y="Count", color="Status", barmode="group", color_discrete_map=STATUS_COLORS, title="Check-ins by Category", template="plotly_dark"), width="stretch")
            streak_df = get_streak_table(df, habit_list[habit_list["Category"].isin(selected_cats)]["Habit"], dt.date.today())
            if not streak_df.empty:
                st.plotly_chart(px.bar(streak_df.melt(id_vars="Habit", var_name="Type", value_name="Days"), x="Habit", y="Days", color="Type", barmode="group", title="Current vs Best Streak", template="plotly_dark"), width="stretch")
            show_heatmap(filtered)

# === PAGE 5: EXCUSE MANAGER (PHASE 3 INNOVATION) ===
elif page == "Excuse Manager":
    st.title("📝 Excuse Manager")
    missed = df[(df["Status"] == "Not Done") & (df["Date"] != "")].sort_values("Date", ascending=False).copy()
    if missed.empty:
        st.info("No missed habits (`Not Done`) recorded yet.")
    else:
        missed["Excuse"] = missed["Excuse"].replace("", "No excuse logged")
        exc_only = missed[missed["Excuse"] != "No excuse logged"]
        top_habit, top_exc = missed["Habit"].value_counts(), exc_only["Excuse"].value_counts()
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Missed Check-ins", len(missed))
        k2.metric("Most Missed Habit", top_habit.index[0], f"{int(top_habit.iloc[0])} misses", delta_color="off")
        k3.metric("Top Excuse Reason", top_exc.index[0] if not top_exc.empty else "None", f"{int(top_exc.iloc[0])} times" if not top_exc.empty else "0 logged", delta_color="off")
        st.dataframe(missed[["Date", "Habit", "Category", "Excuse"]].head(None if st.checkbox("View full Excuse History") else 5), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(missed.groupby(["Habit", "Category"]).size().reset_index(name="Misses").sort_values("Misses", ascending=False), x="Habit", y="Misses", color="Category", title="Most Missed Habits", template="plotly_dark"), width="stretch")
        if not exc_only.empty:
            c2.plotly_chart(px.bar(top_exc.reset_index(name="Count"), x="Excuse", y="Count", title="Top Excuse Reasons", template="plotly_dark", color_discrete_sequence=[STATUS_COLORS["Not Done"]]), width="stretch")
        else:
            c2.info("No written excuses logged yet.")
