import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. DATA INLADEN ---
# We laden de data één keer in voor de hele pagina
df_airports = pd.read_csv('airports-extended-clean.csv', sep=';', decimal=',')
df_schedule = pd.read_csv('schedule_airport.csv')

# --- 2. DATA VOORBEREIDEN ---
# Tel het aantal vluchten per ICAO code
flight_counts = df_schedule.groupby('Org/Des').size().reset_index(name='Aantal_Vluchten')

# Koppel de tellingen aan de vliegveld-informatie (naam, lat, lon)
# We gebruiken 'inner' om alleen vliegvelden te tonen die in het schema staan
df_map = pd.merge(df_airports, flight_counts, left_on='ICAO', right_on='Org/Des', how='inner')

# --- 3. BUBBEL DIAGRAM (Alle vluchten) ---
st.title("Wereldwijde Vluchtactiviteit")
st.write("In dit overzicht zie je alle luchthavens uit het vliegschema.")

fig_bubbles = px.scatter_geo(
    df_map,
    lat='Latitude',
    lon='Longitude',
    size='Aantal_Vluchten',
    hover_name='Name',
    color='Aantal_Vluchten',
    color_continuous_scale='Plasma',
    projection="natural earth",
    title='Alle vluchten per luchthaven',
    labels={'Aantal_Vluchten': 'Aantal Vluchten'}
)

st.plotly_chart(fig_bubbles, use_container_width=True)

st.divider() # Een lijn tussen de twee grafieken

# --- 4. STAAF DIAGRAM (Top 10 hubs) ---
st.header("Top 10 Drukste Luchthavens")

# Filter de top 10 uit de al bestaande df_map
top_10_hubs = df_map.nlargest(10, 'Aantal_Vluchten')

fig_bar = px.bar(
    top_10_hubs, 
    x='Aantal_Vluchten', 
    y='Name', 
    orientation='h', 
    color='Aantal_Vluchten',
    color_continuous_scale='Viridis',
    labels={'Name': 'Luchthaven', 'Aantal_Vluchten': 'Totaal aantal vluchten'}
)

# Zorg dat de grootste staaf bovenaan staat
fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})

st.plotly_chart(fig_bar, use_container_width=True)


