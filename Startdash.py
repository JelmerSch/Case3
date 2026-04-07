import streamlit as st
import pandas as pd
import zipfile
import os
import io
from pathlib import Path
import datetime
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
# @st.cache_data slaat het resultaat op in geheugen op serverniveau.
# De functie wordt maar EEN KEER uitgevoerd, daarna wordt de cache teruggegeven.
# Dit werkt ook over pagina's heen, want de cache leeft buiten session_state.

@st.cache_data(show_spinner="Airports laden...")
def load_airports(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", decimal=",", low_memory=False)

@st.cache_data(show_spinner="Vluchtdata uit ZIP laden...")
def load_flights_from_zip(zip_path: str) -> dict[str, pd.DataFrame]:
    flights: dict[str, pd.DataFrame] = {}

    # Kolommen die numeriek moeten zijn
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
        csv_files = [f for f in all_files if f.endswith(".csv")]

        for name in excel_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df = pd.read_excel(buf)

                # Komma → punt voor alle numerieke kolommen
                for col in NUMERIEKE_KOLOMMEN:
                    if col in df.columns:
                        df[col] = (
                            df[col]
                            .astype(str)
                            .str.replace(",", ".", regex=False)
                            .str.strip()
                        )
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                key = Path(name).stem
                flights[key] = df

        for name in csv_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df = pd.read_csv(buf, low_memory=False)

                for col in NUMERIEKE_KOLOMMEN:
                    if col in df.columns:
                        df[col] = (
                            df[col]
                            .astype(str)
                            .str.replace(",", ".", regex=False)
                            .str.strip()
                        )
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                key = Path(name).stem
                flights[key] = df

    return flights


######################
### Session state  ###
######################
# session_state zorgt ervoor dat de data beschikbaar is op ALLE pagina's
# voor DEZE gebruiker/sessie. We vullen het maar één keer (if ... not in ...).
# De zware laadtaak delegeren we aan de gecachede functies hierboven,
# zodat meerdere gebruikers dezelfde cache delen.

def initialize_data() -> None:
    """
    Zet airports en flights in session_state als ze er nog niet in zitten.
    Roep deze functie aan bovenaan elke pagina:

        from Startdash import initialize_data
        initialize_data()
    """
    # --- Airports ---
    if "airports" not in st.session_state:
        if os.path.exists(AIRPORTS_CSV_PATH):
            # load_airports() is gecached; geen dubbel leeswerk
            st.session_state["airports"] = load_airports(AIRPORTS_CSV_PATH)
        else:
            st.warning(f"Bestand niet gevonden: `{AIRPORTS_CSV_PATH}`")
            st.session_state["airports"] = None

    # --- Flights ---
    if "flights" not in st.session_state:
        if os.path.exists(FLIGHTS_ZIP_PATH):
            # load_flights_from_zip() is gecached; geen dubbel leeswerk
            st.session_state["flights"] = load_flights_from_zip(FLIGHTS_ZIP_PATH)
        else:
            st.warning(f"ZIP niet gevonden: `{FLIGHTS_ZIP_PATH}`")
            st.session_state["flights"] = {}


######################
###   Debugging    ###
######################

def show_data_debugger() -> None:
    """
    Toon een overzicht van alle geladen datasets.
    Handig om te controleren of de data correct is ingeladen.
    """
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

        # Cache-status tonen
        st.markdown("**Cache-status:**")
        col1, col2 = st.columns(2)
        col1.metric(
            "airports cache",
            "Actief" if airports_df is not None else "Leeg",
        )
        col2.metric(
            "flights cache",
            f"{len(flights)} dataset(s)" if flights else "Leeg",
        )

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


st.set_page_config(page_title="Vluchtactiviteit & Klimaat", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# --- 1. DATA INLADEN ---
@st.cache_data
def load_data():
    df_airports = pd.read_csv(os.path.join(BASE_DIR, 'airports-extended-clean.csv'), sep=';', decimal=',')
    
    # Let op: index_col=0 is hier weggehaald!
    df_schedule = pd.read_csv(
        os.path.join(BASE_DIR, 'schedule_airport.csv'),
        sep=',',
        encoding='utf-8-sig'  
    )
    
    # Nu kan Pandas de kolom 'STD' wel gewoon vinden
    df_schedule['Datum'] = pd.to_datetime(df_schedule['STD'], dayfirst=True).dt.date
    
    return df_airports, df_schedule


df_airports, df_schedule = load_data()

# --- 2. CO2 CONFIGURATIE ---
LAT_HOME = 47.4647
LON_HOME = 8.5492

co2_factors = {
    'A319': 5.5,
    'A320': 6.0,
    'A321': 6.5,
    'A21N': 5.5,
    'B763': 15.0,
    'A359': 18.0,
}
RADIATIVE_FORCING_INDEX = 2.0

# --- 3. SIDEBAR & TIJDFILTER ---
st.sidebar.header("⚙️ Filters")

min_datum = df_schedule['Datum'].min()
max_datum = df_schedule['Datum'].max()

geselecteerde_periode = st.sidebar.slider(
    "Selecteer Periode",
    min_value=min_datum,
    max_value=max_datum,
    value=(min_datum, max_datum),
    format="DD-MM-YYYY"
)

# Filter de schedule data op basis van de slider
mask = (df_schedule['Datum'] >= geselecteerde_periode[0]) & (df_schedule['Datum'] <= geselecteerde_periode[1])
df_schedule_filtered = df_schedule[mask]


# --- 4. DATA VOORBEREIDEN (Gefilterd) ---
if df_schedule_filtered.empty:
    st.warning("Er zijn geen vluchten gevonden in deze geselecteerde periode.")
    st.stop() # Stop met renderen als er geen data is

# Tel het aantal vluchten per luchthaven (nu gebaseerd op de gefilterde data)
flight_counts = df_schedule_filtered.groupby('Org/Des').size().reset_index(name='Aantal_Vluchten')

# Haal het meest voorkomende vliegtuigtype per luchthaven op
act_per_airport = (
    df_schedule_filtered.groupby('Org/Des')['ACT']
    .agg(lambda x: x.value_counts().index[0])
    .reset_index()
)

# Maak df_map aan
df_map = pd.merge(df_airports, flight_counts, left_on='ICAO', right_on='Org/Des', how='inner')
df_map = pd.merge(df_map, act_per_airport, left_on='ICAO', right_on='Org/Des', how='left')


