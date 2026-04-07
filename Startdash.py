import streamlit as st
import pandas as pd
import zipfile
import os
import io
from pathlib import Path
import numpy as np
import plotly.express as px


######################
###   Configuratie ###
######################

AIRPORTS_CSV_PATH = "airports-extended-clean.csv"
FLIGHTS_ZIP_PATH  = "case3_data.zip"

######################
###  Cache functies ###
######################

@st.cache_data(show_spinner="Airports laden...")
def load_airports(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", decimal=",", low_memory=False)

@st.cache_data(show_spinner="Vluchtdata uit ZIP laden...")
def load_flights_from_zip(zip_path: str) -> dict[str, pd.DataFrame]:
    flights: dict[str, pd.DataFrame] = {}

    NUMERIEKE_KOLOMMEN = [
        "Time (secs)",
        "[3d Latitude]",
        "[3d Longitude]",
        "[3d Altitude M]",
        "[3d Altitude Ft]",
        "[3d Heading]",
        "TRUE AIRSPEED (derived)",
    ]

    with zipfile.ZipFile(zip_path, "r") as z:
        all_files = [
            name for name in z.namelist()
            if not name.startswith("__MACOSX") and not name.endswith("/")
        ]

        excel_files = [f for f in all_files if f.endswith((".xlsx", ".xls"))]
        csv_files   = [f for f in all_files if f.endswith(".csv")]

        for name in excel_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df = pd.read_excel(buf)
                for col in NUMERIEKE_KOLOMMEN:
                    if col in df.columns:
                        df[col] = (
                            df[col].astype(str)
                            .str.replace(",", ".", regex=False)
                            .str.strip()
                        )
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                flights[Path(name).stem] = df

        for name in csv_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df = pd.read_csv(buf, low_memory=False)
                for col in NUMERIEKE_KOLOMMEN:
                    if col in df.columns:
                        df[col] = (
                            df[col].astype(str)
                            .str.replace(",", ".", regex=False)
                            .str.strip()
                        )
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                flights[Path(name).stem] = df

    return flights


######################
### Session state  ###
######################

def initialize_data() -> None:
    if "airports" not in st.session_state:
        if os.path.exists(AIRPORTS_CSV_PATH):
            st.session_state["airports"] = load_airports(AIRPORTS_CSV_PATH)
        else:
            st.warning(f"Bestand niet gevonden: `{AIRPORTS_CSV_PATH}`")
            st.session_state["airports"] = None

    if "flights" not in st.session_state:
        if os.path.exists(FLIGHTS_ZIP_PATH):
            st.session_state["flights"] = load_flights_from_zip(FLIGHTS_ZIP_PATH)
        else:
            st.warning(f"ZIP niet gevonden: `{FLIGHTS_ZIP_PATH}`")
            st.session_state["flights"] = {}


######################
###   Debugging    ###
######################

def show_data_debugger() -> None:
    st.divider()
    with st.expander("Data Debugger – geladen bestanden", expanded=True):
        st.caption("Overzicht van alle datasets in `st.session_state`")

        rows = []
        airports_df = st.session_state.get("airports")
        rows.append(_make_debug_row(
            bestand="airports-extended-clean.csv",
            bron="CSV",
            sleutel="airports",
            df=airports_df,
        ))

        flights: dict = st.session_state.get("flights", {})
        if flights:
            for naam, df in flights.items():
                rows.append(_make_debug_row(
                    bestand=naam,
                    bron="Excel/CSV (uit ZIP)",
                    sleutel=f'flights["{naam}"]',
                    df=df,
                ))
        else:
            rows.append({
                "Bestand"       : FLIGHTS_ZIP_PATH,
                "Bron"          : "ZIP",
                "session_state" : "flights",
                "Status"        : "Niet gevonden of leeg",
                "Rijen"         : "-",
                "Kolommen"      : "-",
                "Geheugen (MB)" : "-",
            })

        debug_df = pd.DataFrame(rows)
        st.dataframe(
            debug_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status"        : st.column_config.TextColumn(width="small"),
                "Geheugen (MB)" : st.column_config.TextColumn(width="small"),
                "session_state" : st.column_config.TextColumn(width="medium"),
            },
        )

        st.markdown("**Cache-status:**")
        col1, col2 = st.columns(2)
        col1.metric("airports cache", "Actief" if airports_df is not None else "Leeg")
        col2.metric("flights cache", f"{len(flights)} dataset(s)" if flights else "Leeg")

        st.markdown("**Kolomnamen per dataset:**")
        if airports_df is not None:
            with st.expander("airports (airports-extended-clean.csv)"):
                st.write(list(airports_df.columns))

        for naam, df in flights.items():
            with st.expander(f'flights["{naam}"]'):
                col1, col2 = st.columns(2)
                col1.write(list(df.columns))
                col2.dataframe(df.head(3), use_container_width=True)


def _make_debug_row(bestand: str, bron: str, sleutel: str, df) -> dict:
    if df is not None:
        return {
            "Bestand"       : bestand,
            "Bron"          : bron,
            "session_state" : sleutel,
            "Status"        : "Geladen",
            "Rijen"         : f"{len(df):,}",
            "Kolommen"      : len(df.columns),
            "Geheugen (MB)" : f"{df.memory_usage(deep=True).sum() / 1e6:.2f}",
        }
    return {
        "Bestand"       : bestand,
        "Bron"          : bron,
        "session_state" : sleutel,
        "Status"        : "Niet gevonden",
        "Rijen"         : "-",
        "Kolommen"      : "-",
        "Geheugen (MB)" : "-",
    }


######################
###   CO2 config   ###
######################

LAT_HOME = 47.4647
LON_HOME  = 8.5492

CO2_FACTORS = {
    'A319': 5.5,
    'A320': 6.0,
    'A321': 6.5,
    'A21N': 5.5,
    'B763': 15.0,
    'A359': 18.0,
}
RADIATIVE_FORCING_INDEX = 2.0


######################
###   Hulpfuncties ###
######################

def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


######################
###   Pagina       ###
######################

st.set_page_config(page_title="Vluchtactiviteit & Klimaat", layout="wide")

# Data laden vanuit session_state
initialize_data()

df_airports  = st.session_state.get("airports")
flights_dict = st.session_state.get("flights", {})

# Zoek de schedule in de geladen ZIP-bestanden
SCHEDULE_KEY = "schedule_airport.csv"   # pas aan als de bestandsnaam anders is

if SCHEDULE_KEY not in flights_dict:
    st.error(
        f"Bestand `{SCHEDULE_KEY}` niet gevonden in de ZIP. "
        f"Beschikbare sleutels: {list(flights_dict.keys())}"
    )
    st.stop()

df_schedule = flights_dict[SCHEDULE_KEY].copy()

# Datum kolom aanmaken
if "STD" in df_schedule.columns:
    df_schedule["Datum"] = pd.to_datetime(df_schedule["STD"], dayfirst=True).dt.date
else:
    st.error("Kolom 'STD' niet gevonden in schedule data.")
    st.stop()

if df_airports is None:
    st.error("Airports data niet beschikbaar.")
    st.stop()

# --- SIDEBAR & TIJDFILTER ---
st.sidebar.header("⚙️ Filters")

min_datum = df_schedule["Datum"].min()
max_datum = df_schedule["Datum"].max()

geselecteerde_periode = st.sidebar.slider(
    "Selecteer Periode",
    min_value=min_datum,
    max_value=max_datum,
    value=(min_datum, max_datum),
    format="DD-MM-YYYY",
)

mask = (df_schedule["Datum"] >= geselecteerde_periode[0]) & (df_schedule["Datum"] <= geselecteerde_periode[1])
df_schedule_filtered = df_schedule[mask]

if df_schedule_filtered.empty:
    st.warning("Er zijn geen vluchten gevonden in de geselecteerde periode.")
    st.stop()

# --- DATA VOORBEREIDEN ---
flight_counts = (
    df_schedule_filtered.groupby("Org/Des")
    .size()
    .reset_index(name="Aantal_Vluchten")
)

act_per_airport = (
    df_schedule_filtered.groupby("Org/Des")["ACT"]
    .agg(lambda x: x.value_counts().index[0])
    .reset_index()
)

df_map = pd.merge(df_airports, flight_counts, left_on="ICAO", right_on="Org/Des", how="inner")
df_map = pd.merge(df_map, act_per_airport, left_on="ICAO", right_on="Org/Des", how="left")

# --- CO2 & AFSTAND ---
df_map["Distance_km"]                  = haversine_vectorized(LAT_HOME, LON_HOME, df_map["Latitude"], df_map["Longitude"])
df_map["CO2_Factor"]                   = df_map["ACT"].map(CO2_FACTORS).fillna(7.0)
df_map["CO2_Emission_kg"]              = df_map["Distance_km"] * df_map["CO2_Factor"]
df_map["Climate_Impact_CO2e_kg"]       = df_map["CO2_Emission_kg"] * RADIATIVE_FORCING_INDEX
df_map["Total_Climate_Impact_CO2e_Ton"] = (df_map["Climate_Impact_CO2e_kg"] * df_map["Aantal_Vluchten"]) / 1000

# --- DASHBOARD UI ---
st.title("🌍 Wereldwijde Vluchtactiviteit & Klimaatimpact")
st.write(
    f"Elke dag landen en vertrekken er duizenden vliegtuigen. Hierachter zit een wereld van data. "
    f"In dit dashboard is twee jaar vliegdata van Zürich weergegeven. "
    f"In dit dashboard zie je gegevens voor de periode: "
    f"**{geselecteerde_periode[0].strftime('%d-%m-%Y')} tot {geselecteerde_periode[1].strftime('%d-%m-%Y')}**"
)

# --- 1. BUBBEL DIAGRAM ---
st.header("1. Wereldwijde Vluchtactiviteit")
fig_bubbles = px.scatter_geo(
    df_map, lat="Latitude", lon="Longitude", size="Aantal_Vluchten",
    hover_name="Name", color="Aantal_Vluchten", color_continuous_scale="Plasma",
    projection="natural earth", labels={"Aantal_Vluchten": "Aantal Vluchten"},
)
st.plotly_chart(fig_bubbles, use_container_width=True)

st.divider()

# --- 2. TOP 10 DRUKSTE LUCHTHAVENS ---
st.header("2. Top 10 Drukste Luchthavens")
top_10_hubs = df_map.nlargest(10, "Aantal_Vluchten")

fig_bar = px.bar(
    top_10_hubs, x="Aantal_Vluchten", y="Name", orientation="h",
    color="Aantal_Vluchten", color_continuous_scale="Viridis",
    labels={"Name": "Luchthaven", "Aantal_Vluchten": "Totaal aantal vluchten"},
)
fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# --- 3. KLIMAATIMPACT ---
st.header("🌱 3. Klimaatimpact Analyse (CO2e)")
st.write("Overzicht van de uitstoot per route, meegerekend dat effecten op grote hoogte de impact verdubbelen (Radiative Forcing).")

totale_uitstoot    = df_map["Total_Climate_Impact_CO2e_Ton"].sum()
gemiddelde_vlucht  = df_map["Climate_Impact_CO2e_kg"].mean()
bomen_nodig        = (totale_uitstoot * 1000) / 20

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Totale Netwerk Uitstoot (Ton)", f"{totale_uitstoot:,.0f}".replace(",", "."))
with col2:
    st.metric("Gem. uitstoot enkele vlucht (Kg)", f"{gemiddelde_vlucht:,.0f}".replace(",", "."))
with col3:
    st.metric("Bomen nodig voor compensatie", f"{bomen_nodig:,.0f}".replace(",", "."))

st.write("")

st.subheader("Top 10 Routes (Totale Uitstoot)")
top_10_co2 = df_map.nlargest(10, "Total_Climate_Impact_CO2e_Ton")

fig_co2_bar = px.bar(
    top_10_co2, x="Total_Climate_Impact_CO2e_Ton", y="Name", orientation="h",
    color="Total_Climate_Impact_CO2e_Ton", color_continuous_scale="Reds",
    labels={"Name": "Luchthaven", "Total_Climate_Impact_CO2e_Ton": "CO2e (Ton)"},
)
fig_co2_bar.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_co2_bar, use_container_width=True)
