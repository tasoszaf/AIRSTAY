# reservations_dashboard_mode.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
from github import Github
import time

# ---------------- Streamlit config ----------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

# ---------------- Config / Paths ----------------
API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"  # καλύτερα στο st.secrets
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.xlsx")
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# ---------------- Parameters ----------------
START_MONTH = 1   # τροποποίησέ τα όπως θες
END_MONTH = 10
today = date.today()

# ---------------- Apartments & Settings (όπως προηγουμένως) ----------------
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
    winter_months = [1, 2, 3, 11, 12]
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
    # ensure numeric for adults/children
    if "adults" not in df.columns:
        df["adults"] = 0
    if "children" not in df.columns:
        df["children"] = 0
    df["adults"] = pd.to_numeric(df["adults"], errors="coerce").fillna(0)
    df["children"] = pd.to_numeric(df["children"], errors="coerce").fillna(0)

    df["Price Without Tax"] = df.apply(calculate_price_without_tax, axis=1)
    df["Booking Fee"] = df.apply(get_booking_fee, axis=1)
    df["Airstay Commission"] = df.apply(calculate_airstay_commission, axis=1)
    df["Owner Profit"] = df["Price Without Tax"] - df["Booking Fee"] - df["Airstay Commission"]
    df["Guests"] = df["adults"] + df["children"]
    return df

# ---------------- Load expenses (used only in metrics; not saved) ----------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])

def parse_amount(v):
    try:
        return float(v)
    except:
        return 0.0

# Set mode manually: True = fetch & save, False = display from Excel + current month
fetch_and_store = False  # True ή False

# ---------------- Main flow ----------------
# columns to keep (only these are saved in Excel)
columns_to_keep = [
    "booking_id", "apartment_id", "apartment_name", "platform",
    "guest_name", "arrival", "departure",
    "Guests", "price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit"
]

if fetch_and_store:
    # --- Fetch ALL months (START_MONTH -> END_MONTH), process and SAVE ---
    all_dfs = []
    for month in range(START_MONTH, END_MONTH + 1):
        from_date = date(today.year, month, 1).strftime("%Y-%m-%d")
        next_month = date(today.year, month, 28) + timedelta(days=4)
        last_day = (next_month - timedelta(days=next_month.day)).day
        to_date = date(today.year, month, last_day).strftime("%Y-%m-%d")

        
        df_month = fetch_reservations_with_retry(from_date, to_date)
        if df_month.empty:
            st.write(f" - Δεν βρέθηκαν κρατήσεις ή σφάλμα API για {month}/{today.year}.")
            continue

        # ensure platform string
        df_month["platform"] = df_month["platform"].astype(str)
        # Expedia correction (vectorized apply kept for safety)
        df_month["price"] = df_month.apply(
            lambda row: float(row["price"]) / 0.82 if "expedia" in str(row["platform"]).lower() else float(row["price"]),
            axis=1
        )
        df_month = calculate_columns(df_month)
        all_dfs.append(df_month)

    df_new = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

    # ensure columns exist
    for c in columns_to_keep:
        if c not in df_new.columns:
            df_new[c] = pd.NA

    df_to_store = df_new[columns_to_keep].copy()

    # Append + drop duplicates to RESERVATIONS_FILE
    if os.path.exists(RESERVATIONS_FILE):
        existing_df = pd.read_excel(RESERVATIONS_FILE)
        # keep only shown columns from existing file if present
        existing_cols = [c for c in existing_df.columns if c in columns_to_keep]
        if existing_cols:
            existing_df = existing_df[existing_cols]
        combined_df = pd.concat([existing_df, df_to_store], ignore_index=True, sort=False)
        combined_df = combined_df.drop_duplicates(subset=["booking_id"], keep="first")
        df_to_store_final = combined_df.reindex(columns=columns_to_keep)
    else:
        df_to_store_final = df_to_store

    # Round numeric columns to 2 decimals for saving
    for col in ["price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit", "Guests"]:
        if col in df_to_store_final.columns:
            df_to_store_final[col] = pd.to_numeric(df_to_store_final[col], errors="coerce").round(2)

    # Save
    df_to_store_final.to_excel(RESERVATIONS_FILE, index=False)
    st.success(f"✅ Οι κρατήσεις αποθηκεύτηκαν στο {RESERVATIONS_FILE} (μόνο οι εμφανιζόμενες στήλες).")

    # Upload στο GitHub (προαιρετικό, απαιτεί st.secrets["github"])
    try:
        GITHUB_TOKEN = st.secrets["github"]["token"]
        GITHUB_USER = st.secrets["github"]["username"]
        GITHUB_REPO = st.secrets["github"]["repo"]
        FILE_PATH = "reservations.xlsx"

        g = Github(GITHUB_TOKEN)
        repo = g.get_user(GITHUB_USER).get_repo(GITHUB_REPO)

        with open(RESERVATIONS_FILE, "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(FILE_PATH, ref="main")
            repo.update_file(FILE_PATH, "🔁 Update reservations.xlsx", content, contents.sha, branch="main")
        except Exception:
            repo.create_file(FILE_PATH, "🆕 Add reservations.xlsx", content, branch="main")

        st.success("✅ Το αρχείο **reservations.xlsx** ενημερώθηκε επιτυχώς στο GitHub.")
    except Exception as e:
        st.warning(f"⚠️ Σφάλμα κατά το ανέβασμα στο GitHub: {e}")

    # For display: use df_to_store_final
    df_display_source = df_to_store_final.copy()

else:
    # --- Mode FALSE: load from Excel and fetch current month until yesterday (display only) ---
    if os.path.exists(RESERVATIONS_FILE):
        df_excel = pd.read_excel(RESERVATIONS_FILE)
        # ensure we only keep columns_to_keep
        cols_present = [c for c in df_excel.columns if c in columns_to_keep]
        df_excel = df_excel[cols_present].copy()
        # fill missing columns with NA to keep consistent
        for c in columns_to_keep:
            if c not in df_excel.columns:
                df_excel[c] = pd.NA
    else:
        df_excel = pd.DataFrame(columns=columns_to_keep)

    # Fetch current month from 1st to yesterday
    first_of_month = date(today.year, today.month, 1)
    yesterday = today - timedelta(days=1)
    if yesterday < first_of_month:
        # nothing to fetch
        st.info("Δεν υπάρχουν νέες API κλήσεις — σήμερα είναι η πρώτη μέρα του μήνα.")
        df_current_month = pd.DataFrame()
    else:
        from_date = first_of_month.strftime("%Y-%m-%d")
        to_date = yesterday.strftime("%Y-%m-%d")
        st.info(f"📥 Φόρτωση κρατήσεων για τρέχον μήνα ({from_date} → {to_date}) (μόνο για εμφάνιση)...")
        df_current_month = fetch_reservations_with_retry(from_date, to_date)
        if df_current_month.empty:
            st.write(" - Δεν βρέθηκαν νέες κρατήσεις για τον τρέχοντα μήνα ή αποτυχία API.")
        else:
            df_current_month["platform"] = df_current_month["platform"].astype(str)
            df_current_month["price"] = df_current_month.apply(
                lambda row: float(row["price"]) / 0.82 if "expedia" in str(row["platform"]).lower() else float(row["price"]),
                axis=1
            )
            df_current_month = calculate_columns(df_current_month)
            # ensure columns
            for c in columns_to_keep:
                if c not in df_current_month.columns:
                    df_current_month[c] = pd.NA
            df_current_month = df_current_month[columns_to_keep]

    # Combine Excel data + current_month (display only, no save). Drop duplicates for nice view
    if df_current_month is not None and not df_current_month.empty:
        combined_display = pd.concat([df_excel, df_current_month], ignore_index=True, sort=False)
    else:
        combined_display = df_excel.copy()

    # drop duplicates for display (keep first occurrence)
    if "booking_id" in combined_display.columns:
        combined_display = combined_display.drop_duplicates(subset=["booking_id"], keep="first")

    # Round numeric fields for display
    for col in ["price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit", "Guests"]:
        if col in combined_display.columns:
            combined_display[col] = pd.to_numeric(combined_display[col], errors="coerce").round(2)

    df_display_source = combined_display.reindex(columns=columns_to_keep)

# ---------------- Sidebar: 선택 group ----------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

# Filter for selected group for display
if df_display_source.empty:
    df_filtered = pd.DataFrame(columns=columns_to_keep)
else:
    # apartment_id may be numeric; ensure dtype match
    df_filtered = df_display_source[df_display_source["apartment_id"].isin(APARTMENTS[selected_group])].copy()

# Round numeric values to 2 decimals (safety)
for col in ["price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit", "Guests"]:
    if col in df_filtered.columns:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").round(2)

# ---------------- Metrics per month (uses df_filtered and expenses_df; expenses not saved) ----------------
monthly_metrics = defaultdict(lambda: {"Total Price": 0.0, "Total Expenses": 0.0, "Owner Profit": 0.0})

for idx, row in df_filtered.iterrows():
    try:
        checkin = pd.to_datetime(row["arrival"])
        checkout = pd.to_datetime(row["departure"])
    except Exception:
        continue
    total_days = (checkout - checkin).days
    if total_days <= 0:
        continue

    daily_price = float(row.get("Price Without Tax", 0) or 0) / total_days
    daily_profit = float(row.get("Owner Profit", 0) or 0) / total_days
    current_day = checkin
    while current_day < checkout:
        year, month = current_day.year, current_day.month
        next_month_day = (current_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (min(checkout, next_month_day) - current_day).days

        monthly_metrics[(year, month)]["Total Price"] += daily_price * days_in_month
        monthly_metrics[(year, month)]["Owner Profit"] += daily_profit * days_in_month

        current_day = next_month_day

# Add expenses (only for metrics)
for idx, row in expenses_df.iterrows():
    if str(row.get("Accommodation", "")).upper() != selected_group.upper():
        continue
    try:
        key = (int(row["Year"]), int(row["Month"]))
    except Exception:
        continue
    monthly_metrics[key]["Total Expenses"] += parse_amount(row["Amount"])

# Build monthly table
months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
             7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

monthly_table = pd.DataFrame([
    {
        "Έτος": year,
        "Μήνας": months_el[month],
        "Συνολική Τιμή Κρατήσεων (€)": v["Total Price"],
        "Συνολικά Έξοδα (€)": v["Total Expenses"],
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": v["Owner Profit"] - v["Total Expenses"]
    }
    for (year, month), v in sorted(monthly_metrics.items())
])

# Format numbers to 2 decimals for display
if not monthly_table.empty:
    monthly_table["Συνολική Τιμή Κρατήσεων (€)"] = monthly_table["Συνολική Τιμή Κρατήσεων (€)"].map(lambda x: f"{x:.2f}")
    monthly_table["Συνολικά Έξοδα (€)"] = monthly_table["Συνολικά Έξοδα (€)"].map(lambda x: f"{x:.2f}")
    monthly_table["Καθαρό Κέρδος Ιδιοκτήτη (€)"] = monthly_table["Καθαρό Κέρδος Ιδιοκτήτη (€)"].map(lambda x: f"{x:.2f}")

# ---------------- Display in Streamlit (no coloring) ----------------
st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
if monthly_table.empty:
    st.info("Δεν υπάρχουν metrics για εμφάνιση.")
else:
    st.dataframe(monthly_table, use_container_width=True)

st.subheader(f"📅 Κρατήσεις ({selected_group})")
# display df_filtered: ensure columns order
st.dataframe(df_filtered[columns_to_keep], use_container_width=True)
