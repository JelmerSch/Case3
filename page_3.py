import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Pagina configuratie
st.set_page_config(page_title="Airport Insights Dashboard", layout="wide")

# Functie om data in te laden (gecached voor snelheid)
@st.cache_data
def load_data():
    # Inladen met de juiste delimiters
    schedule = pd.read_csv('schedule_airport.csv')
    airports = pd.read_csv('airports-extended-clean.csv', sep=';')

    # Coördinaten opschonen
    airports['Latitude'] = airports['Latitude'].str.replace(',', '.').astype(float)
    airports['Longitude'] = airports['Longitude'].str.replace(',', '.').astype(float)

    # Datums en tijden combineren
    schedule['Scheduled_DT'] = pd.to_datetime(schedule['STD'] + ' ' + schedule['STA_STD_ltc'], dayfirst=True)
    schedule['Actual_DT'] = pd.to_datetime(schedule['STD'] + ' ' + schedule['ATA_ATD_ltc'], dayfirst=True)

    # Vertraging berekenen
    schedule['Delay_min'] = (schedule['Actual_DT'] - schedule['Scheduled_DT']).dt.total_seconds() / 60
    
    # Mergen
    df = schedule.merge(airports[['ICAO', 'Name', 'City', 'Country']], 
                        left_on='Org/Des', right_on='ICAO', how='left')
    
    # Maand en Dag toevoegen
    df['Month_str'] = df['Scheduled_DT'].dt.to_period('M').astype(str)
    df['Day_of_Week'] = df['Scheduled_DT'].dt.day_name()
    
    return df

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

# Tabs voor verschillende analyses
tab1, tab2, tab3 = st.tabs(["📊 Volumes", "⏰ Vertragingen", "🛩️ Vloot & Bestemmingen"])

    with tab1:
    st.header("Vluchtvolumes")
    
    col_a, col_b = st.columns(2)
    
        with col_a:
        st.subheader("Volume per Maand")
        fig_vol = plt.figure(figsize=(10, 5))
        monthly_data = display_df.groupby('Month_str').size()
        plt.plot(monthly_data.index, monthly_data.values, marker='o', color='teal')
        plt.xticks(rotation=45)
        plt.ylabel("Aantal vluchten")
        st.pyplot(fig_vol)

        with col_b:
        st.subheader("Volume per Dag")
        fig_day = plt.figure(figsize=(10, 5))
        order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_data = display_df['Day_of_Week'].value_counts().reindex(order)
        sns.barplot(x=day_data.index, y=day_data.values, palette='coolwarm')
        plt.xticks(rotation=45)
        st.pyplot(fig_day)

    with tab2:
    st.header("Vertragingsanalyse")
    
    st.subheader("Verdeling van Vertragingen (tot 120 min)")
    fig_hist = plt.figure(figsize=(10, 4))
    sns.histplot(display_df[(display_df['Delay_min'] > 0) & (display_df['Delay_min'] < 120)]['Delay_min'], 
                 bins=40, kde=True, color='purple')
    plt.xlabel("Minuten te laat")
    st.pyplot(fig_hist)

    st.subheader("Gemiddelde Vertraging
