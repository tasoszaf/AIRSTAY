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
FETCH_MODE = "save_and_show"  # ή "show_only"

start_month = 1  # από
end_month = 10   # έως

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
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "THRESH_A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "THRESH_A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
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
# Φόρτωση Excel
# -------------------------------------------------------------
try:
    reservations_df = pd.read_excel(RESERVATIONS_FILE)
except FileNotFoundError:
    reservations_df = pd.DataFrame(columns=[
        "ID","Apartment_ID","Group","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee",
        "Price Without Tax","Airstay Commission","Owner Profit","Month","Year"
    ])

try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Date","Month","Year","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Συνάρτηση ανάκτησης κρατήσεων
# -------------------------------------------------------------
def fetch_reservations(from_date, to_date):
    rows = []
    THRESH_IDS = {1200587, 563634, 563637, 563640}

    for group_name, id_list in APARTMENTS.items():
        for apt_id in id_list:
            params = {
                "from": from_date,
                "to": to_date,
                "apartmentId": apt_id,
                "excludeBlocked": "true",
                "showCancellation": "false",
                "page": 1,
                "pageSize": 100,
            }
            while True:
                try:
                    r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                except requests.exceptions.RequestException:
                    break

                bookings = data.get("bookings", [])
                if not bookings:
                    break

                for b in bookings:
                    arrival_str = b.get("arrival")
                    departure_str = b.get("departure")
                    if not arrival_str or not departure_str:
                        continue
                    try:
                        arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d")
                        departure_dt = datetime.strptime(departure_str, "%Y-%m-%d")
                    except:
                        continue

                    if departure_dt < datetime(2025, 1, 2):
                        continue

                    platform = (b.get("channel") or {}).get("name") or "Direct booking"
                    price = float(b.get("price") or 0)
                    adults = int(b.get("adults") or 0)
                    children = int(b.get("children") or 0)
                    guests = adults + children
                    days = max((departure_dt - arrival_dt).days, 0)
                    platform_lower = platform.lower().strip()
                    if "expedia" in platform_lower:
                        price = price / 0.82
                    apt_real_id = b.get("apartment", {}).get("id", apt_id)
                    if apt_real_id in THRESH_IDS:
                        price_wo_tax = round(price, 2)
                    else:
                        settings = APARTMENT_SETTINGS.get(group_name, {"winter_base":2,"summer_base":8})
                        base = settings["winter_base"] if arrival_dt.month in [11,12,1,2] else settings["summer_base"]
                        adjusted = price - base * days
                        price_wo_tax = round((adjusted / 1.13) - (adjusted * 0.005), 2)
                    if not platform:
                        fee = 0
                    elif "booking" in platform_lower:
                        fee = round(price * 0.17, 2)
                    elif "airbnb" in platform_lower:
                        fee = round(price * 0.15, 2)
                    elif "expedia" in platform_lower:
                        fee = round(price * 0.18, 2)
                    else:
                        fee = 0
                    settings = APARTMENT_SETTINGS.get(group_name, {"airstay_commission": 0.248})
                    airstay_commission = round(price_wo_tax * settings["airstay_commission"], 2)
                    owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

                    rows.append({
                        "ID": b.get("id"),
                        "Apartment_ID": apt_real_id,
                        "Group": group_name,
                        "Guest Name": b.get("guest-name"),
                        "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                        "Departure": departure_dt.strftime("%Y-%m-%d"),
                        "Days": days,
                        "Platform": platform,
                        "Guests": guests,
                        "Total Price": round(price,2),
                        "Booking Fee": round(fee,2),
                        "Price Without Tax": round(price_wo_tax,2),
                        "Airstay Commission": round(airstay_commission,2),
                        "Owner Profit": round(owner_profit,2),
                        "Month": arrival_dt.month,
                        "Year": arrival_dt.year
                    })
                if data.get("page") and data.get("page") < data.get("page_count",1):
                    params["page"] += 1
                else:
                    break
    return rows

# -------------------------------------------------------------
# Fetch & Save
# -------------------------------------------------------------
all_rows = fetch_reservations(from_date, to_date)

if FETCH_MODE == "save_and_show":
    reservations_df = pd.concat([reservations_df, pd.DataFrame(all_rows)], ignore_index=True)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    reservations_df.to_excel(RESERVATIONS_FILE, index=False)
    st.success(f"✅ Αποθηκεύτηκαν {len(all_rows)} κρατήσεις ({from_date} → {to_date})")
else:
    st.info(f"Φορτώθηκαν {len(all_rows)} κρατήσεις μόνο για εμφάνιση")

# -------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
filtered_df = reservations_df[reservations_df["Group"]==selected_group].copy()
filtered_df = filtered_df.sort_values(["Arrival"]).reset_index(drop=True)

st.dataframe(filtered_df, width="stretch", hide_index=True)

# -------------------------------------------------------------
# 📤 Αυτόματο ανέβασμα στο GitHub
# -------------------------------------------------------------
def upload_to_github(local_path, repo_path):
    """Ανεβάζει ή ενημερώνει ένα αρχείο στο GitHub repo"""
    try:
        token = st.secrets["github"]["token"]
        username = st.secrets["github"]["username"]
        repo_name = st.secrets["github"]["repo"]

        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        with open(local_path, "rb") as f:
            file_content = f.read()

        try:
            contents = repo.get_contents(repo_path)
            repo.update_file(
                path=contents.path,
                message=f"Αυτόματη ενημέρωση από Streamlit ({datetime.now():%Y-%m-%d %H:%M})",
                content=file_content,
                sha=contents.sha,
            )
            st.success("✅ Το reservations.xlsx ενημερώθηκε στο GitHub.")
        except Exception:
            repo.create_file(
                path=repo_path,
                message=f"Προσθήκη νέου reservations.xlsx ({datetime.now():%Y-%m-%d %H:%M})",
                content=file_content,
            )
            st.success("✅ Το reservations.xlsx ανέβηκε στο GitHub.")
    except Exception as e:
        st.error(f"❌ Σφάλμα κατά την αποστολή στο GitHub: {e}")

# Εκτέλεση αυτόματης αποστολής
upload_to_github(RESERVATIONS_FILE, "reservations.xlsx")
