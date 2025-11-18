import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
from github import Github
import time

# -------------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

# -------------------------------------------------------------
# Config (βάλε εδώ το API KEY / ή καλύτερα st.secrets)
# -------------------------------------------------------------
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
# Hardcoded Months Range (τροποποίησε όπως θες)
# -------------------------------------------------------------
START_MONTH = 1
END_MONTH = 10
today = date.today()

# -------------------------------------------------------------
# Καταλύματα & Settings (πλήρεις λίστες όπως πριν)
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
# Helper Functions
# -------------------------------------------------------------
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
            # επιστρέφουμε κενό DataFrame σε περίπτωση σφάλματος δικτύου/API
            return pd.DataFrame()
        data = r.json()
        all_bookings.extend(data.get("bookings", []))
        if params["page"] >= data.get("page_count", 1):
            break
        params["page"] += 1

    if not all_bookings:
        return pd.DataFrame()

    df = pd.json_normalize(all_bookings)
    # rename για συνέπεια
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
    # Αποκλείουμε blocked bookings αν υπάρχει το πεδίο
    df = df[df.get("is-blocked-booking", False) == False]
    return df

def fetch_reservations_with_retry(from_date, to_date, retries=3, delay=5):
    for attempt in range(retries):
        df = fetch_reservations(from_date, to_date)
        if not df.empty:
            return df
        # μικρό pause και επανάληψη
        time.sleep(delay)
    return pd.DataFrame()

def get_group_by_apartment(apt_id):
    for g, apt_list in APARTMENTS.items():
        if apt_id in apt_list:
            return g
    return None

def calculate_price_without_tax(row):
    price = float(row.get("price", 0))
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
    total = float(row.get("price", 0))
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
    price_without_tax = row.get("Price Without Tax", 0)
    apartment_id = row.get("apartment_id")
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
    # βεβαιώσου ότι υπάρχουν οι στήλες adults/children
    df["adults"] = df.get("adults", 0).fillna(0).astype(float)
    df["children"] = df.get("children", 0).fillna(0).astype(float)
    df["Guests"] = df["adults"] + df["children"]
    return df

# -------------------------------------------------------------
# Load Expenses (θα χρησιμοποιηθούν μόνο για τα metrics, ΔΕΝ θα αποθηκευτούν στο Excel)
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
# Fetch reservations ανά μήνα (batch)
# -------------------------------------------------------------
all_dfs = []
for month in range(START_MONTH, END_MONTH + 1):
    from_date = date(today.year, month, 1).strftime("%Y-%m-%d")
    next_month = date(today.year, month, 28) + timedelta(days=4)
    last_day = (next_month - timedelta(days=next_month.day)).day
    to_date = date(today.year, month, last_day).strftime("%Y-%m-%d")

    st.info(f"📥 Φόρτωση κρατήσεων για {month}/{today.year}...")
    df_month = fetch_reservations_with_retry(from_date, to_date)
    if df_month.empty:
        st.write(f" - Δεν βρέθηκαν κρατήσεις για {month}/{today.year} ή αποτυχία API.")
        continue

    # Διόρθωση τιμής για Expedia (πριν υπολογισμούς)
    df_month["platform"] = df_month["platform"].astype(str)
    df_month["price"] = df_month.apply(
        lambda row: float(row["price"]) / 0.82 if "expedia" in str(row["platform"]).lower() else float(row["price"]),
        axis=1
    )

    # Υπολογιστικά πεδία
    df_month = calculate_columns(df_month)
    all_dfs.append(df_month)

# Συγκέντρωση όλων των μηνών
df_new = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# -------------------------------------------------------------
# Αποθήκευση στο ίδιο Excel - ΜΟΝΟ οι στήλες που εμφανίζονται στην εφαρμογή
# (όπως συμφωνήσαμε)
# -------------------------------------------------------------
# Στήλες που θέλουμε να αποθηκεύουμε
columns_to_keep = [
    "booking_id", "apartment_id", "apartment_name", "platform",
    "guest_name", "arrival", "departure",
    "Guests", "price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit"
]

# Βεβαιωνόμαστε ότι το df_new περιέχει τις στηλες (αν όχι, γεμίζουμε με NaN)
for c in columns_to_keep:
    if c not in df_new.columns:
        df_new[c] = pd.NA

# Επιλέγουμε μόνο τις στήλες που θέλουμε
df_to_store = df_new[columns_to_keep].copy()

# Append + drop duplicates (βάσει booking_id)
if os.path.exists(RESERVATIONS_FILE):
    existing_df = pd.read_excel(RESERVATIONS_FILE)
    # κράτησε μόνο τις στήλες που εμφανίζονται στο παλιό αρχείο, αν υπάρχουν
    # (για συνέπεια στη δομή του αρχείου)
    existing_cols = [c for c in existing_df.columns if c in columns_to_keep]
    if existing_cols:
        existing_df = existing_df[existing_cols]
    combined_df = pd.concat([existing_df, df_to_store], ignore_index=True, sort=False)
    # drop duplicates βάσει booking_id - κρατάμε την πρώτη εμφάνιση
    combined_df = combined_df.drop_duplicates(subset=["booking_id"], keep="first")
    # εξασφαλίζουμε τις τελικές στήλες με σωστή σειρά
    df_to_store_final = combined_df.reindex(columns=columns_to_keep)
else:
    df_to_store_final = df_to_store

# Αποθήκευση
df_to_store_final.to_excel(RESERVATIONS_FILE, index=False)
st.success(f"✅ Οι κρατήσεις αποθηκεύτηκαν στο {RESERVATIONS_FILE} (μόνο οι εμφανιζόμενες στήλες).")

# -------------------------------------------------------------
# Upload στο GitHub (χρησιμοποιώντας st.secrets["github"])
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
    st.warning(f"⚠️ Σφάλμα κατά το ανέβασμα στο GitHub: {e}")

# -------------------------------------------------------------
# Sidebar επιλογής γκρουπ & φιλτράρισμα για εμφάνιση
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

if df_to_store_final.empty:
    df_filtered = pd.DataFrame(columns=columns_to_keep)
else:
    df_filtered = df_to_store_final[df_to_store_final["apartment_id"].isin(APARTMENTS[selected_group])]

# -------------------------------------------------------------
# Metrics ανά μήνα με έξοδα (χρησιμοποιεί expenses_df, αλλά δεν το αποθηκεύει)
# -------------------------------------------------------------
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

    daily_price = float(row.get("Price Without Tax", 0)) / total_days
    daily_profit = float(row.get("Owner Profit", 0)) / total_days
    current_day = checkin
    while current_day < checkout:
        year, month = current_day.year, current_day.month
        next_month_day = (current_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (min(checkout, next_month_day) - current_day).days

        monthly_metrics[(year, month)]["Total Price"] += daily_price * days_in_month
        monthly_metrics[(year, month)]["Owner Profit"] += daily_profit * days_in_month

        current_day = next_month_day

# Προσθήκη εξόδων από expenses_df (αν υπάρχουν) — τα έξοδα ΔΕΝ αποθηκεύονται στο Excel
for idx, row in expenses_df.iterrows():
    if str(row.get("Accommodation", "")).upper() != selected_group.upper():
        continue
    key = (int(row["Year"]), int(row["Month"]))
    monthly_metrics[key]["Total Expenses"] += parse_amount(row["Amount"])

# Μετατροπή σε DataFrame για εμφάνιση
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

# Στρογγυλοποίηση εμφάνισης
if not monthly_table.empty:
    monthly_table["Συνολική Τιμή Κρατήσεων (€)"] = monthly_table["Συνολική Τιμή Κρατήσεων (€)"].map(lambda x: f"{x:.2f}")
    monthly_table["Συνολικά Έξοδα (€)"] = monthly_table["Συνολικά Έξοδα (€)"].map(lambda x: f"{x:.2f}")
    monthly_table["Καθαρό Κέρδος Ιδιοκτήτη (€)"] = monthly_table["Καθαρό Κέρδος Ιδιοκτήτη (€)"].map(lambda x: f"{x:.2f}")

# -------------------------------------------------------------
# Highlighting (έγχρωμη επισήμανση) στα metrics
# -------------------------------------------------------------
def highlight_row(row):
    try:
        net = float(row["Καθαρό Κέρδος Ιδιοκτήτη (€)"])
        exp = float(row["Συνολικά Έξοδα (€)"])
    except Exception:
        return [""] * len(row)
    color_net = "background-color: #b6fcb6" if net >= 0 else "background-color: #fcb6b6"
    color_exp = "background-color: #fff2b6"
    # Επιστρέφουμε style ανά στήλη στη σειρά που εμφανίζεται το monthly_table
    return ["", "", "", color_exp, color_net]

st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
if monthly_table.empty:
    st.info("Δεν υπάρχουν metrics για εμφάνιση.")
else:
    # Εμφάνιση με style
    st.dataframe(monthly_table.style.apply(highlight_row, axis=1), use_container_width=True)

# -------------------------------------------------------------
# Εμφάνιση κρατήσεων (φιλτραρισμένες για το επιλεγμένο group)
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(df_filtered, use_container_width=True)
