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
            </style>)
            """, unsafe_allow_html=True)

st.title("PrepGraph AI - A Multi-Agent Exam Strategist")
st.markdown("Autonomously generate, resource, and dynamically adjust your long-term study timeline.")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "graph_state" not in st.session_state:
    st.session_state.graph_state = None

with st.sidebar:
    st.header("Target Setup")

    exam_name = st.text_input("Target Exam", value = "GATE CS 2026")
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

    tab1, tab2, tab3, tab4 = st.tabs(["Milestones", "Resources", "Weekly Schedule", "Progress & Rerouting"])

    with tab1:
        st.subheader("Monthly Syllabus Plan")
        if state.get("monthly_milestones"):

            milestones = json.loads(state["monthly_milestones"])
            st.json(milestones)

    with tab2:
        st.subheader("Curated Study Materials")
        if state.get("study_resources"):
            resources = json.loads(state["study_resources"])
            st.json(resources)

    with tab3:
        st.subheader("Dynamic 7-Day Timetable")
        if state.get("current_schedule"):
            schedule = json.loads(state["current_schedule"])
            st.json(schedule)

    with tab4:
        st.subheader("Submit Mock Test Results")
        st.info("Input your recent scores. The Evaluator agent will analyze your weak area, and the Router agent will adjust your milestones if necessary")

        test_feedback = st.text_area("How did you recent mock test go?",
                                     placeholder="e.g., Scored 65/100. Great in OS, but struggled heavily with Data Structures and Calculus.")
        
        if st.button("Evaluate & Reroute"):
            with st.spinner("Analyzing progress and rerouting timeline..."):
                update_input = {"messages": [("user", test_feedback)]}
                config = {"configurable": {"thread_id": st.session_state.thread_id}}

                for event in workflow_app.stream(update_input, config = config):
                    pass

                st.session_state.graph_state = workflow_app.get_state(config).values
                st.success("Analysis complete! Check the updated Milestones and Schedule tabs.")
                st.rerun()

else:
    st.info("Please configure your target in the sidebar to generate your initial plan.")