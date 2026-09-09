from pydantic import BaseModel, Field
from typing import Any, Optional, List

class AgentResult(BaseModel):
    """Mandatory return boundary schema for all agent executions."""
    success: bool = Field(..., description="True if execution concluded with zero errors")
    data: Optional[Any] = Field(default=None, description="Response payload matching the target agent schema")
    error: Optional[str] = Field(default=None, description="System error summary trace if success is False")
    execution_time: float = Field(..., description="Calculated duration of execution in seconds")

class TeachingResponse(BaseModel):
    """Final system egress delivery structural payload contract."""
    answer: str = Field(..., description="The instructional answer text delivered to the student")
    summary: str = Field(..., description="A concise single-sentence distillation of the answer")
    key_points: List[str] = Field(..., description="Bullet points outlining essential takeaway terms")
    teaching_mode: str = Field(..., description="The dynamic strategy chosen by the Planner Agent")
    diagram_required: bool = Field(..., description="Flag stating if structural visuals are attached")
    video_required: bool = Field(..., description="Flag highlighting if supplemental media is attached")
    quiz_generated: bool = Field(..., description="Flag verifying that real-time questions are appended")
    confidence_score: float = Field(..., description="Calculated metric bounded between 0.0 and 1.0")
    expression: Optional[str] = Field(default="EXPRESSION_NOD", description="ROS2 expression code for hardware synchronization")

class QuizOption(BaseModel):
    key: str = Field(..., description="Option label (A, B, C, D)")
    text: str = Field(..., description="Text content of the option")

class QuizCardResponse(BaseModel):
    """Flag card quiz response structure delivered to user."""
    card_type: str = Field(default="flag_quiz_card", description="Identifies the card format")
    question_id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The question text generated dynamically using LLM and MongoDB data")
    options: List[QuizOption] = Field(..., description="List of 4 distinct multiple-choice options")
    correct_option: str = Field(..., description="Key of the correct option (A, B, C, or D)")
    explanation: str = Field(..., description="Detailed explanation of the correct answer")
    difficulty: str = Field(default="Medium", description="Difficulty level (Easy, Medium, Hard)")
    class_level: Optional[int] = Field(default=None, description="Class level context")
    subject: Optional[str] = Field(default=None, description="Subject context")

class QuizSetResponse(BaseModel):
    """Collection of multiple flag quiz cards."""
    card_type: str = Field(default="flag_quiz_card_set", description="Identifies the card set format")
    topic: str = Field(..., description="Quiz topic")
    subject: Optional[str] = Field(default=None, description="Subject context")
    class_level: Optional[int] = Field(default=None, description="Class level context")
    cards: List[QuizCardResponse] = Field(..., description="List of flag quiz cards")

class VideoScenePrompt(BaseModel):
    scene_number: int = Field(default=1, description="Sequence number of the scene")
    scene: Optional[int] = Field(default=None, description="Alias for scene_number")
    timestamp_start: str = Field(default="00:00", description="Start timestamp of the scene (e.g. 00:00)")
    timestamp_end: str = Field(default="00:15", description="End timestamp of the scene (e.g. 00:15)")
    duration_seconds: int = Field(default=15, description="Scene duration in seconds")
    shot_type: str = Field(default="Wide shot / 3D Animation", description="Camera angle or rendering style (e.g. Cinematic Close-up, 3D Render)")
    visual_prompt: str = Field(..., description="Detailed prompt description for AI Video generation LLM")
    action: Optional[str] = Field(default=None, description="Alias for visual_prompt")
    narration: str = Field(..., description="Class-appropriate voiceover transcript for the scene")
    script: Optional[str] = Field(default=None, description="Alias for narration")
    scene_explanation: str = Field(default="", description="Detailed breakdown of what occurs at this timestamp")

class VideoAgentResponse(BaseModel):
    """Structured response payload for video generation agent."""
    topic: str = Field(..., description="The core educational topic")
    class_level: int = Field(..., description="Target class grade level")
    video_title: str = Field(..., description="Catchy educational title for the video")
    concept_summary: str = Field(..., description="Overview of what the video explains")
    visual_style: str = Field(default="3D Pixar Educational Animation", description="Visual rendering style")
    visualStyle: Optional[str] = Field(default=None, description="CamelCase alias for visual_style")
    camera_motion: str = Field(default="Dynamic orbital pan with depth of field", description="Camera motion type")
    cameraMotion: Optional[str] = Field(default=None, description="CamelCase alias for camera_motion")
    total_duration_seconds: int = Field(default=60, description="Total video duration in seconds")
    structured_prompt: str = Field(..., description="Complete prompt payload passed to Video Generation LLM")
    masterPrompt: Optional[str] = Field(default=None, description="Alias for structured_prompt")
    scenes: List[VideoScenePrompt] = Field(..., description="Timestamped scene-by-scene script and visual generation prompts")
    video_url: Optional[str] = Field(default=None, description="Generated video URL or payload reference")


class AdaptiveLearningResponse(BaseModel):
    difficulty_level: str = Field(..., description="Beginner / Intermediate / Advanced")
    teaching_style: str = Field(..., description="Visual / Conceptual / Analogy-based / Active Learning")
    recommended_learning_path: List[str] = Field(..., description="List of subtopics for recommended learning path")

class PlannerResponse(BaseModel):
    need_quiz: bool = Field(False, description="Flag indicating if a quiz is needed")
    need_story: bool = Field(False, description="Flag indicating if explanation needs a story style")
    need_diagram: bool = Field(False, description="Flag indicating if explanation needs visual description")
    need_video: bool = Field(False, description="Flag indicating if an educational video script is needed")
    need_homework: bool = Field(False, description="Flag indicating if homework generation is needed")
    need_summary: bool = Field(False, description="Flag indicating if summary is needed")
    need_revision: bool = Field(False, description="Flag indicating if revision is needed")
    need_formula_sheet: bool = Field(False, description="Flag indicating if formula sheet is needed")
    need_example: bool = Field(False, description="Flag indicating if concrete examples are needed")
    teaching_strategy: str = Field(..., description="Overall description of the strategy chosen")
    execution_plan: List[str] = Field(..., description="Names of agents/steps to execute in sequence")

class AssessmentQuestion(BaseModel):
    question_id: str = Field(..., description="Unique question ID")
    type: str = Field(..., description="mcq / subjective / hots / case")
    question_text: str = Field(..., description="Text of the question")
    options: Optional[List[QuizOption]] = Field(default=None, description="Options for MCQs")
    correct_answer: str = Field(..., description="Correct answer text or option key")
    explanation: str = Field(..., description="pedagogical explanation")
    difficulty: str = Field(default="Medium", description="Easy / Medium / Hard")

class AssessmentResponse(BaseModel):
    questions: List[AssessmentQuestion] = Field(..., description="List of assessment questions generated")
    score: Optional[float] = Field(default=None, description="Score if evaluated")
    weak_topics: Optional[List[str]] = Field(default=None, description="Weak topics identified")
    suggested_reading: Optional[List[str]] = Field(default=None, description="Recommended reading topics")
    revision_plan: Optional[str] = Field(default=None, description="Custom revision guidance")

class InteractiveClassroomResponse(BaseModel):
    game_mode: str = Field(..., description="Quiz Mode / Rapid Fire / Science Quiz etc.")
    timer_seconds: int = Field(default=30, description="Recommended timer for current turn")
    score: int = Field(default=0, description="Current score")
    leaderboard: Optional[List[dict]] = Field(default=None, description="Rankings list")
    hints: List[str] = Field(default=[], description="Hints to assist the student")
    game_payload: Any = Field(default=None, description="Dynamic payload for the game state")

class ContentGenerationResponse(BaseModel):
    material_type: str = Field(..., description="lesson notes / handouts / homework / worksheet / flashcard / mindmap")
    format: str = Field(..., description="markdown / html / pdf / ppt")
    content: str = Field(..., description="Text content or representation of the material")
    file_path: Optional[str] = Field(default=None, description="Location where generated file is stored")

class EndOfClassSummaryResponse(BaseModel):
    topics_covered: List[str] = Field(..., description="List of topics taught")
    key_concepts: List[str] = Field(..., description="Summary of key concepts")
    formula_revision: Optional[List[str]] = Field(default=None, description="Formula equations sheet")
    interesting_fact: str = Field(..., description="Interesting hook fact")
    quote_of_day: str = Field(..., description="Motivational quote")
    homework: List[str] = Field(..., description="Assigned exercises")
    next_topic: str = Field(..., description="Suggested next lesson topic")

class AnalyticsResponse(BaseModel):
    subject: str = Field(..., description="Subject domain")
    grade: int = Field(..., description="Class grade level")
    questions_asked: int = Field(default=0, description="Total queries handled")
    average_difficulty: str = Field(default="Medium", description="Calculated avg difficulty")
    weak_topics: List[str] = Field(default=[], description="List of struggle areas")
    topic_statistics: dict = Field(default={}, description="Frequencies of asked topics")
    student_analytics: Optional[dict] = Field(default=None, description="Personal student mastery details")

def get_content_str(x: Any) -> str:
    """Safely extracts raw text string from a message object, dictionary, or string input."""
    if not x:
        return ""
    if isinstance(x, str):
        return x
    
    # Try dictionary-like access
    content = ""
    if isinstance(x, dict):
        content = x.get("content", "")
    else:
        content = getattr(x, "content", "")

    if isinstance(content, list):
        res = []
        for item in content:
            if isinstance(item, str):
                res.append(item)
            elif hasattr(item, "text"):
                val = getattr(item, "text", "")
                res.append(val if isinstance(val, str) else str(val))
            elif isinstance(item, dict):
                res.append(str(item.get("text", "")))
        return "".join(res)
    return str(content)
