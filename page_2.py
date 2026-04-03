import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

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

st.divider

# 1. Definieer de coordinaten van de thuisbasis (Schiphol: 52.31, 4.76)
HOME_LAT = 52.3086
HOME_LON = 4.7639

# 2. Haal de coordinaten van de bestemmingen op uit de airport-lijst
# We maken een hulp-dataframe met alleen de nodige info
df_coords = df_airports[['ICAO', 'Latitude', 'Longitude']].drop_duplicates()

# 3. Voeg de coordinaten toe aan het vluchtschema
df_schedule = pd.merge(df_schedule, df_coords, left_on='Org/Des', right_on='ICAO', how='left')

# 4. Functie om de afstand (Haversine) te berekenen in km
def haversine(lat1, lon1, lat2, lon2):
    R = 6371 # Straal van de aarde
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# 5. Bereken de afstand voor elke vlucht
df_schedule['Distance_km'] = haversine(HOME_LAT, HOME_LON, df_schedule['Latitude'], df_schedule['Longitude'])

# 6. Voeg de kolom 'Flight_Type' toe op basis van jouw parameters
def categorize_flight(dist):
    if dist < 1500:
        return 'Short-haul'
    elif 1500 <= dist <= 4000:
        return 'Medium-haul'
    elif dist > 4000:
        return 'Long-haul'
    else:
        return 'Unknown'

df_schedule['Flight_Type'] = df_schedule['Distance_km'].apply(categorize_flight)

# Controleer het resultaat
st.write(df_schedule[['FLT', 'Org/Des', 'Distance_km', 'Flight_Type']].head())




