import streamlit as st

def action_buttons():

    st.markdown("## 📅 Generate Study Plan")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📘 Today's Study Plan", use_container_width=True):
            st.session_state.current_page = "today"

    with col2:
        if st.button("⏰ Today's Plan with Timings", use_container_width=True):
            st.session_state.current_page = "today_timed"

    col3, col4 = st.columns(2)

    with col3:
        if st.button("🗓 Weekly Study Plan", use_container_width=True):
            st.session_state.current_page = "week"

    with col4:
        if st.button("📅 Weekly Plan with Timings", use_container_width=True):
            st.session_state.current_page = "week_timed"