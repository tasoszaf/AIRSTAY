import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime, date, timedelta

# -------------------------------------------------------------
# Streamlit setup
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
HEADERS = {"Api-Key": API_KEY, "Content-Type": "application/json"}
RES_URL = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# Apartments & Settings
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

SETTINGS = {
    "ZED": {"winter":0.5,"summer":2,"commission":0},
    "NAMI":{"winter":4,"summer":15,"commission":0},
    "THRESH":{"winter":0.5,"summer":2,"commission":0.248},
    "KALISTA":{"winter":2,"summer":8,"commission":0.248},
    "KOMOS":{"winter":0.5,"summer":2,"commission":0},
    "CHELI":{"winter":0.5,"summer":2,"commission":0},
    "AKALI":{"winter":2,"summer":8,"commission":0},
    "ZILEAN":{"winter":0.5,"summer":2,"commission":0.248},
    "NAUTILUS":{"winter":0.5,"summer":2,"commission":0.186},
    "ANIVIA":{"winter":2,"summer":8,"commission":0.248},
    "ELISE":{"winter":2,"summer":8,"commission":0.248},
    "ORIANNA":{"winter":2,"summer":8,"commission":0.248},
    "JAAX":{"winter":2,"summer":8,"commission":0},
    "FINIKAS":{"winter":0.5,"summer":2,"commission":0}
}

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------
def compute_price_wo_tax(price, nights, month, apt):
    s = SETTINGS.get(apt, {"winter":2,"summer":8})
    base = s["winter"] if month in [11,12,1,2] else s["summer"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform, price):
    if not platform:
        return 0
    p = platform.lower()
    if "booking" in p: rate=0.17
    elif "airbnb" in p: rate=0.15
    elif "expedia" in p: rate=0.18
    else: rate=0
    return round(price * rate,2)

def fetch_reservations(from_date, to_date):
    """Fetch reservations from Smoobu API"""
    all_rows=[]
    for apt_name, apt_ids in APARTMENTS.items():
        for apt_id in apt_ids:
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
                    r = requests.get(RES_URL, headers=HEADERS, params=params, timeout=20)
                    r.raise_for_status()
                    data = r.json()
                except requests.exceptions.RequestException:
                    break

                bookings = data.get("bookings", [])
                if not bookings:
                    break
                for b in bookings:
                    arrival = b.get("arrival")
                    departure = b.get("departure")
                    if not arrival or not departure:
                        continue
                    arr_dt = datetime.strptime(arrival, "%Y-%m-%d")
                    dep_dt = datetime.strptime(departure, "%Y-%m-%d")
                    if arr_dt.year != 2025:
                        continue

                    platform = (b.get("channel") or {}).get("name") or "Direct"
                    price = float(b.get("price") or 0)
                    days = (dep_dt - arr_dt).days
                    if "expedia" in platform.lower():
                        price /= 0.82

                    fee = compute_booking_fee(platform, price)
                    price_wo_tax = compute_price_wo_tax(price, days, arr_dt.month, apt_name)
                    comm = SETTINGS.get(apt_name, {}).get("commission", 0)
                    air_comm = round(price_wo_tax * comm, 2)
                    profit = round(price_wo_tax - fee - air_comm, 2)

                    all_rows.append({
                        "ID": b.get("id"),
                        "Apartment": apt_name,
                        "Guest Name": b.get("guestName") or "",
                        "Arrival": arr_dt.strftime("%Y-%m-%d"),
                        "Departure": dep_dt.strftime("%Y-%m-%d"),
                        "Days": days,
                        "Platform": platform,
                        "Total Price": round(price,2),
                        "Booking Fee": fee,
                        "Price Without Tax": price_wo_tax,
                        "Airstay Commission": air_comm,
                        "Owner Profit": profit,
                        "Month": arr_dt.month
                    })

                if data.get("page") and data["page"] < data.get("page_count", 1):
                    params["page"] += 1
                else:
                    break
    return pd.DataFrame(all_rows)

# -------------------------------------------------------------
# Cache logic
# -------------------------------------------------------------
CACHE_FILE = "reservations_cache.xlsx"
today = date.today()
first_day_year = date(today.year, 1, 1)
yesterday = today - timedelta(days=1)
current_month_start = today.replace(day=1)

if not os.path.exists(CACHE_FILE):
    st.warning("📡 Πρώτη εκτέλεση: λήψη όλων των κρατήσεων έως και χθες...")
    df_cache = fetch_reservations(first_day_year.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
    df_cache.to_excel(CACHE_FILE, index=False)
    st.success(f"💾 Αποθηκεύτηκαν {len(df_cache)} κρατήσεις στο Excel (μέχρι {yesterday}).")
else:
    st.info("✅ Διαβάζονται οι κρατήσεις από το Excel...")
    df_cache = pd.read_excel(CACHE_FILE)

    # Λήψη μόνο για τον τρέχοντα μήνα
    new_df = fetch_reservations(current_month_start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))

    # Συγχώνευση
    df = pd.concat([df_cache, new_df], ignore_index=True).drop_duplicates(subset=["ID"])
    df.to_excel(CACHE_FILE, index=False)
    st.success(f"🔄 Ενημερώθηκαν κρατήσεις. Σύνολο: {len(df)}")

    df_cache = df

# -------------------------------------------------------------
# Streamlit UI
# -------------------------------------------------------------
st.sidebar.header("🏠 Κατάλυμα")
selected = st.sidebar.selectbox("Επιλογή", list(APARTMENTS.keys()))
filtered = df_cache[df_cache["Apartment"]==selected].sort_values("Arrival")

month_names = {
    1:"Ιαν",2:"Φεβ",3:"Μαρ",4:"Απρ",5:"Μαι",6:"Ιουν",
    7:"Ιουλ",8:"Αυγ",9:"Σεπ",10:"Οκτ",11:"Νοε",12:"Δεκ"
}
month_opts = ["Όλοι"]+[month_names[m] for m in range(1,13)]
sel_month = st.selectbox("📅 Μήνας", month_opts)

if sel_month!="Όλοι":
    m_idx=[k for k,v in month_names.items() if v==sel_month][0]
    filtered=filtered[filtered["Month"]==m_idx]

col1,col2=st.columns(2)
col1.metric("💰 Σύνολο Τιμής", f"{filtered['Total Price'].sum():.2f} €")
col2.metric("📊 Κέρδος Ιδιοκτήτη", f"{filtered['Owner Profit'].sum():.2f} €")

st.dataframe(filtered, use_container_width=True, hide_index=True)
