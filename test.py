import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict

# -------------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

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
# Ημερομηνίες
# -------------------------------------------------------------
today = date.today()
from_date = "2025-01-01"
to_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

# -------------------------------------------------------------
# Συναρτήσεις
# -------------------------------------------------------------
def compute_price_without_tax(price, nights, month, apt_name):
    if not price or not nights:
        return 0.0
    settings = APARTMENT_SETTINGS.get(apt_name, {"winter_base": 2, "summer_base": 8})
    base = settings["winter_base"] if month in [11,12,1,2] else settings["summer_base"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform_name: str, price: float) -> float:
    if not platform_name:
        return 0.0
    p = platform_name.strip().lower()
    if p in {"website","direct","direct booking","direct-booking","site","web"}:
        rate = 0.00
    elif "booking" in p:
        rate = 0.17
    elif "airbnb" in p:
        rate = 0.15
    elif "expedia" in p:
        rate = 0.18
    else:
        rate = 0.00
    return round((price or 0)*rate, 2)

def parse_amount(v):
    try:
        return float(str(v).replace("€","").strip())
    except:
        return 0.0

# -------------------------------------------------------------
# Φόρτωση Excel ή κενά DataFrames
# -------------------------------------------------------------
RESERVATIONS_FILE = "reservations.xlsx"
EXPENSES_FILE = "expenses.xlsx"

try:
    reservations_df = pd.read_excel(RESERVATIONS_FILE)
except FileNotFoundError:
    reservations_df = pd.DataFrame(columns=[
        "ID","Apartment","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee",
        "Price Without Tax","Airstay Commission","Owner Profit","Month"
    ])

try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Φόρτωση ΟΛΩΝ των κρατήσεων από Smoobu (2025-01-01 έως χθες)
# -------------------------------------------------------------
all_rows = []

st.info(f"📅 Φόρτωση κρατήσεων από {from_date} έως {to_date}")

for apt_name, id_list in APARTMENTS.items():
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
            except requests.exceptions.RequestException as e:
                st.warning(f"⚠️ Σφάλμα για {apt_name}: {e}")
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

                if not (date(2025,1,1) <= arrival_dt.date() <= (today - timedelta(days=1))):
                    continue

                platform = (b.get("channel") or {}).get("name") or "Direct booking"
                price = float(b.get("price") or 0)
                adults = int(b.get("adults") or 0)
                children = int(b.get("children") or 0)
                guests = adults + children
                days = max((departure_dt - arrival_dt).days, 0)

                if "expedia" in platform.lower():
                    price = price / 0.82

                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, apt_name)
                fee = compute_booking_fee(platform, price)
                settings = APARTMENT_SETTINGS.get(apt_name, {"airstay_commission": 0.248})
                airstay_commission = round(price_wo_tax * settings["airstay_commission"], 2)
                owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

                all_rows.append({
                    "ID": b.get("id"),
                    "Apartment": apt_name,
                    "Guest Name": b.get("guestName") or b.get("guest-name"),
                    "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                    "Departure": departure_dt.strftime("%Y-%m-%d"),
                    "Days": days,
                    "Platform": platform,
                    "Guests": guests,
                    "Total Price": round(price, 2),
                    "Booking Fee": round(fee, 2),
                    "Price Without Tax": round(price_wo_tax, 2),
                    "Airstay Commission": round(airstay_commission, 2),
                    "Owner Profit": round(owner_profit, 2),
                    "Month": arrival_dt.month
                })

            if data.get("page") and data.get("page") < data.get("page_count", 1):
                params["page"] += 1
            else:
                break

if all_rows:
    reservations_df = pd.DataFrame(all_rows)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    reservations_df.to_excel(RESERVATIONS_FILE, index=False)
    st.success(f"✅ Αποθηκεύτηκαν όλες οι κρατήσεις στο Excel ({len(reservations_df)}).")
else:
    st.info("Δεν υπάρχουν κρατήσεις για φόρτωση.")
