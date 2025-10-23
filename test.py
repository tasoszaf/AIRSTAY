import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os
import subprocess

# -------------------------------------------------------------
# ΡΥΘΜΙΣΕΙΣ STREAMLIT
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("📊 Smoobu Reservations Dashboard")

# -------------------------------------------------------------
# API & GITHUB ΡΥΘΜΙΣΕΙΣ
# -------------------------------------------------------------
SMOOBU_API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
HEADERS = {"Api-Key": SMOOBU_API_KEY, "Content-Type": "application/json"}
RESERVATIONS_URL = "https://login.smoobu.com/api/reservations"

GITHUB_ENABLED = True  # Βάλε False αν δε θες push
GITHUB_REPO_PATH = "https://github.com/tasoszaf/AIRSTAY"  # <-- Βάλε path του repo σου

RES_FILE = "reservations.xlsx"
EXP_FILE = "expenses.xlsx"

# -------------------------------------------------------------
# ΚΑΤΑΛΥΜΑΤΑ & ΡΥΘΜΙΣΕΙΣ
# -------------------------------------------------------------
APARTMENTS = {
    "ZED": [1439913,1439915,1439917,1439919,1439921,1439923,1439925,1439927,1439929,
            1439931,1439933,1439935,1439937,1439939,1439971,1439973,1439975,1439977,
            1439979,1439981,1439983,1439985],
    "KOMOS": [2160281,2160286,2160291],
    "CHELI": [2146456,2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH": [563628,563631,1200587,563634,563637,563640,563643],
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
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "KALISTA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "AKALI": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0},
    "ZILEAN": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "NAUTILUS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.186},
    "ANIVIA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "ELISE": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "ORIANNA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "JAAX": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.0},
    "FINIKAS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
}

# -------------------------------------------------------------
# ΗΜΕΡΟΜΗΝΙΕΣ
# -------------------------------------------------------------
today = date.today()
first_day_year = date(today.year, 1, 1)
first_day_month = today.replace(day=1)
yesterday = today - timedelta(days=1)
last_month = (first_day_month - timedelta(days=1)).month
last_month_year = (first_day_month - timedelta(days=1)).year

# -------------------------------------------------------------
# ΥΠΟΛΟΓΙΣΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ
# -------------------------------------------------------------
def compute_price_without_tax(price, nights, month, apt):
    s = APARTMENT_SETTINGS.get(apt, {"winter_base": 2, "summer_base": 8})
    base = s["winter_base"] if month in [11,12,1,2] else s["summer_base"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform, price):
    if not platform: return 0.0
    p = platform.lower().strip()
    if "booking" in p: r = 0.17
    elif "airbnb" in p: r = 0.15
    elif "expedia" in p: r = 0.18
    else: r = 0.0
    return round(price * r, 2)

# -------------------------------------------------------------
# ΑΝΑΚΤΗΣΗ ΚΡΑΤΗΣΕΩΝ ΑΠΟ API
# -------------------------------------------------------------
def fetch_reservations(from_date, to_date):
    all_rows = []
    for apt, ids in APARTMENTS.items():
        for aid in ids:
            params = {"from": from_date, "to": to_date, "apartmentId": aid, "excludeBlocked": "true"}
            try:
                r = requests.get(RESERVATIONS_URL, headers=HEADERS, params=params, timeout=30)
                bookings = r.json().get("bookings", [])
            except Exception as e:
                st.warning(f"⚠️ Σφάλμα API για {apt}: {e}")
                continue

            for b in bookings:
                arr, dep = b.get("arrival"), b.get("departure")
                if not arr or not dep: continue
                arr_dt, dep_dt = datetime.strptime(arr, "%Y-%m-%d"), datetime.strptime(dep, "%Y-%m-%d")
                days = (dep_dt - arr_dt).days
                platform = (b.get("channel") or {}).get("name") or "Direct"
                price = float(b.get("price") or 0)
                price_wo_tax = compute_price_without_tax(price, days, arr_dt.month, apt)
                fee = compute_booking_fee(platform, price)
                comm = round(price_wo_tax * APARTMENT_SETTINGS.get(apt, {}).get("airstay_commission", 0), 2)
                owner = round(price_wo_tax - fee - comm, 2)
                all_rows.append({
                    "ID": b.get("id"),
                    "Apartment": apt,
                    "Guest": b.get("guestName"),
                    "Arrival": arr,
                    "Departure": dep,
                    "Days": days,
                    "Platform": platform,
                    "Total Price": price,
                    "Booking Fee": fee,
                    "Price Without Tax": price_wo_tax,
                    "Airstay Commission": comm,
                    "Owner Profit": owner,
                    "Month": arr_dt.month,
                })
    return pd.DataFrame(all_rows)

# -------------------------------------------------------------
# ΦΟΡΤΩΣΗ Ή ΑΝΑΚΤΗΣΗ ΚΡΑΤΗΣΕΩΝ
# -------------------------------------------------------------
if not os.path.exists(RES_FILE):
    st.info("🔄 Πρώτη εκτέλεση – γίνεται ανάκτηση όλων των κρατήσεων από 1/1 έως χθες...")
    df_all = fetch_reservations(first_day_year.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
else:
    df_all = pd.read_excel(RES_FILE)
    df_current = fetch_reservations(first_day_month.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
    df_all = pd.concat([df_all, df_current]).drop_duplicates(subset=["ID"])

# -------------------------------------------------------------
# ΑΠΟΘΗΚΕΥΣΗ ΕΩΣ ΠΡΟΗΓΟΥΜΕΝΟ ΜΗΝΑ
# -------------------------------------------------------------
df_to_save = df_all[pd.to_datetime(df_all["Arrival"]) < first_day_month]
df_to_save.to_excel(RES_FILE, index=False)

# -------------------------------------------------------------
# PUSH ΣΤΟ GITHUB
# -------------------------------------------------------------
if GITHUB_ENABLED:
    try:
        os.chdir(GITHUB_REPO_PATH)
        subprocess.run(["git", "config", "user.name", GIT_USER_NAME])
        subprocess.run(["git", "config", "user.email", GIT_USER_EMAIL])
        subprocess.run(["git", "add", RES_FILE])
        subprocess.run(["git", "commit", "-m", f"Auto-update reservations until {last_month}/{last_month_year}"])
        subprocess.run(["git", "push"])
        st.success("✅ Ενημερώθηκε και στάλθηκε στο GitHub.")
    except Exception as e:
        st.warning(f"⚠️ Σφάλμα GitHub push: {e}")

# -------------------------------------------------------------
# STREAMLIT UI
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_apt = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

filtered = df_all[df_all["Apartment"] == selected_apt].sort_values("Arrival")

st.subheader(f"📅 Κρατήσεις – {selected_apt}")
st.dataframe(filtered, use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# ΥΠΟΛΟΓΙΣΜΟΣ ΣΥΝΟΛΙΚΩΝ
# -------------------------------------------------------------
total_income = df_all["Total Price"].sum()
total_owner = df_all["Owner Profit"].sum()

if os.path.exists(EXP_FILE):
    exp_df = pd.read_excel(EXP_FILE)
    total_expenses = exp_df["Amount"].sum()
else:
    total_expenses = 0.0

net_profit = total_owner - total_expenses

# -------------------------------------------------------------
# ΠΙΝΑΚΑΣ ΣΥΝΟΛΙΚΩΝ
# -------------------------------------------------------------
st.subheader("📊 Συνολικά Στοιχεία (1/1 έως σήμερα)")
summary = pd.DataFrame({
    "Σύνολο Εσόδων (€)": [round(total_income, 2)],
    "Σύνολο Εξόδων (€)": [round(total_expenses, 2)],
    "Καθαρό Κέρδος (€)": [round(net_profit, 2)]
})
st.table(summary)
