import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os

# ======================
# ΡΥΘΜΙΣΕΙΣ ΚΑΤΑΛΥΜΑΤΩΝ
# ======================

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

API_URL = "https://login.smoobu.com/api/reservations"
API_TOKEN = st.secrets["SMOOBU_TOKEN"] if "SMOOBU_TOKEN" in st.secrets else os.getenv("SMOOBU_TOKEN")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

RESERVATIONS_FILE = "reservations-21.xlsx"

# ======================
# ΑΝΑΚΤΗΣΗ ΚΡΑΤΗΣΕΩΝ
# ======================
def fetch_reservations():
    st.info("🔄 Γίνεται ανάκτηση κρατήσεων από Smoobu...")
    response = requests.get(API_URL, headers=HEADERS)
    if response.status_code != 200:
        st.error("Σφάλμα API: " + str(response.status_code))
        return pd.DataFrame()

    data = response.json()
    bookings = data.get("bookings", data)

    all_rows = []

    for b in bookings:
        try:
            # Πραγματικό Apartment ID
            apt_real_id = b.get("apartment", {}).get("id")
            if not apt_real_id:
                continue

            # Εύρεση group βάσει apartment.id
            apt_name = None
            for name, ids in APARTMENTS.items():
                if apt_real_id in ids:
                    apt_name = name
                    break
            if not apt_name:
                continue  # δεν ανήκει σε κάποιο γνωστό group

            # Ανάκτηση δεδομένων
            arrival_dt = datetime.fromisoformat(b.get("arrival")[:10])
            departure_dt = datetime.fromisoformat(b.get("departure")[:10])
            days = (departure_dt - arrival_dt).days
            price = float(b.get("price", 0))
            fee = float(b.get("cleaningFee", 0))
            guests = b.get("guests", 0)
            platform = b.get("channel", {}).get("name", "Unknown")

            settings = APARTMENT_SETTINGS[apt_name]
            commission = settings["airstay_commission"]

            price_wo_tax = price / 1.13
            airstay_commission = price_wo_tax * commission
            owner_profit = price_wo_tax - airstay_commission

            all_rows.append({
                "ID": b.get("id"),
                "Apartment": apt_name,
                "Apartment ID": apt_real_id,
                "Guest Name": b.get("guestName"),
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
        except Exception as e:
            st.warning(f"⚠️ Σφάλμα σε κράτηση: {e}")
            continue

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df.to_excel(RESERVATIONS_FILE, index=False)
        st.success(f"✅ Ενημερώθηκαν {len(df)} κρατήσεις.")
    else:
        st.warning("Δεν βρέθηκαν κρατήσεις.")

    return df


# ======================
# ΕΜΦΑΝΙΣΗ DASHBOARD
# ======================
def show_dashboard(df):
    st.header("📊 Αναφορές Κρατήσεων")
    selected_apartment = st.sidebar.selectbox("Επίλεξε Κατάλυμα", list(APARTMENTS.keys()))

    filtered_df = df[df["Apartment"] == selected_apartment]
    st.write(f"Σύνολο κρατήσεων: {len(filtered_df)}")

    if filtered_df.empty:
        st.info("Δεν υπάρχουν κρατήσεις για αυτό το κατάλυμα.")
        return

    st.dataframe(filtered_df, width="stretch", hide_index=True)

    total_profit = filtered_df["Owner Profit"].sum()
    st.metric("Σύνολο Κερδών Ιδιοκτήτη (€)", f"{total_profit:,.2f}")


# ======================
# STREAMLIT MAIN
# ======================
st.title("🏨 Σύστημα Κρατήσεων")

if st.button("🔄 Ανάκτηση Νέων Κρατήσεων"):
    df = fetch_reservations()
else:
    if os.path.exists(RESERVATIONS_FILE):
        df = pd.read_excel(RESERVATIONS_FILE)
    else:
        st.warning("Δεν υπάρχει αρχείο κρατήσεων. Πάτησε 'Ανάκτηση Νέων Κρατήσεων'.")
        df = pd.DataFrame()

if not df.empty:
    show_dashboard(df)
