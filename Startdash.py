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
###    inladen docs###
######################

Airports_ex_cl = "data/airports-extended-clean.csv"
ZIPPIE = "data/excel_files.zip"  # Pad naar jouw ZIP-bestand

######################
###loading in cache###
######################

@st.cache_data(show_spinner="Airports laden...")
def load_airports(path: str) -> pd.DataFrame:
    """Laadt airports-extended-clean.csv en cached het resultaat."""
    return pd.read_csv(path, low_memory=False)
 
 
@st.cache_data(show_spinner="Vluchtdata uit ZIP laden en converteren...")
def load_flights_from_zip(zip_path: str) -> dict[str, pd.DataFrame]:
    """
    Strategie: ZIP → Excel in-memory → direct naar pandas DataFrame.
 
    Waarom deze aanpak:
    - Excel-bestanden hebben dezelfde kolomstructuur maar mogen NIET gemixt worden
      (elke vlucht is een apart bestand).
    - Door ze via io.BytesIO in te lezen en direct naar DataFrame te converteren,
      sla je de Excel-overhead over bij hergebruik (cache doet de rest).
    - Resultaat: dict van { vlucht_sleutel: DataFrame }, makkelijk op te vragen
      via session_state["flights"]["vlucht_naam"].
 
    Naamgeving sleutel:
    - Bestandsnaam zonder extensie wordt de dict-sleutel, bijv. "vlucht_AMS_2024_01"
    - Zo kun je later eenvoudig selecteren: st.selectbox(options=list(flights.keys()))
    """
    flights: dict[str, pd.DataFrame] = {}
 
    with zipfile.ZipFile(zip_path, "r") as z:
        all_files = [
            name for name in z.namelist()
            if not name.startswith("__MACOSX") and not name.endswith("/")
        ]
 
        excel_files = [f for f in all_files if f.endswith((".xlsx", ".xls"))]
        csv_files   = [f for f in all_files if f.endswith(".csv")]
 
        # ── Excel → DataFrame ──────────────────
        for name in excel_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df  = pd.read_excel(buf)
                key = Path(name).stem          # bestandsnaam zonder extensie
                flights[key] = df
 
        # ── CSV uit ZIP (indien aanwezig) ──────
        for name in csv_files:
            with z.open(name) as f:
                buf = io.BytesIO(f.read())
                df  = pd.read_csv(buf, low_memory=False)
                key = Path(name).stem
                flights[key] = df
 
    return flights

######################
###in session state###
######################

def initialize_data():
    """
    Roep deze functie aan bovenaan elk pagina-bestand.
 
    Gebruik in je pagina:
        from data_loader import initialize_data, show_data_debugger
        initialize_data()
 
        airports = st.session_state["airports"]          # DataFrame
        flights  = st.session_state["flights"]           # dict { naam: DataFrame }
        vlucht   = flights["vlucht_AMS_2024_01"]         # één specifieke vlucht
    """
    # ── Airports CSV ──────────────────────────
    if "airports" not in st.session_state:
        if os.path.exists(AIRPORTS_CSV_PATH):
            st.session_state["airports"] = load_airports(AIRPORTS_CSV_PATH)
        else:
            st.warning(f"Bestand niet gevonden: `{AIRPORTS_CSV_PATH}`")
            st.session_state["airports"] = None
 
    # ── Vluchten uit ZIP ──────────────────────
    if "flights" not in st.session_state:
        if os.path.exists(FLIGHTS_ZIP_PATH):
            st.session_state["flights"] = load_flights_from_zip(FLIGHTS_ZIP_PATH)
        else:
            st.warning(f"ZIP niet gevonden: `{FLIGHTS_ZIP_PATH}`")
            st.session_state["flights"] = {}
 
 
######################
###intro tekst###
######################



######################
###EERSTE FIGUREN  ###
######################


######################
###    Debugging   ###
######################

def show_data_debugger():
    """
    Toon onderin de pagina een overzichtstabel van alle geladen data.
    Roep aan onderaan je pagina-bestand, na je overige inhoud.
    """
    st.divider()
 
    with st.expander("🛠️ Data Debugger – geladen bestanden", expanded=True):
        st.caption("Overzicht van alle datasets in `st.session_state`")
 
        rows = []
 
        # ── Airports ──────────────────────────
        airports_df = st.session_state.get("airports")
        rows.append(_make_debug_row(
            bestand = "airports-extended-clean.csv",
            bron    = "CSV",
            sleutel = "airports",
            df      = airports_df,
        ))
 
        # ── Vluchten ──────────────────────────
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
                "Status"        : "❌ Niet gevonden of leeg",
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
 
        # ── Kolomnamen per bestand ─────────────
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
    """Hulpfunctie: maak één rij voor de debugger-tabel."""
    if df is not None:
        return {
            "Bestand"       : bestand,
            "Bron"          : bron,
            "session_state" : sleutel,
            "Status"        : "✅ Geladen",
            "Rijen"         : f"{len(df):,}",
            "Kolommen"      : len(df.columns),
            "Geheugen (MB)" : f"{df.memory_usage(deep=True).sum() / 1e6:.2f}",
        }
    return {
        "Bestand"       : bestand,
        "Bron"          : bron,
        "session_state" : sleutel,
        "Status"        : "❌ Niet gevonden",
        "Rijen"         : "-",
        "Kolommen"      : "-",
        "Geheugen (MB)" : "-",
    }
 

##  Einde script ###
