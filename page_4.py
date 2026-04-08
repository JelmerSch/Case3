import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from Startdash import initialize_data

#Vertragingsanalyse

# Initialiseer de data (laadt de data in de session state)
initialize_data()

# Stel de paginatitel in (optioneel)
st.set_page_config(page_title="Vluchtvertragingsanalyse", layout="wide")

##################################
### Data laden en voorbereiden ###
##################################

flights_raw = st.session_state.get("flights", {})
airports = st.session_state.get("airports", pd.DataFrame())

# Gebruik ICAO-kolom
icao_to_full_name = {}
if airports is not None and not airports.empty:
    if "ICAO" in airports.columns and "Name" in airports.columns:
        icao_to_full_name = (airports.dropna(subset=["ICAO", "Name"]).set_index("ICAO")["Name"].to_dict())

# Zoek het juiste CSV-bestand in de flights_raw dictionary (bijv. "schedule_airport")
schedule_key = None
for k in flights_raw:
    if "schedule" in k.lower() or "airport" in k.lower():
        schedule_key = k
        break

if schedule_key is None:
    st.error("Geen schedule-bestand gevonden in de session state.")
    st.stop()

df_raw = flights_raw[schedule_key].copy()

###########################
### Feature engineering ###
###########################

def parse_time_col(series: pd.Series) -> pd.Series:
    """Zet een tijdskolom (HH:MM) om naar minuten."""
    def _to_minutes(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        parts = s.split(":")
        try:
            if len(parts) >= 2:
                return int(parts[0]) * 60 + int(parts[1])
        except:
            pass
        return np.nan
    return series.apply(_to_minutes)

@st.cache_data(show_spinner="Features berekenen...")
def build_features(df: pd.DataFrame, airports_mapping) -> pd.DataFrame:
    """Berekent relevante features voor analyse en regressie."""
    df = df.copy()

    # Bereken vertraging in minuten
    if "STA_STD_ltc" in df.columns and "ATA_ATD_ltc" in df.columns:
        df["gepland_min"] = parse_time_col(df["STA_STD_ltc"])
        df["werkelijk_min"] = parse_time_col(df["ATA_ATD_ltc"])
        df["vertraging_min"] = df["werkelijk_min"] - df["gepland_min"]
        df = df.dropna(subset=["vertraging_min"])
    else:
        st.error("Noodzakelijke tijdkolommen (STA_STD_ltc, ATA_ATD_ltc) ontbreken.")
        st.stop()

    # Categoriseer vertraging
    def categorize(v):
        if v < 5:
            return "On time"
        elif v <= 45:
            return "Small delay"
        else:
            return "Large delay"

    df["delay_cat"] = df["vertraging_min"].apply(categorize)
    df["delay_code"] = df["delay_cat"].map(
        {"On time": 0, "Small delay": 1, "Large delay": 2}
    )

    # Datum en tijd informatie
    if "STD" in df.columns:
        df["STD_dt"] = pd.to_datetime(df["STD"], errors="coerce", dayfirst=True)
        df["dag_vd_week"] = df["STD_dt"].dt.dayofweek
        df["maand"] = df["STD_dt"].dt.month
        df["dag_vd_maand"] = df["STD_dt"].dt.day

    # Uur van de dag
    df["uur"] = (df["gepland_min"] // 60).clip(0, 23).astype("Int64")

    # Inbound / Outbound
    if "LSV" in df.columns:
        df["is_inbound"] = (
            df["LSV"].astype(str).str.strip().str.upper() == "L"
        ).astype(int)

    # Aircraft type (label + code voor model)
    if "ACT" in df.columns:
        df["actype_label"] = df["ACT"].astype(str).str.strip().fillna("ONBEKEND")
        le_act = LabelEncoder()
        df["actype_code"] = le_act.fit_transform(df["actype_label"])

    # Runway
    if "RWY" in df.columns:
        df["rwy_label"] = df["RWY"].astype(str).str.strip().fillna("ONBEKEND")
        le_rwy = LabelEncoder()
        df["rwy_code"] = le_rwy.fit_transform(df["rwy_label"])

    # Airport mapping (ICAO -> Volledige naam)
    if "Org/Des" in df.columns:
        # Haal de volledige luchthavennaam op uit de mapping
        df["airport_full_name"] = df["Org/Des"].map(airports_mapping)
        # Als de naam niet wordt gevonden, gebruik dan de IATA-code
        df["airport_full_name"] = df["airport_full_name"].fillna(df["Org/Des"])

        # Identificeer de top 30 bestemmingen voor de model_training
        top_dest = df["Org/Des"].value_counts().nlargest(30).index
        df["dest_code"] = LabelEncoder().fit_transform(
            df["Org/Des"].where(df["Org/Des"].isin(top_dest), other="OVERIG").astype(str)
        )
        df["dest_label"] = df["Org/Des"] # Voor de selectbox

    return df

# Bouw de features
df = build_features(df_raw, icao_to_full_name)

########################
### UI - Hoofdpagina ###
########################

st.title("Vertragingsanalyse & voorspeller")
st.markdown("""
Welkom op de pagina voor het analyseren en voorspellen van vluchtvertragingen.
Dit dashboard is onderverdeeld in vier secties:
1.  **Overzicht**: Bekijk de belangrijkste statistieken over vertragingen.
2.  **Visualisaties**: Analyseer de verdeling van vertragingen via grafieken.
3.  **Model**: Configureer en train een lineair regressiemodel om vertragingen te voorspellen.
4.  **Voorspeller**: Gebruik het getrainde model om de vertraging van een specifieke vlucht te schatten.
""")

######################
### 1. Overzicht #####
######################

st.header("1. Overzicht vertraging")
st.markdown("""
Deze sectie toont de belangrijkste statistieken van de vluchtdata, zoals het totaal aantal vluchten,
de verdeling van vertragingscategorieën en de gemiddelde en mediaan vertraging.
Hierdoor krijg je snel een beeld van de algemene prestaties van de vluchten.
""")

totaal = len(df)
on_time = (df["delay_cat"] == "On time").sum()
small_del = (df["delay_cat"] == "Small delay").sum()
large_del = (df["delay_cat"] == "Large delay").sum()
gem_vertr = df["vertraging_min"].mean()
med_vertr = df["vertraging_min"].median()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Totaal vluchten", f"{totaal:,}")
c2.metric("✅ Op tijd (<5 min)", f"{on_time:,}")
c3.metric("🟡 Kleine vertraging (5-45 min)", f"{small_del:,}")
c4.metric("🔴 Grote vertraging (>45 min)", f"{large_del:,}")
c5.metric("📊 Gem. vertraging", f"{gem_vertr:.1f} min")
c6.metric("📈 Mediaan vertraging", f"{med_vertr:.1f} min")

st.divider()

######################
### 2. Grafieken #####
######################

st.header("2. Visualisaties")
st.markdown("""
Hieronder staan grafieken die de vertragingsdata visualiseren.
* **Verdeling vertragingscategorieën**: Laat zien welk percentage van de vluchten op tijd is, of een kleine/grote vertraging heeft.
* **Cirkeldiagram vertraging per uur**: Toont de verdeling van *alle* vertragingen over de verschillende uren van de dag, waardoor je kunt zien in welk uur de meeste vertragingen optreden.
* **Histogram vertraging**: Toont de frequentie van vertragingen binnen een bepaald bereik (-30 tot 120 minuten), gekleurd per categorie.
""")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Verdeling vertragingscategorieën")
    cat_counts = df["delay_cat"].value_counts().reindex(
        ["On time", "Small delay", "Large delay"]
    )
    fig_pie_cat = go.Figure(go.Pie(
        labels=cat_counts.index,
        values=cat_counts.values,
        marker=dict(colors=["#2ca02c", "#ff7f0e", "#d62728"]),
        hole=0.4,
        textinfo="percent+label",
    ))
    fig_pie_cat.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    st.plotly_chart(fig_pie_cat, use_container_width=True)

with col_g2:
    st.subheader("Totaal aantal vertragingen per uur")
    if "uur" in df.columns:
        uur_counts = (
            df.groupby("uur")["vertraging_min"]
            .count()
            .reset_index()
            .rename(columns={"vertraging_min": "aantal", "uur": "Uur"})
        )
        # Kleur op categoriemix per uur
        uur_delay = (
            df.groupby(["uur", "delay_cat"])
            .size()
            .reset_index(name="aantal")
            .rename(columns={"uur": "Uur"})
        )
        fig_uur = px.bar(
            uur_delay,
            x="Uur",
            y="aantal",
            color="delay_cat",
            color_discrete_map={
                "On time":     "#2ca02c",
                "Small delay": "#ff7f0e",
                "Large delay": "#d62728",
            },
            labels={"aantal": "Aantal vluchten", "Uur": "Uur van de dag", "delay_cat": "Categorie"},
            barmode="stack",
        )
        fig_uur.update_layout(
            height=350,
            margin=dict(l=40, r=20, t=10, b=40),
            legend_title="Categorie",
            xaxis=dict(tickmode="linear", dtick=1),
        )
        st.plotly_chart(fig_uur, use_container_width=True)

st.divider()

######################
### 3. Model #########
######################

st.header("3. Lineaire Regressiemodel")
st.markdown(f"""
In deze sectie kun je een lineair regressiemodel trainen om vertragingen te voorspellen.
Je kunt selecteren welke kenmerken (features) het model moet gebruiken.
Na het trainen worden de prestaties van het model getoond met behulp van statistieken en grafieken.

* **R² score**: Geeft aan hoeveel van de variatie in de vertraging het model verklaart (1 is perfect, 0 betekent dat het model niets verklaart).
* **MAE (Mean Absolute Error)**: De gemiddelde absolute afwijking tussen de voorspelde en werkelijke vertraging, uitgedrukt in minuten.
* **RMSE (Root Mean Squared Error)**: De wortel van de gemiddelde kwadratische fout. Net als MAE meet dit de voorspellingsfout in minuten, maar RMSE straft grote fouten zwaarder af dan MAE — een RMSE van 20 min bij een MAE van 10 min betekent dat er een aantal uitschieters zijn die het gemiddelde omhoog trekken.
* **Testset grootte (%)**: De data wordt opgesplitst in een trainingsset en een testset. Het model leert alleen van de trainingsset; de testset wordt gebruikt om te controleren hoe goed het model generaliseert naar nieuwe, ongeziene vluchten. Een grotere testset geeft een betrouwbaardere evaluatie, maar laat minder data over om op te trainen.
""")

# Beschikbare features
ALLE_FEATURES = {
    "Uur van de dag": "uur",
    "Inbound / Outbound": "is_inbound",
    "Vliegtuigtype": "actype_code",
    "Runway": "rwy_code",
    "Bestemming/afkomst": "dest_code",
    "Dag van de week": "dag_vd_week",
    "Maand": "maand",
    "Dag van de maand": "dag_vd_maand",
}

# Alleen features tonen die daadwerkelijk in df zitten
beschikbare = {
    label: col
    for label, col in ALLE_FEATURES.items()
    if col in df.columns
}

with st.expander("Modelinstellingen", expanded=True):
    gekozen_labels = st.multiselect(
        "Kies de features voor het model:",
        options=list(beschikbare.keys()),
        default=list(beschikbare.keys()),
    )
    test_size = st.slider("Testset grootte (%)", 10, 40, 20, step=5)

if not gekozen_labels:
    st.warning("Selecteer minimaal één feature om het model te trainen.")
    st.stop()

gekozen_cols = [beschikbare[l] for l in gekozen_labels]
y_col = "vertraging_min"

# Voorbereiden van de data voor het model
df_model = df[gekozen_cols + [y_col]].dropna()

if len(df_model) < 50:
    st.error("Te weinig data om een model te trainen na het opschonen.")
    st.stop()

X = df_model[gekozen_cols].values
y = df_model[y_col].values

# Opsplitsen in training en test data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=test_size / 100, random_state=42
)

# Trainen van het lineaire regressiemodel
model = LinearRegression()
model.fit(X_train, y_train)

# Voorspellingen doen op de test data
y_pred = model.predict(X_test)

# Berekenen van de modelprestaties
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

### Modelresultaten tonen
st.subheader("Modelresultaten")

m1, m2, m3, m4 = st.columns(4)
m1.metric("R² score", f"{r2:.3f}")
m2.metric("MAE", f"{mae:.2f} min")
m3.metric("RMSE", f"{rmse:.2f} min")
m4.metric("Trainingsdata (rijen)", f"{len(X_train):,}")

# Visualisatie van modelprestaties
col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("**Werkelijk vs. Voorspeld**")
    st.markdown("""
    In deze grafiek zie je de werkelijke vertraging op de x-as en de voorspelde vertraging op de y-as.
    Een perfect model zou alle punten op de rode stippellijn hebben.
    Hoe dichter de punten bij de rode lijn liggen, hoe beter de voorspellingen.
    """)
    sample_n = min(500, len(y_test))
    idx = np.random.choice(len(y_test), sample_n, replace=False)
    
    # 1. De scatterpunten
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=y_test[idx], y=y_pred[idx],
        mode="markers",
        marker=dict(size=4, color="#1f77b4", opacity=0.5),
        name="Voorspelling",
    ))

    # 2. De Ideale lijn (y=x)
    lijn_max = max(200, float(y_test.max()), float(y_pred.max()))
    lijn_min = min(0, float(y_test.min()), float(y_pred.min()))
    fig_scatter.add_trace(go.Scatter(
        x=[lijn_min, lijn_max], y=[lijn_min, lijn_max],
        mode="lines",
        line=dict(color="red", dash="dash", width=1),
        name="Ideaal (y=x)",
    ))

    # 3. De Model Regressielijn (Trendlijn)
    # We fitten een simpele lijn door de test-resultaten om de afwijking te zien
    reg_line_model = LinearRegression().fit(y_test.reshape(-1, 1), y_pred)
    y_reg_line = reg_line_model.predict(np.array([lijn_min, lijn_max]).reshape(-1, 1))
    
    fig_scatter.add_trace(go.Scatter(
        x=[lijn_min, lijn_max], y=y_reg_line,
        mode="lines",
        line=dict(color="orange", width=2),
        name="Model Trend",
    ))

    fig_scatter.update_layout(
        xaxis=dict(title="Werkelijke vertraging (min)", range=[lijn_min, 200]),
        yaxis=dict(title="Voorspelde vertraging (min)", range=[lijn_min, 200]),
        height=380,
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with col_r2:
    st.markdown("**Feature Importantie (Coëfficiënten)**")
    st.markdown("""
    De grafiek toont de coëfficiënten van het lineaire model.
    Een positieve coëfficiënt (rood) verhoogt de verwachte vertraging,
    terwijl een negatieve coëfficiënt (blauw) de verwachte vertraging verlaagt.
    De grootte van de balk geeft de sterkte van het effect aan.
    """)
    coef_df = pd.DataFrame({
        "Feature": gekozen_labels,
        "Coëfficiënt": model.coef_,
    }).sort_values("Coëfficiënt", key=abs, ascending=True)

    fig_coef = go.Figure(go.Bar(
        x=coef_df["Coëfficiënt"],
        y=coef_df["Feature"],
        orientation="h",
        marker_color=[
            "#d62728" if c > 0 else "#1f77b4"
            for c in coef_df["Coëfficiënt"]
        ],
    ))
    fig_coef.update_layout(
        xaxis_title="Coëfficiënt (effect op vertraging in minuten)",
        height=380,
        margin=dict(l=10, r=20, t=10, b=40),
    )
    st.plotly_chart(fig_coef, use_container_width=True)

st.divider()

######################
### 4. Voorspeller ###
######################

st.header("4. Voorspel een vertraging")
st.markdown("""
Gebruik deze tool om de verwachte vertraging van een vlucht te berekenen op basis van het hierboven getrainde model.
Vul de details van de vlucht in en klik op 'Voorspel vertraging'.
*Let op: De nauwkeurigheid hangt af van de features die je in de modelsectie hebt geselecteerd.*
""")

# Maak een dictionary voor de volledige luchthavennamen (voor de selectbox)
org_des_labels = sorted(df["airport_full_name"].dropna().unique())

pred_input = {}
cols_pred = st.columns(4)
# Verdeel de features over de kolommen
col_idx = 0

for label, col_key in beschikbare.items():
    if label not in gekozen_labels:
        continue # Sla over als deze feature niet in het model zit

    with cols_pred[col_idx % 4]:
        if col_key == "uur":
            pred_input[col_key] = st.number_input(label, 0, 23, 10, help="Het geplande uur van vertrek of aankomst.")
        elif col_key == "is_inbound":
            inbound_choice = st.selectbox(label, ["Outbound", "Inbound"], help="Is de vlucht een aankomst of vertrek?")
            pred_input[col_key] = 1 if inbound_choice == "Inbound" else 0
        elif col_key == "actype_code":
            actype_choice = st.selectbox(label, sorted(df["actype_label"].unique()), help="Het type vliegtuig.")
            pred_input[col_key] = df[df["actype_label"] == actype_choice]["actype_code"].iloc[0]
        elif col_key == "rwy_code":
             rwy_choice = st.selectbox(label, sorted(df["rwy_label"].unique()), help="De gebruikte start- of landingsbaan.")
             pred_input[col_key] = df[df["rwy_label"] == rwy_choice]["rwy_code"].iloc[0]
        elif col_key == "dest_code":
            # Hier gebruiken we de volledige luchthavennamen in de selectbox
            airport_choice = st.selectbox(label, org_des_labels, help="De volledige naam van de luchthaven (herkomst of bestemming).")
            # Vind de bijbehorende dest_code
            pred_input[col_key] = df[df["airport_full_name"] == airport_choice]["dest_code"].iloc[0]
        elif col_key in ["dag_vd_week", "maand", "dag_vd_maand"]:
            min_val = int(df[col_key].min())
            max_val = int(df[col_key].max())
            pred_input[col_key] = st.number_input(label, min_val, max_val, int(df[col_key].median()), help=f"Voer een waarde in tussen {min_val} en {max_val}.")
        else:
            min_val = int(df[col_key].min())
            max_val = int(df[col_key].max())
            pred_input[col_key] = st.number_input(label, min_val, max_val, int(df[col_key].median()))
    col_idx += 1

if st.button("Voorspel vertraging"):
    # Zorg dat de input features in de juiste volgorde staan
    input_data = []
    for col in gekozen_cols:
        input_data.append(pred_input[col])

    X_new = np.array([input_data])
    voorspelling = model.predict(X_new)[0]

    if voorspelling < 0:
        st.success(f"De verwachte vertraging is: {-voorspelling:.1f} minuten *te vroeg*.")
    else:
        st.success(f"De verwachte vertraging is: {voorspelling:.1f} minuten.")
