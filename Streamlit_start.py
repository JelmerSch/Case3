import streamlit as st

st.set_page_config(layout="wide", page_title="vlucht data analyse")

dashboard = st.Page("Startdash.py", title="Startpagina",                     icon=":material/dashboard:")
page_1    = st.Page("page_2.py",   title="Wereldwijde Vluchtactiviteit",     icon=":material/article:")
page_2    = st.Page("page_3.py",   title="Airport Operations",               icon=":material/article:")
page_3    = st.Page("page_4.py",   title="Vertragingsanalyse",               icon=":material/article:")
page_4    = st.Page("page_1.py",   title="Vliegtuig route",                  icon=":material/article:")

pg = st.navigation([dashboard, page_1, page_2, page_3, page_4])
pg.run()
