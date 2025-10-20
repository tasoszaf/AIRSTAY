import pickle
from pathlib import Path

# -------------------------------------------------------------
# 🧭 Επιλογή Ομάδας (sidebar)
# -------------------------------------------------------------
st.sidebar.header("🏘️ Επιλογή Ομάδας Καταλυμάτων")
selected_group = st.sidebar.selectbox("Διάλεξε ομάδα", list(groups.keys()))
apartment_ids = groups[selected_group]

# -------------------------------------------------------------
# 📅 Δημιουργία λίστας μηνών για 2025
# -------------------------------------------------------------
def month_ranges(year: int):
    ranges = []
    for month in range(1, 13):
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        ranges.append((start, end))
    return ranges

year = 2025
month_periods = month_ranges(year)

# -------------------------------------------------------------
# 💾 Cache setup
# -------------------------------------------------------------
CACHE_DIR = Path("smoobu_cache")
CACHE_DIR.mkdir(exist_ok=True)

def cache_file(group: str, year: int, month: int) -> Path:
    return CACHE_DIR / f"{group}_{year}_{month:02d}.pkl"

def load_cached_bookings(group: str, year: int, month: int):
    path = cache_file(group, year, month)
    if path.exists():
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None

def save_cached_bookings(group: str, year: int, month: int, data):
    path = cache_file(group, year, month)
    with open(path, "wb") as f:
        pickle.dump(data, f)

# -------------------------------------------------------------
# 📦 Ανάκτηση κρατήσεων (με caching μόνο για παρελθόντες μήνες)
# -------------------------------------------------------------
today = date.today()
all_bookings = []
progress = st.progress(0)
step = 0
total_steps = len(apartment_ids) * len(month_periods)

for apt_id in apartment_ids:
    for (from_dt, to_dt) in month_periods:
        # Αν ο μήνας είναι μελλοντικός → τον αγνοούμε τελείως
        if to_dt > today:
            step += 1
            progress.progress(step / total_steps)
            continue

        # Αν ο μήνας έχει παρέλθει → δοκίμασε να φορτώσεις cache
        use_cache = to_dt < date(today.year, today.month, 1)
        cached = load_cached_bookings(selected_group, year, from_dt.month) if use_cache else None

        if cached is not None:
            all_bookings.extend(cached)
            step += 1
            progress.progress(step / total_steps)
            continue

        # Διαφορετικά, κάνε API call
        params = {
            "from": from_dt.strftime("%Y-%m-%d"),
            "to": to_dt.strftime("%Y-%m-%d"),
            "apartmentId": apt_id,
            "excludeBlocked": "true",
            "showCancellation": "true",
            "page": 1,
            "pageSize": 100,
        }

        month_bookings = []
        while True:
            try:
                r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Σφάλμα ({apt_id}, {from_dt:%b}): {e}")
                break

            bookings = data.get("bookings", [])
            if not bookings:
                break
            month_bookings.extend(bookings)

            if data.get("page") and data.get("page") < data.get("page_count", 1):
                params["page"] += 1
            else:
                break

        all_bookings.extend(month_bookings)
        # Αν ο μήνας έχει ολοκληρωθεί, αποθήκευσέ τον στο cache
        if use_cache:
            save_cached_bookings(selected_group, year, from_dt.month, month_bookings)

        step += 1
        progress.progress(step / total_steps)

progress.empty()
st.success(f"✅ Φορτώθηκαν {len(all_bookings)} κρατήσεις για την ομάδα: {selected_group}")
