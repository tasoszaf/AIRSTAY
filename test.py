import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os

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

THRESH_SPECIAL_IDS = {563637, 563640, 563643, 1200587}  # IDs για τα οποία Price Without Tax = Total Price

# -------------------------------------------------------------
# Ημερομηνίες
# -------------------------------------------------------------
today = date.today()
first_day_of_month = date(today.year, today.month, 1)
last_month = first_day_of_month - timedelta(days=1)

# -------------------------------------------------------------
# Φόρτωση ή δημιουργία Excel
# -------------------------------------------------------------
if os.path.exists(RESERVATIONS_FILE):
    reservations_df = pd.read_excel(RESERVATIONS_FILE)
    first_run = False
else:
    reservations_df = pd.DataFrame(columns=[
        "ID","Group","Apartment_ID","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee","Price Without Tax","Airstay Commission",
        "Owner Profit","Year"
    ])
    first_run = True

# -------------------------------------------------------------
# Συνθήκες για κλήση API
# -------------------------------------------------------------
if first_run:
    from_date = f"{today.year}-01-01"
    to_date = last_month.strftime("%Y-%m-%d")
else:
    from_date = first_day_of_month.strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

# -------------------------------------------------------------
# Συναρτήσεις υπολογισμού
# -------------------------------------------------------------
def compute_price_without_tax(price, nights, month, apt_name, apt_id):
    if not price or not nights:
        return 0.0
    if apt_id in THRESH_SPECIAL_IDS:
        return round(price, 2)
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
# Ανάκτηση νέων κρατήσεων από Smoobu
# -------------------------------------------------------------
all_rows = []
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
                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, group_name, apt_real_id)
                fee = compute_booking_fee(platform, price)
                settings = APARTMENT_SETTINGS.get(group_name, {"airstay_commission": 0.248})
                airstay_commission = round(price_wo_tax * settings["airstay_commission"], 2)
                owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

                all_rows.append({
                    "ID": b.get("id"),
                    "Group": group_name,
                    "Apartment_ID": apt_real_id,
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
                    "Year": arrival_dt.year
                })

            if data.get("page") and data.get("page") < data.get("page_count",1):
                params["page"] += 1
            else:
                break

# Προσθήκη στο Excel μόνο αν πρώτης εκτέλεσης
if first_run and all_rows:
    new_df = pd.DataFrame(all_rows)
    reservations_df = pd.concat([reservations_df, new_df], ignore_index=True)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    reservations_df.to_excel(RESERVATIONS_FILE, index=False)

# -------------------------------------------------------------
# Sidebar επιλογής καταλύματος
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

display_df = reservations_df[reservations_df["Group"]==selected_group].copy()
display_df = display_df.sort_values(["Arrival"]).reset_index(drop=True)

# -------------------------------------------------------------
# Metrics ανά μήνα
# -------------------------------------------------------------
months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

monthly_metrics = defaultdict(lambda: {"Total Price":0, "Total Expenses":0, "Owner Profit":0})

for idx, row in display_df.iterrows():
    arrival = pd.to_datetime(row["Arrival"])
    departure = pd.to_datetime(row["Departure"])
    total_days = (departure - arrival).days
    if total_days == 0:
        continue
    start_day = max(arrival, pd.Timestamp(today.year,1,2))
    end_day = min(departure, pd.Timestamp(today.year, today.month, today.day))
    days_total = (end_day - start_day).days
    if days_total == 0:
        continue

    price_per_day = row["Total Price"] / total_days
    owner_profit_per_day = row["Owner Profit"] / total_days

    for i in range(days_total):
        day = start_day + pd.Timedelta(days=i)
        key = (day.year, day.month)
        monthly_metrics[key]["Total Price"] += price_per_day
        monthly_metrics[key]["Owner Profit"] += owner_profit_per_day

# Προσθήκη εξόδων
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Date","Month","Year","Accommodation","Category","Amount","Description"])

for (year, month) in list(monthly_metrics.keys()):
    df_exp_month = expenses_df[
        (expenses_df["Month"]==month) &
        (pd.to_datetime(expenses_df["Date"]).dt.year==year) &
        (expenses_df["Accommodation"].str.upper()==selected_group.upper())
    ]
    monthly_metrics[(year, month)]["Total Expenses"] = df_exp_month["Amount"].apply(parse_amount).sum()

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

st.subheader(f"📊 Metrics ανά μήνα ({selected_group}) - {today.year}")
st.dataframe(monthly_table, width="stretch", hide_index=True)

# -------------------------------------------------------------
# Εμφάνιση κρατήσεων (ασφαλής επιλογή columns για KeyError)
# -------------------------------------------------------------
columns_to_show = [
    "ID","Group","Apartment_ID","Guest Name","Arrival","Departure","Days","Platform","Guests",
    "Total Price","Booking Fee","Price Without Tax","Airstay Commission","Owner Profit"
]
existing_columns = [col for col in columns_to_show if col in display_df.columns]

st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(display_df[existing_columns], width="stretch", hide_index=True)



