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

initialize_data()

######################
###  Data laden     ###
######################

flights_raw = st.session_state.get("flights", {})

schedule_key = None
for k in flights_raw:
    if "schedule" in k.lower() or "airport" in k.lower():
        schedule_key = k
        break

if schedule_key is None:
    st.error(
        "Geen schedule-bestand gevonden in de ZIP. "
        "Zorg dat het bestandsnaam 'schedule' of 'airport' bevat."
    )
    st.stop()

df_raw = flights_raw[schedule_key].copy()

######################
### Feature engineering
######################

def parse_time_col(series: pd.Series) -> pd.Series:
    """Zet HH:MM:SS of HH:MM strings om naar tijddelta in minuten."""
    def _to_minutes(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        parts = s.split(":")
        try:
            if len(parts) >= 2:
                h, m = int(parts[0]), int(parts[1])
                return h * 60 + m
        except Exception:
            pass
        return np.nan
    return series.apply(_to_minutes)

@st.cache_data(show_spinner="Features berekenen...")
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["gepland_min"]   = parse_time_col(df["STA_STD_ltc"])
    df["werkelijk_min"] = parse_time_col(df["ATA_ATD_ltc"])
    df["vertraging_min"] = df["werkelijk_min"] - df["gepland_min"]
    df = df.dropna(subset=["vertraging_min"])

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

    if "STD" in df.columns:
        df["STD_dt"] = pd.to_datetime(df["STD"], errors="coerce", dayfirst=True)
        df["dag_vd_week"]  = df["STD_dt"].dt.dayofweek
        df["maand"]        = df["STD_dt"].dt.month
        df["dag_vd_maand"] = df["STD_dt"].dt.day

    df["uur"] = (df["gepland_min"] // 60).clip(0, 23).astype("Int64")

    if "LSV" in df.columns:
        df["is_inbound"] = (df["LSV"].astype(str).str.strip().str.upper() == "L").astype(int)

    if "ACT" in df.columns:
        le_act = LabelEncoder()
        df["actype_code"] = le_act.fit_transform(
            df["ACT"].astype(str).str.strip().fillna("ONBEKEND")
        )

    if "RWY" in df.columns:
        le_rwy = LabelEncoder()
        df["rwy_code"] = le_rwy.fit_transform(
            df["RWY"].astype(str).str.strip().fillna("ONBEKEND")
        )

    if "Org/Des" in df.columns:
        top_dest = df["Org/Des"].value_counts().nlargest(30).index
        df["dest_top"] = df["Org/Des"].where(df["Org/Des"].isin(top_dest), other="OVERIG")
        le_dest = LabelEncoder()
        df["dest_code"] = le_dest.fit_transform(df["dest_top"].astype(str))

    return df

df = build_features(df_raw)

######################
### UI              ###
######################

st.title("Vertragingsanalyse & Regressie")

st.markdown("""
Deze pagina biedt een uitgebreide analyse van vluchvertragingen. Je vindt hier:
- **Overzichtsstatistieken** van alle vertragingen
- **Visuele analyses** om patronen te ontdekken
- **Een voorspelmodel** om toekomstige vertragingen in te schatten

Vertragingen zijn ingedeeld in drie categorieën:
- **On time**: minder dan 5 minuten vertraging
- **Small delay**: 5 tot 45 minuten vertraging  
- **Large delay**: meer dan 45 minuten vertraging
""")

st.divider()

######################
### 1. Overzicht    ###
######################

st.subheader("📊 Overzicht vertraging")

st.markdown("""
Onderstaande kerncijfers geven een snel inzicht in de algehele vertragingsprestaties. 
Deze metrics helpen bij het identificeren van de omvang van vertragingsproblemen.
""")

totaal     = len(df)
on_time    = (df["delay_cat"] == "On time").sum()
small_del  = (df["delay_cat"] == "Small delay").sum()
large_del  = (df["delay_cat"] == "Large delay").sum()
gem_vertr  = df["vertraging_min"].mean()
med_vertr  = df["vertraging_min"].median()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Totaal vluchten",   f"{totaal:,}")
c2.metric("✅ On time",         f"{on_time:,}",   f"{on_time/totaal*100:.1f}%")
c3.metric("🟡 Small delay",    f"{small_del:,}",  f"{small_del/totaal*100:.1f}%")
c4.metric("🔴 Large delay",    f"{large_del:,}",  f"{large_del/totaal*100:.1f}%")
c5.metric("📊 Gem. vertraging", f"{gem_vertr:.1f} min")
c6.metric("📈 Mediaan",         f"{med_vertr:.1f} min")

with st.expander("ℹ️ Wat betekenen deze cijfers?"):
    st.markdown(f"""
    | Metric | Betekenis | Interpretatie |
    |--------|-----------|---------------|
    | **Totaal vluchten** | Het totale aantal geanalyseerde vluchten | Basis voor alle percentages |
    | **On time** | Vluchten met <5 min vertraging | Hoe hoger, hoe beter de prestatie |
    | **Small delay** | Vluchten met 5-45 min vertraging | Acceptabele vertragingen, maar ruimte voor verbetering |
    | **Large delay** | Vluchten met >45 min vertraging | Kritieke vertragingen die aandacht vereisen |
    | **Gemiddelde vertraging** | Rekenkundig gemiddelde van alle vertragingen | Geeft algemeen beeld, maar gevoelig voor uitschieters |
    | **Mediaan** | Middelste waarde van alle vertragingen | Robuuster dan gemiddelde; de "typische" vertraging |
    
    **Tip:** Als het gemiddelde veel hoger is dan de mediaan (zoals nu: {gem_vertr:.1f} vs {med_vertr:.1f} min), 
    zijn er waarschijnlijk enkele vluchten met extreme vertragingen die het gemiddelde omhoog trekken.
    """)

st.divider()

######################
### 2. Grafieken   ###
######################

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Verdeling vertragingscategorieën")
    st.markdown("*Toont het aandeel van elke vertragingscategorie in het totaal.*")
    
    cat_counts = df["delay_cat"].value_counts().reindex(
        ["On time", "Small delay", "Large delay"]
    )
    fig_pie = go.Figure(go.Pie(
        labels=cat_counts.index,
        values=cat_counts.values,
        marker=dict(colors=["#2ca02c", "#ff7f0e", "#d62728"]),
        hole=0.4,
        textinfo="percent+label",
    ))
    fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0),
                          showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_g2:
    st.subheader("Aantal vertragingen per categorie")
    st.markdown("*Toont het absolute aantal vluchten per vertragingscategorie.*")
    
    # Nieuw cirkeldiagram met aantallen
    cat_counts = df["delay_cat"].value_counts().reindex(
        ["On time", "Small delay", "Large delay"]
    )
    fig_counts = go.Figure(go.Pie(
        labels=cat_counts.index,
        values=cat_counts.values,
        marker=dict(colors=["#2ca02c", "#ff7f0e", "#d62728"]),
        hole=0.4,
        textinfo="value+label",
        texttemplate="%{label}<br>%{value:,} vluchten",
    ))
    fig_counts.update_layout(
        height=350, 
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False
    )
    st.plotly_chart(fig_counts, use_container_width=True)

with st.expander("ℹ️ Hoe lees je deze grafieken?"):
    st.markdown("""
    **Linker diagram (percentages):**
    - Toont de *proportionele verdeling* van vertragingen
    - Groen = op tijd, oranje = kleine vertraging, rood = grote vertraging
    - Ideaal: zo veel mogelijk groen
    
    **Rechter diagram (aantallen):**
    - Toont de *absolute aantallen* per categorie
    - Handig om de werkelijke impact te zien (bijv. hoeveel passagiers zijn getroffen)
    - Gecombineerd met percentages krijg je een compleet beeld
    """)

# Histogram vertraging
st.subheader("Histogram vertraging (−30 t/m +120 min)")
st.markdown("""
*Dit histogram toont de spreiding van vertragingen. Negatieve waarden betekenen dat de vlucht 
eerder aankwam dan gepland.*
""")

df_clip = df[df["vertraging_min"].between(-30, 120)]
fig_hist = px.histogram(
    df_clip, x="vertraging_min", nbins=60,
    color="delay_cat",
    color_discrete_map={
        "On time":     "#2ca02c",
        "Small delay": "#ff7f0e",
        "Large delay": "#d62728",
    },
    labels={"vertraging_min": "Vertraging (min)", "delay_cat": "Categorie"},
)
fig_hist.update_layout(
    height=350,
    margin=dict(l=40, r=20, t=10, b=40),
    bargap=0.05,
    legend_title="Categorie",
)
st.plotly_chart(fig_hist, use_container_width=True)

with st.expander("ℹ️ Wat zie je in dit histogram?"):
    st.markdown("""
    - **X-as**: Vertraging in minuten (negatief = vroeger, positief = later)
    - **Y-as**: Aantal vluchten met die vertraging
    - **Kleuren**: Corresponderen met de vertragingscategorieën
    
    **Wat te zoeken:**
    - Een *smalle piek rond 0* duidt op goede punctualiteit
    - Een *lange staart naar rechts* wijst op structurele vertragingsproblemen
    - *Meerdere pieken* kunnen wijzen op verschillende oorzaken van vertraging
    """)

st.divider()

######################
### 3. Regressie   ###
######################

st.subheader("📈 Lineaire regressie – vertraging voorspellen")

st.markdown("""
Met lineaire regressie proberen we te voorspellen hoeveel vertraging een vlucht zal hebben, 
gebaseerd op kenmerken zoals tijdstip, vliegtuigtype en bestemming.

**Hoe werkt het?**
Het model zoekt een wiskundige relatie tussen de gekozen kenmerken (features) en de vertraging. 
Deze relatie wordt "getraind" op historische data en kan daarna gebruikt worden voor voorspellingen.
""")

ALLE_FEATURES = {
    "Uur van de dag":        "uur",
    "Inbound / Outbound":    "is_inbound",
    "Vliegtuigtype":         "actype_code",
    "Runway":                "rwy_code",
    "Bestemming/afkomst":    "dest_code",
    "Dag van de week":       "dag_vd_week",
    "Maand":                 "maand",
    "Dag van de maand":      "dag_vd_maand",
}

beschikbare = {
    label: col
    for label, col in ALLE_FEATURES.items()
    if col in df.columns
}

with st.expander("⚙️ Instellingen regressie", expanded=True):
    st.markdown("*Selecteer welke kenmerken het model moet gebruiken voor de voorspelling.*")
    
    gekozen_labels = st.multiselect(
        "Kies de features voor het model:",
        options=list(beschikbare.keys()),
        default=list(beschikbare.keys()),
        help="Meer features kunnen leiden tot betere voorspellingen, maar ook tot 'overfitting'."
    )
    test_size = st.slider(
        "Testset grootte (%)", 10, 40, 20, step=5,
        help="Percentage data dat apart gehouden wordt om het model te testen."
    )
    target_col = st.radio(
        "Doelvariabele:",
        ["Vertraging in minuten (regressie)", "Vertragingscategorie (0/1/2)"],
        horizontal=True,
        help="Kies of je de exacte vertraging wilt voorspellen of alleen de categorie."
    )

if not gekozen_labels:
    st.warning("Selecteer minimaal één feature.")
    st.stop()

gekozen_cols = [beschikbare[l] for l in gekozen_labels]
y_col = "vertraging_min" if "minuten" in target_col else "delay_code"

df_model = df[gekozen_cols + [y_col]].dropna()

if len(df_model) < 50:
    st.error("Te weinig rijen na cleaning om een model te trainen.")
    st.stop()

X = df_model[gekozen_cols].values
y = df_model[y_col].values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=test_size / 100, random_state=42
)

model = LinearRegression()
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

mae  = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2   = r2_score(y_test, y_pred)

######################
### 4. Resultaten  ###
######################

st.subheader("📊 Modelresultaten")

m1, m2, m3, m4 = st.columns(4)
m1.metric("R² score",   f"{r2:.3f}")
m2.metric("MAE",        f"{mae:.2f} min")
m3.metric("RMSE",       f"{rmse:.2f} min")
m4.metric("Trainrijen", f"{len(X_train):,}")

with st.expander("ℹ️ Wat betekenen deze modelmetrics?"):
    st.markdown(f"""
    | Metric | Waarde | Betekenis | Interpretatie |
    |--------|--------|-----------|---------------|
    | **R² score** | {r2:.3f} | Verklaarde variantie | 0 = model verklaart niets, 1 = perfecte voorspelling. Huidige waarde betekent dat {r2*100:.1f}% van de variatie verklaard wordt. |
    | **MAE** | {mae:.2f} min | Gemiddelde absolute fout | Gemiddeld zit de voorspelling er {mae:.1f} minuten naast. |
    | **RMSE** | {rmse:.2f} min | Root mean squared error | Zoals MAE, maar bestraft grote fouten zwaarder. |
    | **Trainrijen** | {len(X_train):,} | Aantal trainingsvoorbeelden | Meer data = betrouwbaarder model. |
    
    **Is dit model goed?**
    - R² < 0.3: Model heeft beperkte voorspellende kracht
    - R² 0.3-0.6: Redelijke voorspellingen mogelijk
    - R² > 0.6: Goede voorspellingen
    
    *Let op: vertragingen zijn inherent moeilijk te voorspellen omdat ze vaak afhangen van externe factoren 
    (weer, technische problemen) die niet in deze data zitten.*
    """)

col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("**Werkelijk vs. voorspeld**")
    st.markdown("*Hoe dichter de punten bij de rode lijn, hoe beter het model.*")
    
    sample_n = min(500, len(y_test))
    idx = np.random.choice(len(y_test), sample_n, replace=False)
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=y_test[idx], y=y_pred[idx],
        mode="markers",
        marker=dict(size=4, color="#1f77b4", opacity=0.5),
        name="Voorspelling",
    ))
    mn, mx = float(y_test.min()), float(y_test.max())
    fig_scatter.add_trace(go.Scatter(
        x=[mn, mx], y=[mn, mx],
        mode="lines",
        line=dict(color="red", dash="dash", width=1),
        name="Ideaal",
    ))
    fig_scatter.update_layout(
        xaxis_title="Werkelijke vertraging",
        yaxis_title="Voorspelde vertraging",
        height=380,
        margin=dict(l=40, r=20, t=10, b=40),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with col_r2:
    st.markdown("**Feature importantie (coëfficiënten)**")
    st.markdown("*Toont hoeveel elke feature bijdraagt aan de voorspelling.*")
    
    coef_df = pd.DataFrame({
        "Feature":     gekozen_labels,
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
        xaxis_title="Coëfficiënt (effect op vertraging)",
        height=380,
        margin=dict(l=10, r=20, t=10, b=40),
    )
    st.plotly_chart(fig_coef, use_container_width=True)

with st.expander("ℹ️ Hoe interpreteer je deze grafieken?"):
    st.markdown("""
    **Scatter plot (links):**
    - Elk punt is één vlucht uit de testset
    - X-as: werkelijke vertraging
    - Y-as: door model voorspelde vertraging
    - De rode stippellijn toont perfecte voorspelling
    - Punten ver van de lijn = slechte voorspellingen
    
    **Feature importantie (rechts):**
    - Toont de coëfficiënt (gewicht) van elke feature
    - **Rood (positief)**: hogere waarde → meer vertraging
    - **Blauw (negatief)**: hogere waarde → minder vertraging
    - Langere balk = grotere invloed op voorspelling
    
    *Let op: de schaal van features beïnvloedt de coëfficiënt. 
    Een kleine coëfficiënt kan nog steeds belangrijk zijn als de feature grote waarden heeft.*
    """)

st.divider()

######################
### 5. Predictor   ###
######################

st.subheader("🔮 Voorspel een vertraging")

st.markdown("""
Gebruik het getrainde model om een voorspelling te doen voor een specifieke vlucht.
Vul de kenmerken in en klik op 'Voorspel vertraging' om te zien wat het model voorspelt.

**Let op:** Dit is een *schatting* gebaseerd op historische patronen. Werkelijke vertragingen 
kunnen afwijken door factoren die niet in het model zitten (weer, stakingen, etc.).
""")

pred_input = {}
cols_pred = st.columns(4)
col_map = {col: i % 4 for i, col in enumerate(gekozen_labels)}

for label in gekozen_labels:
    col_key = beschikbare[label]
    with cols_pred[col_map[label]]:
        if col_key == "uur":
            pred_input[col_key] = st.number_input(label, 0, 23, 10, help="0-23, waarbij 0 = middernacht")
        elif col_key == "is_inbound":
            pred_input[col_key] = st.selectbox(label, [0, 1],
                                                format_func=lambda x: "Inbound" if x == 1 else "Outbound",
                                                help="Inbound = aankomend, Outbound = vertrekkend")
        elif col_key == "dag_vd_week":
            dag_namen = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
            pred_input[col_key] = st.selectbox(label, list(range(7)),
                                                format_func=lambda x: dag_namen[x])
        elif col_key == "maand":
            pred_input[col_key] = st.number_input(label, 1, 12, 6, help="1 = januari, 12 = december")
        elif col_key == "dag_vd_maand":
            pred_input[col_key] = st.number_input(label, 1, 31, 15)
        else:
            min_val = int(df[col_key].min())
            max_val = int(df[col_key].max())
            med_val = int(df[col_key].median())
            pred_input[col_key] = st.number_input(
                label, min_val, max_val, med_val,
                help=f"Code voor {label.lower()}. Mediaan: {med_val}"
            )

if st.button("Voorspel vertraging", type="primary"):
    X_new = np.array([[pred_input[c] for c in gekozen_cols]])
    voorspelling = model.predict(X_new)[0]

    if "minuten" in target_col:
        cat = (
            "✅ On time" if voorspelling < 5
            else "🟡 Small delay" if voorspelling <= 45
            else "🔴 Large delay"
        )
        st.success(
            f"Voorspelde vertraging: **{voorspelling:.1f} minuten**  →  {cat}"
        )
        
        # Extra context
        st.info(f"""
        **Context:** Het gemiddelde in de dataset is {gem_vertr:.1f} minuten. 
        Deze voorspelling is {"hoger" if voorspelling > gem_vertr else "lager"} dan gemiddeld.
        
        *Onthoud: de MAE van het model is {mae:.1f} minuten, dus de werkelijke vertraging 
        kan gemiddeld zoveel afwijken van deze voorspelling.*
        """)
    else:
        cat_map = {0: "✅ On time", 1: "🟡 Small delay", 2: "🔴 Large delay"}
        st.success(
            f"Voorspelde categorie: **{cat_map.get(round(voorspelling), '?')}** "
            f"(score: {voorspelling:.2f})"
        )
