import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import zipfile
import os
import io
from pathlib import Path

######################
###   Configuratie ###
######################

AIRPORTS_CSV_PATH = "airports-extended-clean.csv"
FLIGHTS_ZIP_PATH  = "data/excel_files.zip"

######################
###  Cache functies ###
######################

@st.cache_data(show_spinner="Airports laden...")
def load_airports(path: str) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


@st.cache_data(show_spinner="Vluchtdata uit ZIP laden...")
def load_flights_from_zip(zip_path: str) -> dict[str, pd.DataFrame]:
    flights: dict[str, pd.DataFrame] = {}

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
                df  = pd.read_excel(buf)
                key = Path(name).stem
                flights[key] = df

        for name in csv_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df  = pd.read_csv(buf, low_memory=False)
                key = Path(name).stem
                flights[key] = df

    return flights

######################
### Session state  ###
######################

def initialize_data():
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

# ── Initialiseer bij het laden van dit bestand ──
initialize_data()

######################
###  Intro tekst   ###
######################



######################
### Eerste figuren ###
######################



######################
###   Debugging    ###
######################

def show_data_debugger():
    st.divider()

    with st.expander("🛠️ Data Debugger – geladen bestanden", expanded=True):
        st.caption("Overzicht van alle datasets in `st.session_state`")

        rows = []

        airports_df = st.session_state.get("airports")
        rows.append(_make_debug_row(
            bestand = "airports-extended-clean.csv",
            bron    = "CSV",
            sleutel = "airports",
            df      = airports_df,
        ))

        flights: dict = st.session_state.get("flights", {})
        if flights:
            for naam, df in flights.items():
                rows.append(_make_debug_row(
                    bestand = naam,
                    bron    = "Excel (uit ZIP)",
                    sleutel = f'flights["{naam}"]',
                    df      = df,
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
            }
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


# ── Debugger altijd tonen onderaan ──
show_data_debugger()

### Einde script ###
