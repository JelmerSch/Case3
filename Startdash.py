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

# Data laden
df = load_data()

# --- STREAMLIT UI ---
st.title("✈️ Airport Operations & Insights Dashboard")
st.markdown("Dit dashboard geeft inzicht in vluchtvolumes, bestemmingen en vertragingen op basis van de verstrekte data.")

# Sidebar filters
st.sidebar.header("Filters")
selected_country = st.sidebar.multiselect("Selecteer Landen", options=df['Country'].unique(), default=None)

if selected_country:
    display_df = df[df['Country'].isin(selected_country)]
else:
    display_df = df

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

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Volumes", "⏰ Vertragingen", "🛩️ Vloot & Bestemmingen"])

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


# --- 5. CO2 & AFSTAND BEREKENEN ---
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

df_map['Distance_km'] = haversine_vectorized(LAT_HOME, LON_HOME, df_map['Latitude'], df_map['Longitude'])
df_map['CO2_Factor'] = df_map['ACT'].map(co2_factors).fillna(7.0)
df_map['CO2_Emission_kg'] = df_map['Distance_km'] * df_map['CO2_Factor']
df_map['Climate_Impact_CO2e_kg'] = df_map['CO2_Emission_kg'] * RADIATIVE_FORCING_INDEX
df_map['Total_Climate_Impact_CO2e_Ton'] = (df_map['Climate_Impact_CO2e_kg'] * df_map['Aantal_Vluchten']) / 1000


# --- 6. DASHBOARD UI ---
st.title("🌍 Wereldwijde Vluchtactiviteit & Klimaatimpact")
st.write(f"Elke dag landen en vertrekken er duizenden vliegtuigen. Hierachter zit een wereld van data. In dit dashboard is twee jaar vliegdata van Zürich weergegeven. Op de verschillende pagina's zijn een aantal zaken te vinden. Hierbij kan gedacht worden aan populaire bestemmingen, milieu impact, type vliegtuigen en vertragingen. In dit dashboard zie je gegevens voor de periode: **{geselecteerde_periode[0].strftime('%d-%m-%Y')} tot {geselecteerde_periode[1].strftime('%d-%m-%Y')}**")

# --- BUBBEL DIAGRAM ---
st.header("1. Wereldwijde Vluchtactiviteit")
fig_bubbles = px.scatter_geo(
    df_map, lat='Latitude', lon='Longitude', size='Aantal_Vluchten',
    hover_name='Name', color='Aantal_Vluchten', color_continuous_scale='Plasma',
    projection="natural earth", labels={'Aantal_Vluchten': 'Aantal Vluchten'}
)
st.plotly_chart(fig_bubbles, use_container_width=True)


st.divider()

# --- STAAF DIAGRAM (Top 10 hubs) ---
st.header("2. Top 10 Drukste Luchthavens")
top_10_hubs = df_map.nlargest(10, 'Aantal_Vluchten')

fig_bar = px.bar(
    top_10_hubs, x='Aantal_Vluchten', y='Name', orientation='h', 
    color='Aantal_Vluchten', color_continuous_scale='Viridis',
    labels={'Name': 'Luchthaven', 'Aantal_Vluchten': 'Totaal aantal vluchten'}
)
fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# --- KLIMAAT IMPACT SECTIE ---
st.header("🌱 3. Klimaatimpact Analyse (CO2e)")
st.write("Overzicht van de uitstoot per route, meegerekend dat effecten op grote hoogte de impact verdubbelen (Radiative Forcing).")

# KPI's
totale_uitstoot = df_map['Total_Climate_Impact_CO2e_Ton'].sum()
gemiddelde_vlucht = df_map['Climate_Impact_CO2e_kg'].mean()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Totale Netwerk Uitstoot (Ton)", f"{totale_uitstoot:,.0f}".replace(',', '.'))
with col2:
    st.metric("Gem. uitstoot enkele vlucht (Kg)", f"{gemiddelde_vlucht:,.0f}".replace(',', '.'))
with col3:
    bomen_nodig = (totale_uitstoot * 1000) / 20
    st.metric("Bomen nodig voor compensatie", f"{bomen_nodig:,.0f}".replace(',', '.'))

st.write("") 

# Hier staan de grafieken nu recht onder elkaar in plaats van in kolommen

# Staafdiagram meest vervuilende routes 
st.subheader("Top 10 Routes (Totale Uitstoot)")
top_10_co2 = df_map.nlargest(10, 'Total_Climate_Impact_CO2e_Ton')

fig_co2_bar = px.bar(
    top_10_co2, x='Total_Climate_Impact_CO2e_Ton', y='Name', orientation='h', 
    color='Total_Climate_Impact_CO2e_Ton', color_continuous_scale='Reds',
    labels={'Name': 'Luchthaven', 'Total_Climate_Impact_CO2e_Ton': 'CO2e (Ton)'}
)
fig_co2_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_co2_bar, use_container_width=True)

st.write("") # Beetje extra ruimte ertussen
