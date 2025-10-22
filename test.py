import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta

st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "YOUR_API_KEY"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"
EXP_FILE = "reservations.xlsx"

# -------------------- Καταλύματα & Ρυθμίσεις --------------------
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

months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",
             5:"Μάιος",6:"Ιούνιος",7:"Ιούλιος",8:"Αύγουστος",
             9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

# -------------------- Φόρτωση προηγούμενων δεδομένων --------------------
try:
    df_excel = pd.read_excel(EXP_FILE)
except FileNotFoundError:
    df_excel = pd.DataFrame(columns=["ID","Apartment","Guest Name","Arrival","Departure",
                                     "Days","Platform","Total Price","Booking Fee",
                                     "Owner Profit","Month"])

# -------------------- Επιλογή Καταλύματος --------------------
selected_apartment = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

# -------------------- API call μόνο για τρέχοντα μήνα --------------------
today = date.today()
first_day_month = today.replace(day=1)
last_day_yesterday = today - timedelta(days=1)

existing_current_month = df_excel[(df_excel["Apartment"]==selected_apartment) & (df_excel["Month"]==first_day_month.month)]

if existing_current_month.empty:
    all_rows = []
    for apt_id in APARTMENTS[selected_apartment]:
        params = {
            "from": first_day_month.strftime("%Y-%m-%d"),
            "to": last_day_yesterday.strftime("%Y-%m-%d"),
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
            except:
                break
            bookings = data.get("bookings", [])
            if not bookings: break
            for b in bookings:
                arrival_dt = datetime.strptime(b.get("arrival"), "%Y-%m-%d")
                departure_dt = datetime.strptime(b.get("departure"), "%Y-%m-%d")
                platform = (b.get("channel") or {}).get("name") or "Direct booking"
                price = float(b.get("price") or 0)
                days = max((departure_dt - arrival_dt).days,0)
                if "expedia" in platform.lower(): price /= 0.82
                price_wo_tax = (price - APARTMENT_SETTINGS[selected_apartment]["summer_base"]*days)/1.13
                fee = price*0.15 if "airbnb" in platform.lower() else 0
                owner_profit = round(price_wo_tax - fee,2)
                all_rows.append({
                    "ID": b.get("id"),
                    "Apartment": selected_apartment,
                    "Guest Name": b.get("guestName") or b.get("guest-name"),
                    "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                    "Departure": departure_dt.strftime("%Y-%m-%d"),
                    "Days": days,
                    "Platform": platform,
                    "Total Price": round(price,2),
                    "Booking Fee": round(fee,2),
                    "Owner Profit": owner_profit,
                    "Month": arrival_dt.month
                })
            if data.get("page") and data.get("page") < data.get("page_count",1):
                params["page"] +=1
            else: break
    df_current = pd.DataFrame(all_rows)
    df_excel = pd.concat([df_excel, df_current], ignore_index=True)
    df_excel.to_excel(EXP_FILE, index=False)

# -------------------- Φιλτράρισμα --------------------
filtered_df = df_excel[df_excel["Apartment"]==selected_apartment].copy()
filtered_df = filtered_df.sort_values("Arrival")

# -------------------- Totals --------------------
total_price = filtered_df["Total Price"].sum()
total_owner_profit = filtered_df["Owner Profit"].sum()

col1, col2 = st.columns(2)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("📊 Κέρδος Ιδιοκτήτη", f"{total_owner_profit:.2f} €")

st.subheader(f"📅 Κρατήσεις ({selected_apartment})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)
