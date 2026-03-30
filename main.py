from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
import operator


# Defining GraphState
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_profile: str
    raw_syllabus: str
    monthly_milestones: str
    study_resources: str
    current_schedule: str
    mock_test_results: str
    weak_areas: str


# Initializing LLM
load_dotenv()
llm = ChatGoogleGenerativeAI(model = "gemini-2.5-flash")

# Defining Pydantic Functions 

class UserIntakeData(BaseModel):
    exam: str = Field(description="The exam name of the target exam, e.g., GATE CS 2026")
    timeframe: Optional[int] = Field(description="Months remaining until the exam")

class MonthMilestone(BaseModel):
    month_number: int = Field(description="The month sequence (1,2,3...)")
    focus_topics: List[str] = Field(description="Key topics to cover this month")
    expected_outcone: str = Field(description="What the user should master by month's end")

class SyllabusPlan(BaseModel):
    plan: List[MonthMilestone] = Field(description="The complete month-by-month study plan")

class ResourceItem(BaseModel):
    topic: str = Field(description="The specific syllabus topic")
    recommended_book: str = Field(description="Title of the best textbook for this topic")
    video_lecture_query: str = Field(description="Exact YouTube search query to find lectures")
    practice_platform: str = Field(description="Where to find mock tests for this")

class ResourcePlan(BaseModel):
    resources: List[ResourceItem] = Field(description="List of resources mapped to current milestones")

class DailyTask(BaseModel):
    day: str = Field(description="Day of the week (e.g., Monday)")
    topics_to_study: List[str] = Field(description="What to read/watch today")
    practice_required: bool = Field(description="Whether the users needs to do a mock test today")

class WeeklySchedule(BaseModel):
    week_plan: List[DailyTask] = Field(description="The 7-day study schedule")


class EvaluationResult(BaseModel):
    weak_topic: List[str] = Field(description="Topics the user scored poorly on")
    needs_reroute: bool = Field(description="True if the schedule needs a major adjustment, False if they are on track")
    feedback_summary: str = Field(description="A brief encouraging summary of their performance")



# Defining Prompt Templates
input_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are the intake strategist for a long-term competitive exam planner. "
    "Your job is to extract the exact name of the exam the user wants to take and the timeframe they have to prepare."
    "If the timeframe is not explicitly stated, make a logical guess based on standard prep times for that exam, or return null."),
    ("human", "User Input: {user_text}")
])

syllabus_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert academic strategist specializing in massive, high-stakes exams."
    "Your task is to take a raw, unstructured syllabus and break it down into a logical chronological month-by-month study plan."
    "Crucial Rules: \n"
    "1. Always schedule foundational prerequisites before advanced topic.\n"
    "2. Group logically related topics together within the same month.\n"
    "3. Ensure the final month includes dedicated time for full-length mock exams."),
    ("human", "User Profile: {profile}\n\nRaw Syllabus:\n{syllabus}")
])

resource_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an educational resource librarian. Your job is to look at a student's upcoming study milestones and recommend the absolute best study materials."
    "Provide specific, highly-rated textbook titles, exact YouTube search queries"
    "(e.g., 'Laplace Transforms engineering mathematics full lecture' or 'Data Structures arraw practice'), and name specific platform for mock tests."),
    ("human", "Current Milestones: \n{milestones}")
])

scheduler_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are strict but realistic study schedule coordinator. Based on the user's monthly milestones and available resources, generate a highly specific 7-day weekly timetable."
    "Rules:\n"
    "1. Balance reading textbooks, watching lectures, and doing practice problems.\n"
    "2. Do not overload the student; keep daily tasks focused on 1 or 2 core topics.\n"
    "3. Assign at least one day for revision or a mock test."),
    ("human", "User Profile: {profile}\n\nCurrent Milestones:\n{milestones}\n\nStudy Resources:\n{resources}")
])

evaluator_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an analytical academic tutor, Read the student's recent status report or mock test results and compare it against their current schedule."
    "Your task is to objective identify exactly which specific topics they are struggling with."
    "Provide a brief, encouraging summary, but clearly isolate the 'weak areas' that require immediate revision."
    "If they are doing well, state that no rerouting is needed."),
    ("human", "Current Active Schedule:\n{current_schedule}\n\nStudent's Progress Report:\n{user_report}")
])

router_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an adaptive academic planner. The student has taken a mock test and identified specific weak areas that they are failing."
    "Your task is to rewrite their upcoming monthly milestones. You must inject dedicated revision blocks for these weak areas into the upcoming month WITHOUT completely derailing their long-term timeline."
    "Condense or shift future topics slightly to make room for this critical revision."),
    ("human", "Identified Weak Areas:\n{weak_areas}\n\nCurrent Monthly Milestones:\n{current_milestones}")
])


# Agents to build

def node_intake_user(state: AgentState):
    if not state.get("messages"):
        return state
    user_input = state["messages"][-1].content

    structured_llm = llm.with_structured_output(UserIntakeData)

    chain = input_prompt | structured_llm
    extracted_data = chain.invoke({"user_text": user_input})

    profile_string = f"Exam: {extracted_data.exam}, Timeframe: {extracted_data.timeframe}"

    return{
        "user_profile": profile_string,
    }

def node_syllabus_planner(state: AgentState):
    profile = state.get("user_profile","")

    raw_syllabus = state.get("raw_syllabus", "Standard CS Syllabus: DSA, OS, DB, etc.")

    structured_llm = llm.with_structured_output(SyllabusPlan)

    chain = syllabus_prompt | structured_llm
    extracted_plan = chain.invoke({"profile": profile,"syllabus": raw_syllabus})

    milestones_str = extracted_plan.model_dump_json()

    return{
        "monthly_milestones": milestones_str,
    }

def node_resource_gatherer(state: AgentState):
    milestones = state.get("monthly_milestones","")

    structured_llm = llm.with_structured_output(ResourcePlan)

    chain = resource_prompt | structured_llm
    extracted_resources = chain.invoke({"milestones": milestones})

    return{
        "study_resources": extracted_resources.model_dump_json()
    }

def node_dynamic_scheduler(state: AgentState):
    milestones = state.get("monthly_milestones", "")
    resources = state.get("study_resources","")
    profile = state.get("user_profile","")

    structured_llm = llm.with_structured_output(WeeklySchedule)

    chain = scheduler_prompt | structured_llm
    schedule = chain.invoke({
        "milestones": milestones,
        "resources": resources,
        "profile": profile
    })

    return{
        "current_schedule": schedule.model_dump_json()
    }

def node_evaluate_progress(state: AgentState):
    if not state.get("messages"):
        return state
    user_report = state["messages"][-1].content
    current_schedule = state.get("current_schedule","")

    structured_llm = llm.with_structured_output(EvaluationResult)

    chain = evaluator_prompt | structured_llm
    evaluation = chain.invoke({
        "user_report": user_report,
        "current_schedule": current_schedule
    })

    return{
        "weak_areas": ", ".join(evaluation.weak_topics),
        "mock_test_results": evaluation.model_dump_json()
    }

def node_re_router(state: AgentState):
    weak_areas = state.get("weak_areas","")
    current_milestones = state.get("monthly_milestones","")

    if not weak_areas:
        return state
    
    structured_llm = llm.with_structured_output(SyllabusPlan)

    chain = router_prompt | structured_llm
    updated_plan = chain.invoke({
        "weak_areas": weak_areas,
        "current_milestones": current_milestones
    })

    return{
        "monthly_milestones": updated_plan.model_dump_json()
    }

def route_start(state: AgentState):

    if not state.get("user_profile"):
        return "new_setup"
    
    return "progress_update"
    

def should_reroute(state: AgentState):
    weak_areas = state.get("weak_areas", "")

    if weak_areas:
        return "needs_rerouting"
    
    return "on_track"


# Defining Workflow
workflow = StateGraph(AgentState)

workflow.add_node("intake", node_intake_user)
workflow.add_node("planner", node_syllabus_planner)
workflow.add_node("gatherer", node_resource_gatherer)
workflow.add_node("scheduler", node_dynamic_scheduler)
workflow.add_node("evaluator", node_evaluate_progress)
workflow.add_node("router", node_re_router)

workflow.add_conditional_edges(
    START,
    route_start,
    {
        "new_setup": "intake",
        "progress_update": "evaluator"
    }
)

workflow.add_edge("intake","planner")
workflow.add_edge("planner","gatherer")
workflow.add_edge("gatherer","scheduler")

workflow.add_conditional_edges(
    "evaluator",
    should_reroute,
    {
        "needs_rerouting": "router",
        "on_track": "scheduler"
    }
)

workflow.add_edge("router", "scheduler")
workflow.add_edge("scheduler", END)

memory = MemorySaver()

app = workflow.compile(checkpointer=memory)

