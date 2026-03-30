import streamlit as st
import uuid
import json
from main import app as workflow_app

st.set_page_config(
    page_title="AI Exam Strategist",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
            <style>
            .stButton>button {
            width:100%;
            border-radius: 5px;
            font-weight: bold;
            }
            </style>
            """, unsafe_allow_html=True)

st.title("PrepGraph AI - A Multi-Agent Exam Strategist")
st.markdown("Autonomously generate, resource, and dynamically adjust your long-term study timeline.")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "graph_state" not in st.session_state:
    st.session_state.graph_state = None

with st.sidebar:
    st.header("Target Setup")

    exam_name = st.text_input("Target Exam", value = "GATE CS 2027")
    timeframe = st.number_input("Months to Prepare", min_value=1, max_value=24, value=8)
    hours_week = st.slider("Study Hours per Week", 5, 80, 20)

    if st.button("Generate Master Plan", type = "primary"):
        with st.spinner("Agents are drafting you strategy..."):
            initial_input = {
                "messages": [("user", f"I want to crack {exam_name} in {timeframe} months. I can study {hours_week} hours a week.")]
            }          
            config = {"configurable": {"thread_id": st.session_state.thread_id}}

            for event in workflow_app.stream(initial_input, config = config):
                pass

            st.session_state.graph_state = workflow_app.get_state(config).values
            st.success("Plan Generated!")

if st.session_state.graph_state:
    state = st.session_state.graph_state

    tab1, tab2, tab3, tab4 = st.tabs(["Milestones", "Resources", "Weekly Schedule", "Daily Check-in"])

    with tab1:
        st.subheader("Monthly Syllabus Plan")
        if state.get("monthly_milestones"):

            milestones = json.loads(state["monthly_milestones"]).get("plan",[])
            
            for m in milestones:
                month_num = m.get('month_number','?')
                outcome = m.get('expected_outcome', 'Core focus for this month')
                topics = m.get('focus_topics', [])

                with st.expander(f"Month {month_num}: {outcome}"):
                    st.markdown("**Focus Topics:**")
                    for topic in topics:
                        st.markdown(f"- {topic}")

    with tab2:
        st.subheader("Curated Study Materials")
        if state.get("study_resources"):
            resources = json.loads(state["study_resources"]).get("resources",[])

            for res in resources:
                with st.container():
                    st.markdown(f"### {res['topic']}")
                    st.markdown(f" **Book:** {res['recommended_book']}")
                    st.markdown(f"🌐 **Link: ** [{res['resource_link']}]({res['resource_link']})")
                    st.markdown(f" **Practice:** {res['practice_platform']}")
                    st.divider()

    with tab3:
        st.subheader("Dynamic 7-Day Timetable")
        if state.get("current_schedule"):
            schedule = json.loads(state["current_schedule"]).get("week_plan", [])

            for day in schedule:
                with st.expander(f" {day['day']}", expanded = True):
                    for topic in day['topics_to_study']:
                        st.checkbox(f"Study: {topic}", key=f"{day['day']}_{topic}")
                    if day['practice_required']:
                        st.warning("Practice Mock Test Required Today!")

    with tab4:
        st.subheader("Daily Progress & Tracker")
        st.info("Log your daily study progress or submit a mock test score. The AI will analyze your update and reroute your milestones if you are falling behind.")

        update_type = st.radio("What are you logging today?", ["Daily Study Progress", "Mock Test Results"])

        if update_type == "Daily Study Progress":
            test_feedback = st.text_area("What did you study today? Did you struggle with anything?",
                                        placeholder="e.g., Completed the Digital Logic module. Graph theory is still confusing.")
        else:
            test_feedback = st.text_area("Mock Test Score & Weak Areas:",
                                        placeholder="e.g., Scored 45/100. Failed all the probability questions.")
        
        if st.button("Submit Update & Analyze"):
            with st.spinner("Analyzing progress and rerouting timeline..."):
                update_input = {"messages": [("user",f"[{update_type}] {test_feedback}")]}
                config = {"configurable": {"thread_id": st.session_state.thread_id}}

                for event in workflow_app.stream(update_input, config = config):
                    pass

                st.session_state.graph_state = workflow_app.get_state(config).values
                st.success("Analysis complete! Check the updated Milestones and Schedule tabs for any adjustments.")
                st.rerun()

else:
    st.info("Please configure your target in the sidebar to generate your initial plan.")