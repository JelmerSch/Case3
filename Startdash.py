import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

CSV_PATH = "data/airports-extended-clean.csv"
ZIP_PATH = "data/excel_files.zip"  # Pad naar jouw ZIP-bestand

######################
###loading in cache###
######################

@st.cache_data(show_spinner="Airports laden...")
def load_airports_csv(path: str) -> pd.DataFrame:
    """Laadt het airports CSV-bestand en cached het resultaat."""
    df = pd.read_csv(path, low_memory=False)
    return df
 
 
@st.cache_data(show_spinner="Excel-bestanden uit ZIP laden...")
def load_excel_from_zip(zip_path: str) -> dict[str, pd.DataFrame]:
    """
    Pakt een ZIP uit en leest alle Excel-bestanden (.xlsx / .xls) in.
    Geeft een dict terug: { bestandsnaam: DataFrame }.
    """
    excel_frames: dict[str, pd.DataFrame] = {}
 
    with zipfile.ZipFile(zip_path, "r") as z:
        excel_names = [
            name for name in z.namelist()
            if name.endswith((".xlsx", ".xls")) and not name.startswith("__MACOSX")
        ]
 
        for name in excel_names:
            with z.open(name) as f:
                # Lees in via bytes-buffer zodat pandas de bestandsnaam niet nodig heeft
                data = io.BytesIO(f.read())
                df = pd.read_excel(data)
                # Gebruik alleen de bestandsnaam (zonder mappad in de ZIP)
                short_name = Path(name).name
                excel_frames[short_name] = df
 
    return excel_frames

######################
###in session state###
######################
def initialize_data():
    """
    Roep deze functie aan bovenaan je pagina-bestand.
    Laadt alle data (via cache) en zet ze in st.session_state.
    """
    # ── Airports CSV ──────────────────────────
    if "airports" not in st.session_state:
        if os.path.exists(CSV_PATH):
            st.session_state["airports"] = load_airports_csv(CSV_PATH)
        else:
            st.warning(f"CSV niet gevonden: `{CSV_PATH}`")
            st.session_state["airports"] = None
 
    # ── Excel-bestanden uit ZIP ───────────────
    if "excel_data" not in st.session_state:
        if os.path.exists(ZIP_PATH):
            st.session_state["excel_data"] = load_excel_from_zip(ZIP_PATH)
        else:
            st.warning(f"ZIP niet gevonden: `{ZIP_PATH}`")
            st.session_state["excel_data"] = {}

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
    Toont een debugger-tabel onderaan de pagina.
    Zet st.session_state["show_debugger"] = True om te activeren.
    """
    st.divider()
 
    with st.expander("🛠️ Data Debugger", expanded=True):
        st.caption("Overzicht van alle geladen bestanden in `st.session_state`")
 
        rows = []
 
        # Airports CSV
        airports_df = st.session_state.get("airports")
        rows.append({
            "Bestand": "airports-extended-clean.csv",
            "Type": "CSV",
            "Status": "✅ Geladen" if airports_df is not None else "❌ Niet gevonden",
            "Rijen": len(airports_df) if airports_df is not None else "-",
            "Kolommen": len(airports_df.columns) if airports_df is not None else "-",
            "Grootte (MB)": f"{airports_df.memory_usage(deep=True).sum() / 1e6:.2f}" if airports_df is not None else "-",
        })
 
        # Excel-bestanden uit ZIP
        excel_data: dict = st.session_state.get("excel_data", {})
        if excel_data:
            for naam, df in excel_data.items():
                rows.append({
                    "Bestand": naam,
                    "Type": "Excel (uit ZIP)",
                    "Status": "✅ Geladen",
                    "Rijen": len(df),
                    "Kolommen": len(df.columns),
                    "Grootte (MB)": f"{df.memory_usage(deep=True).sum() / 1e6:.2f}",
                })
        else:
            rows.append({
                "Bestand": ZIP_PATH,
                "Type": "ZIP / Excel",
                "Status": "❌ Niet gevonden of leeg",
                "Rijen": "-",
                "Kolommen": "-",
                "Grootte (MB)": "-",
            })
 
        debug_df = pd.DataFrame(rows)
        st.dataframe(
            debug_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(width="medium"),
                "Grootte (MB)": st.column_config.TextColumn(width="small"),
            }
        )
 
        # Toon kolomnamen per bestand
        st.markdown("**Kolomnamen per bestand:**")
        if airports_df is not None:
            with st.expander("airports-extended-clean.csv"):
                st.write(list(airports_df.columns))
 
        for naam, df in excel_data.items():
            with st.expander(naam):
                st.write(list(df.columns))

##  Einde script ###
