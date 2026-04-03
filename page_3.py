import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. DATA LADEN EN VOORBEREIDEN
# Inladen met de juiste delimiters
schedule = pd.read_csv('schedule_airport.csv')
airports = pd.read_csv('airports-extended-clean.csv', sep=';')

# Coördinaten opschonen (komma naar punt)
airports['Latitude'] = airports['Latitude'].str.replace(',', '.').astype(float)
airports['Longitude'] = airports['Longitude'].str.replace(',', '.').astype(float)

# Datums en tijden combineren en omzetten naar datetime objecten
schedule['Scheduled_DT'] = pd.to_datetime(schedule['STD'] + ' ' + schedule['STA_STD_ltc'], dayfirst=True)
schedule['Actual_DT'] = pd.to_datetime(schedule['STD'] + ' ' + schedule['ATA_ATD_ltc'], dayfirst=True)

# Vertraging berekenen in minuten
schedule['Delay_min'] = (schedule['Actual_DT'] - schedule['Scheduled_DT']).dt.total_seconds() / 60

# Datasets samenvoegen op basis van ICAO code
df_merged = schedule.merge(airports[['ICAO', 'Name', 'City', 'Country']], 
                           left_on='Org/Des', right_on='ICAO', how='left')

# Instellingen voor de stijl van de grafieken
sns.set_theme(style="whitegrid")

# 2. VISUALISATIE: TOP 10 LANDEN (VOLUME)
top_countries = df_merged['Country'].value_counts().head(10)
plt.figure(figsize=(10, 6))
sns.barplot(x=top_countries.values, y=top_countries.index, palette='viridis')
plt.title('Top 10 Bestemmingen/Herkomst landen')
plt.xlabel('Aantal vluchten')
plt.ylabel('Land')
plt.tight_layout()
plt.show()

# 3. VISUALISATIE: GEMIDDELDE VERTRAGING PER LAND
# We kijken alleen naar vluchten met een positieve vertraging
delays = df_merged[df_merged['Delay_min'] > 0]
avg_delay_country = delays.groupby('Country')['Delay_min'].mean().reindex(top_countries.index)

plt.figure(figsize=(10, 6))
sns.barplot(x=avg_delay_country.values, y=avg_delay_country.index, palette='magma')
plt.title('Gemiddelde Vertraging per Land (Top 10 volumes)')
plt.xlabel('Gemiddelde vertraging (minuten)')
plt.ylabel('Land')
plt.tight_layout()
plt.show()

# 4. VISUALISATIE: MAANDELIJKS VLUCHTVOLUME (TIJDLIJN)
df_merged['Month_dt'] = df_merged['Scheduled_DT'].dt.to_period('M').astype(str)
monthly_flights = df_merged.groupby('Month_dt').size()

plt.figure(figsize=(12, 6))
monthly_flights.plot(kind='line', marker='o', color='teal', linewidth=2)
plt.title('Aantal vluchten per maand (2019-2020)')
plt.xlabel('Maand')
plt.ylabel('Aantal vluchten')
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.show()

# 5. VISUALISATIE: DRUKSTE DAGEN VAN DE WEEK
df_merged['Day_of_Week'] = df_merged['Scheduled_DT'].dt.day_name()
order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
day_volume = df_merged['Day_of_Week'].value_counts().reindex(order)

plt.figure(figsize=(10, 6))
sns.barplot(x=day_volume.index, y=day_volume.values, palette='coolwarm')
plt.title('Vluchtvolume per Dag van de Week')
plt.xlabel('Dag')
plt.ylabel('Aantal vluchten')
plt.tight_layout()
plt.show()

# 6. VISUALISATIE: DISTRIBUTIE VAN VERTRAGINGEN
plt.figure(figsize=(10, 6))
# Filter op vertragingen tot 2 uur voor een duidelijk beeld
sns.histplot(delays[delays['Delay_min'] < 120]['Delay_min'], bins=30, kde=True, color='purple')
plt.title('Verdeling van Vertragingen (Vluchten < 2 uur vertraging)')
plt.xlabel('Minuten vertraging')
plt.ylabel('Aantal vluchten')
plt.tight_layout()
plt.show()
