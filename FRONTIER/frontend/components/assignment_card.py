import streamlit as st


def assignment_card(title, due, source, priority):

    colors = {
        "High": "🔴",
        "Medium": "🟠",
        "Low": "🟢"
    }

    icon = colors.get(priority, "🔵")

    with st.container(border=True):

        col1, col2 = st.columns([5, 1])

        with col1:
            st.subheader(f"📄 {title}")

        with col2:
            st.write(f"### {icon}")

        col3, col4, col5 = st.columns(3)

        with col3:
            st.markdown("**📅 Deadline**")
            st.write(due)

        with col4:
            st.markdown("**📚 Source**")
            st.write(source)

        with col5:
            st.markdown("**🔥 Priority**")
            st.write(priority)