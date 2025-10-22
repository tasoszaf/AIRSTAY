import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import requests
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# ---------------------- ΡΥΘΜΙΣΕΙΣ ----------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# ---------------------- Καταλύματα & Ρυθμίσεις ----------------------
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
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,2715218,2715223,2715228,2715233,2715238,2715273]
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

# ---------------------- Συναρτήσεις ----------------------
def compute_price_without_tax(price, nights, month, apt_name):
    settings = APARTMENT_SETTINGS.get(apt_name, {"winter_base": 2, "summer_base": 8})
    base = settings["winter_base"] if month in [11,12,1,2] else settings["summer_base"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform_name: str, price: float) -> float:
    p = platform_name.strip().lower() if platform_name else ''
    if p in {"website","direct","direct booking","direct-booking","site","web"}:
        rate = 0.0
    elif "booking" in p:
        rate = 0.17
    elif "airbnb" in p:
        rate = 0.15
    elif "expedia" in p:
        rate = 0.18
    else:
        rate = 0.0
    return round((price or 0) * rate, 2)

# ---------------------- Fetch κρατήσεων ----------------------
@st.cache_data(ttl=3600)
def fetch_all_reservations():
    all_rows = []
    from_date = "2025-01-01"
    to_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    for apt_name, id_list in APARTMENTS.items():
        for apt_id in id_list:
            params = {"from": from_date, "to": to_date,
                      "apartmentId": apt_id, "excludeBlocked": "true",
                      "showCancellation": "true", "page": 1, "pageSize": 100}
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
                    arrival = b.get("arrival")
                    departure = b.get("departure")
                    if not arrival or not departure: continue
                    arrival_dt = datetime.strptime(arrival, "%Y-%m-%d")
                    departure_dt = datetime.strptime(departure, "%Y-%m-%d")
                    if arrival_dt.date() > date.today() - timedelta(days=1): continue
                    platform = (b.get("channel") or {}).get("name") or "Direct booking"
                    price = float(b.get("price") or 0)
                    days = max((departure_dt - arrival_dt).days, 0)
                    if "expedia" in platform.lower(): price /= 0.82
                    price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, apt_name)
                    fee = compute_booking_fee(platform, price)
                    settings = APARTMENT_SETTINGS.get(apt_name, {"airstay_commission":0.248})
                    airstay_commission = round(price_wo_tax*settings["airstay_commission"],2)
                    owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

                    all_rows.append({
                        "ID": b.get("id"),
                        "Apartment": apt_name,
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
                    params["page"] += 1
                else: break
    return pd.DataFrame(all_rows).drop_duplicates(subset=["ID"])

# ---------------------- Φόρτωση δεδομένων ----------------------
df_all = fetch_all_reservations()

# ---------------------- Sidebar & φίλτρα ----------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
apartment_options = ["Όλα"] + list(APARTMENTS.keys())
selected_apartment = st.sidebar.selectbox("Κατάλυμα", apartment_options)

month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in range(1,13)]
selected_month = st.sidebar.selectbox("📅 Επιλογή Μήνα", month_options)

filtered_df = df_all.copy()
if selected_apartment != "Όλα":
    filtered_df = filtered_df[filtered_df["Apartment"]==selected_apartment]
if selected_month != "Όλοι οι μήνες":
    month_idx = [k for k,v in months_el.items() if v==selected_month][0]
    filtered_df = filtered_df[filtered_df["Month"]==month_idx]

# ---------------------- Υπολογισμός totals για pinned row ----------------------
total_row = {
    "ID": "",
    "Apartment": "Σύνολα",
    "Guest Name": "",
    "Arrival": "",
    "Departure": "",
    "Days": filtered_df["Days"].sum(),
    "Platform": "",
    "Total Price": filtered_df["Total Price"].sum(),
    "Booking Fee": filtered_df["Booking Fee"].sum(),
    "Owner Profit": filtered_df["Owner Profit"].sum(),
    "Month": ""
}

# ---------------------- AgGrid ----------------------
st.subheader(f"📅 Κρατήσεις ({selected_apartment} – {selected_month})")
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

gb = GridOptionsBuilder.from_dataframe(filtered_df)
gb.configure_default_column(editable=False, filter=True, sortable=True)
gb.configure_column("Month", header_name="Μήνας")
grid_options = gb.build()

AgGrid(
    filtered_df,
    gridOptions=grid_options,
    height=500,
    enable_enterprise_modules=False,
    update_mode=GridUpdateMode.NO_UPDATE,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    fit_columns_on_grid_load=True,
    pinnedBottomRowData=[total_row]
)
