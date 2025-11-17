import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
from github import Github

# -------------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# Paths για αρχεία Excel
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.xlsx")
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# -------------------------------------------------------------
# Επιλογή λειτουργίας
# -------------------------------------------------------------
FETCH_MODE = "show_only"  # ή "show_only" ή "save_and_show"
start_month = 1
end_month = 10

# -------------------------------------------------------------
# Ημερομηνίες
# -------------------------------------------------------------
today = date.today()
yesterday = today - timedelta(days=1)

if FETCH_MODE == "show_only":
    from_date = date(today.year, today.month, 1).strftime("%Y-%m-%d")
    to_date = yesterday.strftime("%Y-%m-%d")
else:
    from_date = date(today.year, start_month, 1).strftime("%Y-%m-%d")
    next_month = date(today.year, end_month, 28) + timedelta(days=4)
    last_day = (next_month - timedelta(days=next_month.day)).day
    to_date = date(today.year, end_month, last_day).strftime("%Y-%m-%d")

# -------------------------------------------------------------
# Καταλύματα & Settings
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# Sidebar: Επιλογή μήνα/καταλύματος
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

st.sidebar.header("📅 Επιλογή Μηνών")
start_month = st.sidebar.number_input("Από μήνα", min_value=1, max_value=12, value=1)
end_month = st.sidebar.number_input("Έως μήνα", min_value=1, max_value=12, value=date.today().month)

# -------------------------------------------------------------
# Fetch Reservations
# -------------------------------------------------------------
def fetch_reservations(from_date, to_date):
    params = {"dateFrom": from_date, "dateTo": to_date}
    r = requests.get(reservations_url, headers=headers, params=params)
    if r.status_code != 200:
        st.error(f"Σφάλμα API: {r.status_code}")
        return pd.DataFrame()
    data = r.json()
    df = pd.DataFrame(data)
    return df

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------
def get_group_by_apartment(apt_id):
    for g, apt_list in APARTMENTS.items():
        if apt_id in apt_list:
            return g
    return None

def calculate_price_without_tax(row):
    price = float(row.get("price", 0))
    nights = float(row.get("numberOfNights", 0))
    month = int(row.get("month", 0))
    platform = str(row.get("platform", "")).upper()
    winter_months = [1, 2, 3, 11, 12]

    apartment_id = row.get("apartmentId")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0

    winter_base = APARTMENT_SETTINGS[group]["winter_base"]
    summer_base = APARTMENT_SETTINGS[group]["summer_base"]
    base = winter_base if month in winter_months else summer_base

    if platform == "EXPEDIA":
        adjusted = (price * 0.82) - (base * nights)
        result = (adjusted / 1.13) - (adjusted * 0.005) + (price * 0.18)
        return result

    adjusted = price - (base * nights)
    result = (adjusted / 1.13) - (adjusted * 0.005)
    return result

def get_booking_fee(row):
    platform = str(row.get("platform", "")).lower()
    total = float(row.get("price", 0))
    apartment_id = row.get("apartmentId")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0

    settings = APARTMENT_SETTINGS[group]

    if "booking" in platform:
        return total * settings.get("booking_fee", 0.166)
    if "airbnb" in platform:
        return total * 0.15
    if "expedia" in platform:
        return total * 0.18

    return total * settings.get("booking_fee_other", 0.0)

def calculate_airstay_commission(row):
    price_without_tax = row.get("Price Without Tax", 0)
    apartment_id = row.get("apartmentId")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0
    rate = APARTMENT_SETTINGS[group].get("airstay_commission", 0.0)
    return price_without_tax * rate

def calculate_columns(df):
    if df.empty:
        return df

    df["Price Without Tax"] = df.apply(calculate_price_without_tax, axis=1)
    df["Booking Fee"] = df.apply(get_booking_fee, axis=1)
    df["Airstay Commission"] = df.apply(calculate_airstay_commission, axis=1)
    df["Owner Profit"] = df["Price Without Tax"] - df["Booking Fee"] - df["Airstay Commission"]

    return df

# -------------------------------------------------------------
# Load Expenses
# -------------------------------------------------------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])

def parse_amount(v):
    try:
        return float(v)
    except:
        return 0.0

# -------------------------------------------------------------
# Main Flow
# -------------------------------------------------------------
today = date.today()
from_date = date(today.year, start_month, 1).strftime("%Y-%m-%d")
next_month = date(today.year, end_month, 28) + timedelta(days=4)
last_day = (next_month - timedelta(days=next_month.day)).day
to_date = date(today.year, end_month, last_day).strftime("%Y-%m-%d")

df_new = fetch_reservations(from_date, to_date)
df_new = calculate_columns(df_new)

# Φιλτράρισμα ανά group
df_filtered = df_new[df_new["apartmentId"].isin(APARTMENTS[selected_group])]

# -------------------------------------------------------------
# Metrics ανά μήνα
# -------------------------------------------------------------
monthly_metrics = defaultdict(lambda: {"Total Price": 0, "Total Expenses": 0, "Owner Profit": 0})

for idx, row in df_filtered.iterrows():
    checkin = pd.to_datetime(row.get("arrivalDate", today))
    checkout = pd.to_datetime(row.get("departureDate", today))
    total_days = (checkout - checkin).days
    if total_days == 0:
        continue

    daily_price = row["Price Without Tax"] / total_days
    daily_profit = row["Owner Profit"] / total_days

    current_day = checkin
    while current_day < checkout:
        year, month = current_day.year, current_day.month
        next_month_day = (current_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (min(checkout, next_month_day) - current_day).days

        monthly_metrics[(year, month)]["Total Price"] += daily_price * days_in_month
        monthly_metrics[(year, month)]["Owner Profit"] += daily_profit * days_in_month

        current_day = next_month_day

# Προσθήκη εξόδων ανά μήνα
for idx, row in expenses_df.iterrows():
    if row["Accommodation"].upper() != selected_group.upper():
        continue
    key = (int(row["Year"]), int(row["Month"]))
    monthly_metrics[key]["Total Expenses"] += parse_amount(row["Amount"])

months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

monthly_table = pd.DataFrame([
    {
        "Έτος": year,
        "Μήνας": months_el[month],
        "Συνολική Τιμή Κρατήσεων (€)": f"{v['Total Price']:.2f}",
        "Συνολικά Έξοδα (€)": f"{v['Total Expenses']:.2f}",
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{v['Owner Profit'] - v['Total Expenses']:.2f}"
    }
    for (year, month), v in sorted(monthly_metrics.items())
])

# -------------------------------------------------------------
# Εμφάνιση στο Streamlit
# -------------------------------------------------------------
st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
st.dataframe(monthly_table, use_container_width=True)

st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(df_filtered, use_container_width=True)

# -------------------------------------------------------------
# Αποθήκευση σε Excel
# -------------------------------------------------------------
df_filtered.to_excel(RESERVATIONS_FILE, index=False)
st.success(f"✅ Οι κρατήσεις αποθηκεύτηκαν στο {RESERVATIONS_FILE}")

# -------------------------------------------------------------
# Upload στο GitHub
# -------------------------------------------------------------
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
    st.warning(f"⚠️ Σφάλμα κατά το ανέβασμα στο GitHub: {e}"))
