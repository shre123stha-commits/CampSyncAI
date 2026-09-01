import streamlit as st

def planner_cards():

    st.markdown("## 🤖 AI Study Planner")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader("📘 Today's Study Plan")
            st.write("Generate today's study plan without timings.")

            if st.button("Generate", key="today"):
                st.session_state.current_page = "today"
                st.rerun()

    with col2:
        with st.container(border=True):
            st.subheader("⏰ Today's Plan with Timings")
            st.write("Generate today's study plan using free slots.")

            if st.button("Generate", key="today_timed"):
                st.session_state.current_page = "today_timed"
                st.rerun()

    col3, col4 = st.columns(2)

    with col3:
        with st.container(border=True):
            st.subheader("📅 Weekly Study Plan")
            st.write("Generate a weekly study plan.")

            if st.button("Generate", key="week"):
                st.session_state.current_page = "week"
                st.rerun()

    with col4:
        with st.container(border=True):
            st.subheader("🗓 Weekly Plan with Timings")
            st.write("Generate a weekly timetable-based plan.")

            if st.button("Generate", key="week_timed"):
                st.session_state.current_page = "week_timed"
                st.rerun()