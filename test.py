import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
import time
from github import Github

# ---------------- Streamlit config ----------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

# ---------------- Config / Paths ----------------
API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.xlsx")
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# ---------------- GitHub Config ----------------
GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_USERNAME = st.secrets["github"]["username"]
REPO_NAME = "AIRSTAY"

# ---------------- Parameters ----------------
START_MONTH = 1
END_MONTH = 10
today = date.today()

# ---------------- Apartments & Settings ----------------
APARTMENTS = {
    "ZED": [1439913,1439915,1439917,1439919,1439921,1439923,1439925,1439927,1439929,
            1439931,1439933,1439935,1439937,1439939,1439971,1439973,1439975,1439977,
            1439979,1439981,1439983,1439985],
    "KOMOS": [2160281,2160286,2160291],
    "CHELI": [2146456,2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH": [563628,563631,563637,563640,563643],
    "THRESH_A3": [1200587],
    "THRESH_A4": [563634],
    "ZILEAN": [1756004,1756007,1756010,1756013,1756016,1756019,1756022,1756025,1756031],
    "NAUTILUS": [563712,563724,563718,563721,563715,563727],
    "ANIVIA": [563703,563706],
    "ELISE": [563625,1405415],
    "ORIANNA": [1607131],
    "KALISTA": [750921],
    "JAAX": [2712218],
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,
               2715218,2715223,2715228,2715233,2715238,2715273]
}

APARTMENT_SETTINGS = {
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.216},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "THRESH_A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
    "THRESH_A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "KALISTA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.216},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.216},
    "AKALI": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
    "ZILEAN": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_fee_other": 0.10, "booking_fee": 0.166},
    "NAUTILUS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.186, "booking_fee_other": 0, "booking_fee": 0.216},
    "ANIVIA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "ELISE": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "ORIANNA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.216},
    "JAAX": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.0, "booking_fee_other": 0, "booking_fee": 0.166},
    "FINIKAS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
}

# ---------------- Helper functions ----------------
def fetch_reservations(from_date, to_date):
    params = {
        "from": from_date,
        "to": to_date,
        "includePriceElements": True,
        "showCancellation": False,
        "excludeBlocked": True,
        "page": 1,
        "pageSize": 100
    }
    all_bookings = []
    while True:
        try:
            r = requests.get(reservations_url, headers=headers, params=params, timeout=10)
            r.raise_for_status()
        except requests.RequestException:
            return pd.DataFrame()
        data = r.json()
        all_bookings.extend(data.get("bookings", []))
        if params["page"] >= data.get("page_count", 1):
            break
        params["page"] += 1
    if not all_bookings:
        return pd.DataFrame()
    df = pd.json_normalize(all_bookings)
    df = df[df["type"] != "cancellation"]
    df = df.rename(columns={
        "id": "booking_id",
        "apartment.id": "apartment_id",
        "apartment.name": "apartment_name",
        "channel.name": "platform",
        "guest-name": "guest_name",
        "adults": "adults",
        "children": "children",
        "price": "price"
    })
    df = df[df.get("is-blocked-booking", False) == False]
    return df

def fetch_reservations_with_retry(from_date, to_date, retries=3, delay=5):
    for attempt in range(retries):
        df = fetch_reservations(from_date, to_date)
        if not df.empty:
            return df
        time.sleep(delay)
    return pd.DataFrame()

def get_group_by_apartment(apt_id):
    for g, apt_list in APARTMENTS.items():
        if apt_id in apt_list:
            return g
    return None

def calculate_price_without_tax(row):
    price = float(row.get("price", 0) or 0)
    arrival = pd.to_datetime(row.get("arrival"))
    departure = pd.to_datetime(row.get("departure"))
    nights = (departure - arrival).days
    month = arrival.month
    apartment_id = row.get("apartment_id")
    group = get_group_by_apartment(apartment_id)
    if not group or nights == 0:
        return 0.0
    winter_months = [1,2,3,11,12]
    winter_base = APARTMENT_SETTINGS[group]["winter_base"]
    summer_base = APARTMENT_SETTINGS[group]["summer_base"]
    base = winter_base if month in winter_months else summer_base
    net_price = price - (base * nights)
    return (net_price / 1.13) - (net_price * 0.005)

def get_booking_fee(row):
    platform = str(row.get("platform", "")).lower()
    total = float(row.get("price", 0) or 0)
    apartment_id = row.get("apartment_id")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0
    settings = APARTMENT_SETTINGS[group]
    if "booking.com" in platform:
        return total * settings.get("booking_fee", 0.166)
    elif "airbnb" in platform:
        return total * 0.15
    elif "expedia" in platform:
        return total * 0.18
    else:
        return total * settings.get("booking_fee_other", 0.0)

def calculate_airstay_commission(row):
    price_without_tax = row.get("Price Without Tax", 0) or 0
    apartment_id = row.get("apartment_id")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0
    rate = APARTMENT_SETTINGS[group].get("airstay_commission", 0.0)
    return price_without_tax * rate

def calculate_columns(df):
    if df.empty:
        return df
    df["adults"] = pd.to_numeric(df.get("adults",0), errors="coerce").fillna(0)
    df["children"] = pd.to_numeric(df.get("children",0), errors="coerce").fillna(0)
    df["Price Without Tax"] = df.apply(calculate_price_without_tax, axis=1)
    df["Booking Fee"] = df.apply(get_booking_fee, axis=1)
    df["Airstay Commission"] = df.apply(calculate_airstay_commission, axis=1)
    df["Owner Profit"] = df["Price Without Tax"] - df["Booking Fee"] - df["Airstay Commission"]
    df["Guests"] = df["adults"] + df["children"]
    return df

def parse_amount(v):
    try:
        return float(v)
    except:
        return 0.0

def push_file_to_github(file_path, repo_name, username, token, commit_message):
    g = Github(token)
    repo = g.get_user().get_repo(repo_name)
    with open(file_path, "rb") as f:
        content = f.read()
    file_name = os.path.basename(file_path)
    try:
        contents = repo.get_contents(file_name)
        repo.update_file(contents.path, commit_message, content, contents.sha)
    except:
        repo.create_file(file_name, commit_message, content)

# ---------------- Load or Fetch Reservations ----------------
fetch_and_store = False  # True για fetch από API και αποθήκευση, False για φόρτωση από Excel

columns_to_keep = [
    "booking_id", "apartment_id", "apartment_name", "platform",
    "guest_name", "arrival", "departure",
    "Guests", "price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit"
]

if fetch_and_store:
    all_dfs = []
    for month in range(START_MONTH, END_MONTH + 1):
        from_date = date(today.year, month, 1).strftime("%Y-%m-%d")
        next_month = date(today.year, month, 28) + timedelta(days=4)
        last_day = (next_month - timedelta(days=next_month.day)).day
        to_date = date(today.year, month, last_day).strftime("%Y-%m-%d")
        df_month = fetch_reservations_with_retry(from_date, to_date)
        if df_month.empty:
            continue
        df_month["platform"] = df_month["platform"].astype(str)
        # Διόρθωση expedia τιμών
        df_month["price"] = df_month.apply(
            lambda row: float(row["price"])/0.82 if "expedia" in str(row["platform"]).lower() else float(row["price"]),
            axis=1
        )
        df_month = calculate_columns(df_month)
        all_dfs.append(df_month)

    df_new = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    for c in columns_to_keep:
        if c not in df_new.columns:
            df_new[c] = pd.NA
    df_to_store = df_new[columns_to_keep].copy()

    # Συνδυασμός με υπάρχον Excel
    if os.path.exists(RESERVATIONS_FILE):
        existing_df = pd.read_excel(RESERVATIONS_FILE)
        existing_cols = [c for c in existing_df.columns if c in columns_to_keep]
        if existing_cols:
            existing_df = existing_df[existing_cols]
        combined_df = pd.concat([existing_df, df_to_store], ignore_index=True, sort=False)
        combined_df = combined_df.drop_duplicates(subset=["booking_id"], keep="first")
        df_to_store_final = combined_df.reindex(columns=columns_to_keep)
    else:
        df_to_store_final = df_to_store

    for col in ["price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit", "Guests"]:
        if col in df_to_store_final.columns:
            df_to_store_final[col] = pd.to_numeric(df_to_store_final[col], errors="coerce").round(2)

    # Αποθήκευση Excel και push στο GitHub
    df_to_store_final.to_excel(RESERVATIONS_FILE, index=False)
    push_file_to_github(
        RESERVATIONS_FILE,
        REPO_NAME,
        GITHUB_USERNAME,
        GITHUB_TOKEN,
        commit_message=f"Update reservations.xlsx from Streamlit ({today})"
    )

    df_display_source = df_to_store_final.copy()
else:
    # Φόρτωση υπάρχοντος Excel
    if os.path.exists(RESERVATIONS_FILE):
        df_display_source = pd.read_excel(RESERVATIONS_FILE)
    else:
        df_display_source = pd.DataFrame(columns=columns_to_keep)

    # Fetch τρέχοντος μήνα μέχρι χθες
    today_date = date.today()
    first_day = today_date.replace(day=1)
    yesterday = today_date - timedelta(days=1)
    df_current_month = fetch_reservations_with_retry(first_day.strftime("%Y-%m-%d"),
                                                     yesterday.strftime("%Y-%m-%d"))
    if not df_current_month.empty:
        df_current_month = calculate_columns(df_current_month)
        # Προσθήκη στο υπάρχον
        df_display_source = pd.concat([df_display_source, df_current_month], ignore_index=True)
        df_display_source = df_display_source.drop_duplicates(subset=["booking_id"], keep="first")


# ---------------- Load Expenses ----------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])

# ---------------- Sidebar: Επιλογή Group ----------------
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
df_filtered = df_display_source[df_display_source["apartment_id"].isin(APARTMENTS[selected_group])].copy()

# ---------------- Metrics ανά μήνα ----------------
monthly_metrics = defaultdict(lambda: {
    "Total Price":0.0,
    "Total Expenses":0.0,
    "Owner Profit":0.0,
    "Airstay Commission":0.0
})

for idx, row in df_filtered.iterrows():
    try:
        checkin = pd.to_datetime(row["arrival"])
        checkout = pd.to_datetime(row["departure"])
    except:
        continue
    total_days = (checkout - checkin).days
    if total_days <= 0:
        continue
    daily_price = float(row.get("price",0))/total_days
    daily_profit = float(row.get("Owner Profit",0))/total_days
    daily_airstay = float(row.get("Airstay Commission",0))/total_days
    current_day = checkin
    while current_day < checkout:
        year, month = current_day.year, current_day.month
        next_month_day = (current_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (min(checkout, next_month_day) - current_day).days
        monthly_metrics[(year,month)]["Total Price"] += daily_price * days_in_month
        monthly_metrics[(year,month)]["Owner Profit"] += daily_profit * days_in_month
        monthly_metrics[(year,month)]["Airstay Commission"] += daily_airstay * days_in_month
        current_day = next_month_day

for idx, row in expenses_df.iterrows():
    if str(row.get("Accommodation","")).upper() != selected_group.upper():
        continue
    try:
        key = (int(row["Year"]), int(row["Month"]))
    except:
        continue
    monthly_metrics[key]["Total Expenses"] += parse_amount(row["Amount"])

months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
             7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

monthly_table = pd.DataFrame([
    {
        "Έτος": year,
        "Μήνας": months_el[month],
        "Συνολική Τιμή Κρατήσεων (€)": v["Total Price"],
        "Συνολικά Έξοδα (€)": v["Total Expenses"],
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": v["Owner Profit"] - v["Total Expenses"],
        "Συνολικά Έσοδα Airstay (€)": v["Airstay Commission"]
    }
    for (year,month),v in sorted(monthly_metrics.items())
])

monthly_table = monthly_table[
    ((monthly_table["Καθαρό Κέρδος Ιδιοκτήτη (€)"] + monthly_table["Συνολικά Έσοδα Airstay (€)"]) != 0)
    & (monthly_table["Έτος"]==today.year)
    & (monthly_table["Μήνας"].map(lambda m: list(months_el.values()).index(m)+1) <= today.month)
]

for col in ["Συνολική Τιμή Κρατήσεων (€)",
            "Συνολικά Έξοδα (€)",
            "Καθαρό Κέρδος Ιδιοκτήτη (€)",
            "Συνολικά Έσοδα Airstay (€)"]:
    if not monthly_table.empty:
        monthly_table[col] = monthly_table[col].map(lambda x: f"{x:.2f}")

if not monthly_table.empty:
    total_row = {
        "Έτος": "Σύνολο",
        "Μήνας": "",
        "Συνολική Τιμή Κρατήσεων (€)": f"{monthly_table['Συνολική Τιμή Κρατήσεων (€)'].astype(float).sum():.2f}",
        "Συνολικά Έξοδα (€)": f"{monthly_table['Συνολικά Έξοδα (€)'].astype(float).sum():.2f}",
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{monthly_table['Καθαρό Κέρδος Ιδιοκτήτη (€)'].astype(float).sum():.2f}",
        "Συνολικά Έσοδα Airstay (€)": f"{monthly_table['Συνολικά Έσοδα Airstay (€)'].astype(float).sum():.2f}"
    }
    monthly_table = pd.concat([monthly_table, pd.DataFrame([total_row])], ignore_index=True)

# ---------------- Display Metrics & Reservations ----------------
st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
if monthly_table.empty:
    st.info("Δεν υπάρχουν metrics για εμφάνιση.")
else:
    st.dataframe(monthly_table, use_container_width=True)

st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(df_filtered[columns_to_keep], use_container_width=True)

# ---------------- Section Έξοδα ----------------
st.subheader(f"💸 Έξοδα ({selected_group})")

with st.form(f"add_expense_form_{selected_group}"):
    month = st.selectbox("Μήνας", list(range(1,13)))
    amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    category = st.text_input("Κατηγορία Έξοδου")
    description = st.text_input("Περιγραφή")
    submit = st.form_submit_button("Προσθήκη Έξοδου")

    if submit:
        new_expense = {
            "ID": expenses_df["ID"].max() + 1 if not expenses_df.empty else 1,
            "Month": month,
            "Year": today.year,
            "Accommodation": selected_group,
            "Category": category,
            "Amount": amount,
            "Description": description
        }
        expenses_df = pd.concat([expenses_df, pd.DataFrame([new_expense])], ignore_index=True)
        expenses_df.to_excel(EXPENSES_FILE, index=False)
        st.success(f"Έξοδο προστέθηκε για {selected_group}!")

        push_file_to_github(
            EXPENSES_FILE,
            REPO_NAME,
            GITHUB_USERNAME,
            GITHUB_TOKEN,
            commit_message=f"Update expenses.xlsx from Streamlit ({today})"
        )

df_group_expenses = expenses_df[expenses_df["Accommodation"] == selected_group].copy()
if not df_group_expenses.empty:
    df_group_expenses["Amount"] = df_group_expenses["Amount"].apply(lambda x: f"{float(x):.2f}")
st.dataframe(df_group_expenses, use_container_width=True)

# ---------------- Γράφημα Metrics ----------------
import plotly.express as px
import pandas as pd

# Φιλτράρουμε τη γραμμή "Σύνολο"
df_plot = monthly_table[monthly_table["Έτος"] != "Σύνολο"].copy()
if not df_plot.empty:
    # Μετατροπή σε float
    for col in ["Συνολική Τιμή Κρατήσεων (€)", 
                "Καθαρό Κέρδος Ιδιοκτήτη (€)", 
                "Συνολικά Έσοδα Airstay (€)",
                "Συνολικά Έξοδα (€)"]:
        df_plot[col] = df_plot[col].astype(float)
    
    # Ορισμός σωστής χρονολογικής σειράς μηνών
    months_order = ["Ιανουάριος","Φεβρουάριος","Μάρτιος","Απρίλιος","Μάιος","Ιούνιος",
                    "Ιούλιος","Αύγουστος","Σεπτέμβριος","Οκτώβριος","Νοέμβριος","Δεκέμβριος"]
    df_plot["Μήνας"] = pd.Categorical(df_plot["Μήνας"], categories=months_order, ordered=True)
    df_plot = df_plot.sort_values("Μήνας")
    
    # Δημιουργία γραφήματος
    fig = px.line(
        df_plot,
        x="Μήνας",
        y=["Συνολική Τιμή Κρατήσεων (€)", 
           "Καθαρό Κέρδος Ιδιοκτήτη (€)", 
           "Συνολικά Έσοδα Airstay (€)",
           "Συνολικά Έξοδα (€)"],
        markers=True,
        title=f"Metrics & Έξοδα ανά μήνα ({selected_group})",
        labels={"value": "€", "variable": "Metric"}
    )

    fig.update_layout(
        legend_title_text="Metrics",
        xaxis_title="Μήνας",
        yaxis_title="€",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)
