import streamlit as st
import pandas as pd
import zipfile
import os
import io
from pathlib import Path
import numpy as np
import plotly.express as px

#startdash
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
SCHEDULE_KEY = "schedule_airport"   # pas aan als de bestandsnaam anders is

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

# --- DASHBOARD UI (STARTDASH) ---
st.title("✈️ Zürich Global Connect: Operations & Performance")

# Introductie tekst ---
with st.container():
    st.markdown("""
    ### Welkom bij het Airport Insights Dashboard
    Op deze pagina krijgt u een overzicht van de wereldwijde vluchtactiviteit en de operationele bezetting van de luchthavens. 
    De data biedt inzicht in waar de meeste vluchten vandaan komen, welke hubs het drukst zijn en hoe de volumes zich over de tijd verdelen.

    **Diepere Analyse**
    Wilt u meer weten over specifieke onderwerpen zoals vertragingen, vlootdetails of klimaatimpact? 
    Gebruik de navigatie om naar de andere pagina's te gaan. Daar wordt per onderwerp een diepere analyse uitgevoerd met gedetailleerde statistieken.
    """)

    st.write(
        f"In dit overzicht zie je gegevens voor de geselecteerde periode: "
        f"**{geselecteerde_periode[0].strftime('%d-%m-%Y')} tot {geselecteerde_periode[1].strftime('%d-%m-%Y')}**"
    )
st.divider()


display_df = df[df['Country'].isin(selected_country)]

    
# Key Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Totaal aantal vluchten", len(display_df))
with col2:
    avg_delay = display_df[display_df['Delay_min'] > 0]['Delay_min'].mean()
    st.metric("Gem. Vertraging", f"{avg_delay:.1f} min")
with col3:
    st.metric("Unieke Bestemmingen", display_df['Org/Des'].nunique())
with col4:
    most_common_ac = display_df['ACT'].mode()[0]
    st.metric("Meest gebruikt toestel", most_common_ac)

st.divider()
# --- BUBBEL DIAGRAM ---
st.header("Wereldwijde Vluchtactiviteit")
fig_bubbles = px.scatter_geo(
    df_map, lat="Latitude", lon="Longitude", size="Aantal_Vluchten",
    hover_name="Name", color="Aantal_Vluchten", color_continuous_scale="Plasma",
    projection="natural earth", labels={"Aantal_Vluchten": "Aantal Vluchten"},
)
st.plotly_chart(fig_bubbles, use_container_width=True)

# ---Vlucht volume  ---
st.subheader("Vluchtvolume per Maand")
# We gebruiken de gefilterde schedule data voor de tijdlijn
df_schedule_filtered['Month_str'] = pd.to_datetime(df_schedule_filtered['STD'], dayfirst=True).dt.to_period('M').astype(str)
monthly_counts = df_schedule_filtered.groupby('Month_str').size().reset_index(name='Vluchten')

fig_vol_line = px.line(
    monthly_counts, x='Month_str', y='Vluchten', 
    markers=True, 
    labels={'Month_str': 'Maand', 'Vluchten': 'Aantal vluchten'},
    color_discrete_sequence=['teal']
)
st.plotly_chart(fig_vol_line, use_container_width=True)

st.divider()

# --- TOP 10 DRUKSTE LUCHTHAVENS ---
st.header("Top 10 Drukste Luchthavens")
top_10_hubs = df_map.nlargest(10, "Aantal_Vluchten")

fig_bar = px.bar(
    top_10_hubs, x="Aantal_Vluchten", y="Name", orientation="h",
    color="Aantal_Vluchten", color_continuous_scale="Viridis",
    labels={"Name": "Luchthaven", "Aantal_Vluchten": "Totaal aantal vluchten"},
)
fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_bar, use_container_width=True)


