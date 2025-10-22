import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import requests
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# ---------------------- Ρυθμίσεις ----------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "YOUR_API_KEY"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"
EXP_FILE = "reservations.xlsx"

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

# ---------------------- Συναρτήσεις ----------------------
def compute_price_without_tax(price, nights, month, apt_name):
    settings = APARTMENT_SETTINGS.get(apt_name, {"winter_base": 2, "summer_base": 8})
    base = settings["winter_base"] if month in [11,12,1,2] else settings["summer_base"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform_name: str, price: float) -> float:
    p = platform_name.strip().lower()
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
    return round((price or 0)*rate, 2)

# ---------------------- Φόρτωση Excel ----------------------
try:
    df_excel = pd.read_excel(EXP_FILE)
except FileNotFoundError:
    df_excel = pd.DataFrame(columns=["ID","Apartment","Guest Name","Arrival","Departure",
                                     "Days","Platform","Total Price","Booking Fee",
                                     "Owner Profit","Month"])

# ---------------------- Sidebar επιλογής καταλύματος ----------------------
selected_apartment = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

# ---------------------- Προσδιορισμός τρέχοντος μήνα ----------------------
today = date.today()
first_day_month = today.replace(day=1)
last_day_yesterday = today - timedelta(days=1)

# ---------------------- Ελέγχουμε αν έχουμε ήδη τον τρέχοντα μήνα ----------------------
existing_current_month = df_excel[
    (df_excel["Apartment"]==selected_apartment) &
    (df_excel["Month"]==first_day_month.month)
]

if existing_current_month.empty:
    # ---------------------- Fetch API για τρέχοντα μήνα ----------------------
    all_rows = []
    for apt_id in APARTMENTS[selected_apartment]:
        params = {
            "from": first_day_month.strftime("%Y-%m-%d"),
            "to": last_day_yesterday.strftime("%Y-%m-%d"),
            "apartmentId": apt_id,
            "excludeBlocked": "true",
            "showCancellation": "true",
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
            if not bookings:
                break
            for b in bookings:
                arrival_dt = datetime.strptime(b.get("arrival"), "%Y-%m-%d")
                departure_dt = datetime.strptime(b.get("departure"), "%Y-%m-%d")
                platform = (b.get("channel") or {}).get("name") or "Direct booking"
                price = float(b.get("price") or 0)
                days = max((departure_dt - arrival_dt).days, 0)
                if "expedia" in platform.lower(): price /= 0.82
                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, selected_apartment)
                fee = compute_booking_fee(platform, price)
                settings = APARTMENT_SETTINGS.get(selected_apartment, {"airstay_commission":0.248})
                airstay_commission = round(price_wo_tax*settings["airstay_commission"],2)
                owner_profit = round(price_wo_tax - fee - airstay_commission, 2)
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
                params["page"] += 1
            else:
                break
    df_current = pd.DataFrame(all_rows)
    df_excel = pd.concat([df_excel, df_current], ignore_index=True)
    df_excel.to_excel(EXP_FILE, index=False)

# ---------------------- Εμφάνιση με AgGrid ----------------------
filtered_df = df_excel[df_excel["Apartment"]==selected_apartment]

st.subheader(f"📅 Κρατήσεις για {selected_apartment}")

gb = GridOptionsBuilder.from_dataframe(filtered_df)
gb.configure_default_column(editable=False, filter=True, sortable=True)
gb.configure_column("Month", header_name="Μήνας", type=["numericColumn"], filter="agNumberColumnFilter")
gb.configure_column("Apartment", header_name="Κατάλυμα", filter=True)
grid_options = gb.build()

grid_response = AgGrid(
    filtered_df,
    gridOptions=grid_options,
    height=500,
    enable_enterprise_modules=False,
    update_mode=GridUpdateMode.NO_UPDATE,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True
)

# ---------------------- Δυναμικά totals ----------------------
if 'data' in grid_response and len(grid_response['data']) > 0:
    df_filtered = pd.DataFrame(grid_response['data'])
    total_row = {
        "ID": "",
        "Apartment": "Σύνολα",
        "Guest Name": "",
        "Arrival": "",
        "Departure": "",
        "Days": df_filtered["Days"].sum(),
        "Platform": "",
        "Total Price": df_filtered["Total Price"].sum(),
        "Booking Fee": df_filtered["Booking Fee"].sum(),
        "Owner Profit": df_filtered["Owner Profit"].sum(),
        "Month": ""
    }
    st.markdown("---")
    st.write("**Σύνολα για τα φιλτραρισμένα δεδομένα:**")
    st.write(total_row)
