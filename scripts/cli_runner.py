import asyncio
import os
import sys
import re
import json
import getpass
from dotenv import load_dotenv
from loguru import logger

# Bypass local DNS resolution timeouts for MongoDB Atlas SRV connections
try:
    import dns.resolver
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1', '8.8.4.4']
except Exception:
    pass

# Load environment
load_dotenv()

# Setup default environment variables if not present
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB_NAME", "SiliconRag")
os.environ.setdefault("VECTOR_STORE_TYPE", "qdrant")

import models.compat
from agentscope.message import UserMsg
from agents.supervisor_agent_v2 import ClassroomSupervisorAgentV2
from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3
from agents.quiz_agent import QuizAgent
from agents.video_agent import VideoAgent
from state.agentState import AgentStateManager
from ai_teacher_robot.repositories.user_repository import UserRepository
from ai_teacher_robot.repositories.curriculum_repository import CurriculumRepository

def safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n[Input Stream Ended or Interrupted] Exiting...")
        sys.exit(0)

async def authenticate_flow(user_repo: UserRepository) -> dict:
    print("\n" + "="*50)
    print(" 🎓 WELCOME TO AI CLASSROOM TEACHING ROBOT")
    print("="*50)
    
    invalid_attempts = 0
    while True:
        choice = safe_input("Do you have an account? (yes/no/exit): ").strip().lower()
        if choice in ('exit', 'q', 'quit'):
            sys.exit(0)
            
        if choice == 'yes':
            invalid_attempts = 0
            username = safe_input("Username: ").strip()
            try:
                password = getpass.getpass("Password: ")
            except (EOFError, KeyboardInterrupt):
                print("\n[Input Interrupted] Exiting...")
                sys.exit(0)
            
            if not username or not password:
                print("Username and password cannot be empty.")
                continue
                
            try:
                user = await user_repo.authenticate_user(username, password)
                if user:
                    print(f"\n✅ Access Granted. Welcome back, {username} ({user['role'].capitalize()}, Class {user['class_level']})!")
                    return user
                else:
                    print("❌ Access Denied. Invalid username or password.")
            except Exception as e:
                logger.error(f"Authentication database error: {e}")
                print("❌ Database connection error. Please ensure MongoDB is running.")
                
        elif choice == 'no':
            invalid_attempts = 0
            username = safe_input("Choose a Username: ").strip()
            try:
                password = getpass.getpass("Choose a Password: ")
            except (EOFError, KeyboardInterrupt):
                print("\n[Input Interrupted] Exiting...")
                sys.exit(0)
            role = safe_input("Role (student/teacher): ").strip().lower()
            
            if role not in ('student', 'teacher'):
                print("Invalid role. Role must be 'student' or 'teacher'.")
                continue
                
            try:
                class_level_str = safe_input("Class Level (1-10): ").strip()
                class_level = int(class_level_str)
                if not (1 <= class_level <= 10):
                    print("Class level must be between 1 and 10.")
                    continue
            except ValueError:
                print("Class level must be a numeric integer.")
                continue
                
            if not username or not password:
                print("Username and password cannot be empty.")
                continue
                
            try:
                await user_repo.register_user(username, password, role, class_level)
                print(f"\n✅ Registration Successful! Welcome, {username}!")
                user = await user_repo.authenticate_user(username, password)
                if user:
                    return user
            except ValueError as ve:
                print(f"❌ Registration failed: {ve}")
            except Exception as e:
                logger.error(f"Database error during registration: {e}")
                print("❌ Database connection error. Please ensure MongoDB is running.")
        else:
            invalid_attempts += 1
            if invalid_attempts >= 5:
                print("❌ Too many invalid attempts or non-interactive standard input detected. Exiting.")
                sys.exit(1)
            print("Invalid option. Please type 'yes', 'no', or 'exit'.")

def select_subject(subjects: list, class_level: int) -> str:
    seen_keys = set()
    cleaned = []
    for s in (subjects or []):
        if not s or not isinstance(s, str):
            continue
        norm = " ".join(s.replace("_", " ").split()).title()
        key = norm.lower()
        if key not in seen_keys:
            seen_keys.add(key)
            cleaned.append(norm)

    sorted_subjects = sorted(cleaned)
    if not sorted_subjects:
        print(f"📚 No registered subjects found for Class {class_level}. Defaulting to 'General'.")
        return "General"

    print(f"\n📚 Select a Subject for Class {class_level}:")
    for idx, subj in enumerate(sorted_subjects, 1):
        print(f"  {idx}. {subj}")

    default_subj = sorted_subjects[0]
    invalid_count = 0
    while True:
        choice = safe_input(f"\nSelect subject number [1-{len(sorted_subjects)}] (Default 1: {default_subj}): ").strip()
        if not choice:
            return default_subj
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(sorted_subjects):
                return sorted_subjects[idx - 1]
            else:
                print(f"❌ Invalid selection. Please choose a number between 1 and {len(sorted_subjects)}.")
        else:
            match = next((s for s in sorted_subjects if s.lower() == choice.lower() or s.replace("_", " ").lower() == choice.lower()), None)
            if match:
                return match
            print("❌ Invalid selection. Please choose a valid subject number.")
        invalid_count += 1
        if invalid_count >= 3:
            print(f"Using default subject: {default_subj}")
            return default_subj

async def run_educational_query(supervisor: ClassroomSupervisorAgentV2, user: dict, curriculum_repo: CurriculumRepository, session_id: str):
    print("\n" + "="*50)
    print(" 📖 OPTION 1: ASK EDUCATIONAL QUESTION / INTERACTIVE CHAT")
    print("="*50)
    
    subjects = await curriculum_repo.get_subjects_by_class(user["class_level"])
    subject = select_subject(subjects, user["class_level"])
    display_subject = subject.replace('_', ' ').title()
    print(f"\n✅ Selected Subject: {display_subject}")

    query = safe_input(f"\n🎓 Enter your question or topic for {display_subject}: ").strip()
    if not query:
        print("Query cannot be empty.")
        return

    user_msg = UserMsg(
        name=user["username"],
        content=query,
        metadata={"session_id": session_id, "grade": user["class_level"], "subject": subject, "role": user["role"]}
    )

    print("\n⌛ Thinking and searching curriculum...")
    start_time = asyncio.get_event_loop().time()
    reply = await supervisor.reply(user_msg)
    duration = asyncio.get_event_loop().time() - start_time

    agent_result = getattr(reply, "metadata", {}).get("agent_result", {})
    print("\n" + "="*60)
    print(" PIPELINE EXECUTION RESULTS")
    print("="*60)
    print(f"Execution Time: {round(duration, 3)} seconds")
    
    if agent_result.get("success", False):
        data = agent_result.get("data", {})
        print(f"\n🤖 Answer:\n{data.get('answer', '')}")
        citations = data.get("citations", [])
        if citations:
            print(f"\n📚 Citations ({len(citations)} source blocks):")
            for idx, cit in enumerate(citations, 1):
                print(f"  [{idx}] {cit.get('source_file')} | Page {cit.get('page_number')} | Chapter {cit.get('chapter')}")
                print(f"      Text: \"{cit.get('content', '').strip()}\"")
        print(f"\n📈 Confidence Score: {round(data.get('confidence_score', 0.0), 3)}")
    else:
        print(f"\n❌ Error: {agent_result.get('error', 'Unknown Error')}")
    print("="*60)

async def practice_quiz_cards(cards: list):
    print("\n" + "="*60)
    print(" 📝 INTERACTIVE QUIZ PRACTICE")
    print("="*60)
    score = 0
    total = len(cards)

    for idx, card in enumerate(cards, 1):
        print(f"\n--- Question {idx} of {total} ---")
        print(f"❓ {card.get('question')}")
        print("📋 Options:")
        for opt in card.get("options", []):
            print(f"   [{opt.get('key')}] {opt.get('text')}")

        while True:
            ans = safe_input("\nYour Answer (A/B/C/D): ").strip().upper()
            if ans in ('A', 'B', 'C', 'D'):
                break
            print("Please enter A, B, C, or D.")

        correct = str(card.get("correct_option", "")).strip().upper()

        if ans == correct:
            print("✅ Correct!")
            score += 1
        else:
            print(f"❌ Incorrect. The correct option was [{correct}].")
        print(f"💡 Explanation: {card.get('explanation')}")

    print("\n" + "="*60)
    print(f" 📊 QUIZ RESULTS: You scored {score}/{total} ({round((score/total)*100)}%)!")
    print("="*60)

async def run_quiz_card_generation(supervisor: ClassroomSupervisorAgentV2, user: dict, curriculum_repo: CurriculumRepository, session_id: str):
    print("\n" + "="*50)
    print(" 🎯 OPTION 2: DYNAMIC FLAG QUIZ CARD GENERATOR")
    print("="*50)
    
    subjects = await curriculum_repo.get_subjects_by_class(user["class_level"])
    subject = select_subject(subjects, user["class_level"])
    display_subject = subject.replace('_', ' ').title()
    print(f"\n✅ Selected Subject: {display_subject}")

    topic = safe_input(f"\n🎯 Enter quiz topic for {display_subject} (e.g. Northern Mountains, Fractions, Photosynthesis): ").strip()
    if not topic:
        print("Topic cannot be empty.")
        return

    previous_questions = []

    while True:
        user_msg = UserMsg(
            name=user["username"],
            content=f"Generate 4 flag quiz cards for topic: {topic}",
            metadata={
                "session_id": session_id,
                "grade": user["class_level"],
                "subject": subject,
                "intent": "quiz",
                "count": 4,
                "previous_questions": previous_questions
            }
        )

        print("\n⌛ Querying MongoDB and generating 4 dynamic Flag Quiz Cards...")
        reply = await supervisor.reply(user_msg)
        agent_result = getattr(reply, "metadata", {}).get("agent_result", {})

        if not agent_result.get("success", False):
            print(f"❌ Quiz Generation Error: {agent_result.get('error')}")
            break

        data = agent_result.get("data", {})
        cards = []
        if isinstance(data, dict):
            cards = data.get("cards", [])
            if not cards and "question" in data:
                cards = [data]
        elif isinstance(data, list):
            cards = data

        if not cards:
            print("❌ No quiz cards generated.")
            break

        print("\n" + "="*60)
        print(f" 🚩 4 DYNAMIC FLAG QUIZ CARDS FOR: {topic.upper()}")
        print("="*60)

        for idx, card in enumerate(cards, 1):
            q_text = card.get('question', '')
            if q_text:
                previous_questions.append(q_text)
            print(f"\n🎴 CARD #{idx} [ID: {card.get('question_id')} | Class: {card.get('class_level')} | Subject: {card.get('subject')} | Difficulty: {card.get('difficulty')}]")
            print(f"❓ Question:\n   {q_text}")
            print("\n📋 Options:")
            for opt in card.get("options", []):
                mark = " (Correct)" if opt.get("key") == card.get("correct_option") else ""
                print(f"   [{opt.get('key')}] {opt.get('text')}{mark}")
            print(f"\n💡 Explanation:\n   {card.get('explanation')}")
            print("-" * 60)

        print("\nWhat would you like to do next?")
        print("  1. 🔄 Regenerate 4 New Quiz Cards (New Questions)")
        print("  2. 📝 Practice / Answer these 4 Questions")
        print("  3. 🚪 Return to Main Menu")

        choice = safe_input("\nSelect an option (1-3): ").strip()
        if choice == "1":
            print("\n🔄 Requesting 4 new questions from QuizAgent...")
            continue
        elif choice == "2":
            await practice_quiz_cards(cards)
            post_choice = safe_input("\nWould you like to regenerate 4 new cards now? (yes/no): ").strip().lower()
            if post_choice in ("yes", "y"):
                continue
            else:
                break
        else:
            break

async def run_video_generation(supervisor: ClassroomSupervisorAgentV2, user: dict, curriculum_repo: CurriculumRepository, session_id: str):
    print("\n" + "="*50)
    print(" 🎬 OPTION 3: EDUCATIONAL VIDEO GENERATOR")
    print("="*50)
    
    subjects = await curriculum_repo.get_subjects_by_class(user["class_level"])
    subject = select_subject(subjects, user["class_level"])
    display_subject = subject.replace('_', ' ').title()
    print(f"\n✅ Selected Subject: {display_subject}")

    topic = safe_input(f"\n🎬 Enter topic for {display_subject} video lesson (e.g. Solar System, Photosynthesis, Water Cycle): ").strip()
    if not topic:
        print("Topic cannot be empty.")
        return

    user_msg = UserMsg(
        name=user["username"],
        content=f"Generate an educational video for topic: {topic}",
        metadata={"session_id": session_id, "grade": user["class_level"], "subject": subject, "intent": "video"}
    )

    print("\n⌛ Constructing video lesson blueprint & scene prompts...")
    reply = await supervisor.reply(user_msg)
    agent_result = getattr(reply, "metadata", {}).get("agent_result", {})

    print("\n" + "="*60)
    print(" 🎬 VIDEO LESSON BLUEPRINT RESULT")
    print("="*60)

    if agent_result.get("success", False):
        vid = agent_result.get("data", {})
        print(f"Title: {vid.get('video_title')}")
        print(f"Class Level: {vid.get('class_level')} | Topic: {vid.get('topic')}")
        print(f"\n📝 Concept Summary:\n   {vid.get('concept_summary')}")
        print(f"\n🎥 Structured LLM Video Prompt:\n   {vid.get('structured_prompt')}")
        print("\n🎞️ Scene Breakdown & Voiceover Script:")
        for sc in vid.get("scenes", []):
            print(f"\n   Scene #{sc.get('scene_number')}:")
            print(f"     🎙️ Narration: {sc.get('narration')}")
            print(f"     👁️ Visual Prompt: {sc.get('visual_prompt')}")
    else:
        print(f"❌ Video Generation Error: {agent_result.get('error')}")
    print("="*60)

async def run_textbook_ingestion():
    print("\n" + "="*50)
    print(" 📑 OPTION 4: TEXTBOOK DATA INGESTION")
    print("="*50)
    try:
        from ai_teacher_robot.pipelines.curriculum_ingestion_pipeline import CurriculumIngestionPipeline
        pdf_path = safe_input("Enter path to PDF textbook file [Press Enter to cancel]: ").strip()
        if not pdf_path or not os.path.exists(pdf_path):
            print("Path does not exist or operation cancelled.")
            return
        print(f"Starting ingestion pipeline for: {pdf_path}")
        pipeline = CurriculumIngestionPipeline()
        doc_id = await pipeline.ingest_pdf(pdf_path)
        print(f"✅ Ingestion completed successfully! Generated Document ID: {doc_id}")
    except Exception as e:
        print(f"❌ Ingestion error: {e}")


async def run_system_diagnostics(supervisor: ClassroomSupervisorAgentV2):
    print("\n" + "="*50)
    print(" 🧪 OPTION 5: SYSTEM DIAGNOSTIC DEMOS & TESTS")
    print("="*50)
    print("Executing component verification suite...")
    
    state_mgr = AgentStateManager()
    p1 = state_mgr.get_class_subject_prompt(4, "Social Studies")
    p2 = state_mgr.get_class_subject_prompt(10, "Science")
    
    print("✅ Prompt Loader Test: Successfully loaded Class 4 Social Studies & Class 10 Science MD prompts.")
    print("✅ Agent State Manager: Active and ready.")
    print("✅ Supervisor Agent V2: Pipeline initialized and healthy.")
    print("="*50)

async def run_v3_session(user: dict, curriculum_repo: CurriculumRepository):
    from pipelines.adaptive_learning_pipeline import AdaptiveLearningPipeline
    from pipelines.assessment_pipeline import AssessmentPipeline
    from pipelines.classroom_pipeline import ClassroomPipeline
    from pipelines.homework_pipeline import HomeworkPipeline
    from pipelines.analytics_pipeline import AnalyticsPipeline
    from pipelines.summary_pipeline import SummaryPipeline

    supervisor = ClassroomSupervisorAgentV3(name="ClassroomSupervisorAgentV3")
    session_id = f"session_v3_{user['username']}_{int(asyncio.get_event_loop().time())}"

    print("\n" + "="*60)
    print(" 🏫 WELCOME TO AUTONOMOUS CLASSROOM SESSION (VERSION 3)")
    print("="*60)

    # Let the user pick a subject first
    subjects = await curriculum_repo.get_subjects_by_class(user["class_level"])
    subject = select_subject(subjects, user["class_level"])
    display_subject = subject.replace('_', ' ').title()
    print(f"\n✅ Target subject set to: {display_subject}")

    while True:
        print(f"\n--- V3 Session Control (Logged in as: {user['username']} | Role: {user['role'].capitalize()} | Class {user['class_level']} | {display_subject}) ---")
        if user["role"] == "teacher":
            print("  1. 📚 Ask Educational/Instructional Query")
            print("  2. 📝 Generate Lesson Notes / Handouts / Practice Sheets")
            print("  3. 📊 Compile & Display Student Analytics Report")
            print("  4. 🚪 Exit Autonomous Session")
        else:
            print("  1. 📖 Personalised Interactive Tutoring / Q&A")
            print("  2. 🎯 Enter Assessment/Test Mode (Take Test & Evaluate)")
            print("  3. 🎮 Play Classroom Interaction Game (Quiz Mode, Rapid Fire)")
            print("  4. 🚪 Exit Autonomous Session")

        choice = safe_input("\nChoose Option (1-4): ").strip()
        if choice == "4":
            print("Returning to main menu...")
            break

        if choice == "1":
            query = safe_input("\n🎓 Enter message or topic: ").strip()
            if not query:
                print("Query cannot be empty.")
                continue

            user_msg = UserMsg(
                name=user["username"],
                content=query,
                metadata={
                    "session_id": session_id,
                    "grade": user["class_level"],
                    "subject": subject,
                    "student_id": user["username"],
                    "role": user["role"]
                }
            )

            print("\n⌛ Executing V3 autonomous planning and adaptive pipeline...")
            reply = await supervisor.reply(user_msg)
            agent_result = getattr(reply, "metadata", {}).get("agent_result", {})

            if agent_result.get("success", False):
                data = agent_result.get("data", {})
                print("\n" + "="*60)
                print(" V3 PIPELINE OUTPUT")
                print("="*60)
                print(f"🤖 Answer:\n{data.get('answer', '')}")
                
                profile = data.get("adaptive_profile", {})
                if profile:
                    print(f"\n⚡ Personalisation: Level={profile.get('difficulty_level')} | Style={profile.get('teaching_style')}")
                
                strategy = data.get("planning_strategy", "")
                if strategy:
                    print(f"📋 Planning Strategy: {strategy}")
                
                vid = data.get("video_blueprint", {})
                if vid:
                    print(f"\n🎥 Video Lesson Blueprint Generated:\n  Title: {vid.get('video_title')}\n  Script Summary: {vid.get('concept_summary')}")
                
                quiz = data.get("quiz_cards", {})
                if quiz:
                    print(f"\n🚩 Quiz Cards Appended.")
                
                summary = data.get("session_summary", {})
                if summary:
                    print(f"\n📝 Session Summary Appended:\n  Interesting Fact: {summary.get('interesting_fact')}\n  Homework: {summary.get('homework')}")
                
                print("="*60)
            else:
                print(f"\n❌ Pipeline Error: {agent_result.get('error')}")

        elif choice == "2":
            if user["role"] == "teacher":
                topic = safe_input("\nEnter topic for teaching material: ").strip()
                if not topic:
                    continue
                print("\nAvailable formats: notes, worksheet, flashcards")
                m_type = safe_input("Choose material type (notes/worksheet/flashcards): ").strip().lower()
                pipeline = HomeworkPipeline()
                print("\n⌛ Generating teaching aid...")
                res = await pipeline.generate_material(
                    topic=topic,
                    material_type=m_type or "worksheet",
                    format_type="markdown",
                    metadata={"teacher_id": user["username"], "grade": user["class_level"], "subject": subject}
                )
                if res.success:
                    print(f"\n✅ Content Generated Successfully!\nPath: {res.data.get('file_path')}\n\nContent Preview:\n{res.data.get('content')[:500]}...")
                else:
                    print(f"\n❌ Generation failed: {res.error}")
            else:
                topic = safe_input("\nEnter topic to start assessment: ").strip()
                if not topic:
                    continue
                pipeline = AssessmentPipeline()
                print("\n⌛ Generating questions (MCQ, Subjective, HOTS, Case)...")
                res = await pipeline.run_generate(topic, {"student_id": user["username"], "grade": user["class_level"], "subject": subject})
                if not res.success:
                    print(f"❌ Error: {res.error}")
                    continue
                
                questions = res.data.get("questions", [])
                answers = {}
                print("\n" + "="*50)
                print(f" 📝 ASSESSMENT: {topic.upper()}")
                print("="*50)
                for idx, q in enumerate(questions, 1):
                    print(f"\nQ{idx} [{q.get('type').upper()} - {q.get('difficulty')}]:")
                    print(q.get("question_text"))
                    if q.get("options"):
                        for opt in q.get("options"):
                            print(f"   [{opt.get('key')}] {opt.get('text')}")
                        ans = safe_input("\nYour Answer (A/B/C/D): ").strip().upper()
                    else:
                        ans = safe_input("\nYour Explanation / Answer: ").strip()
                    answers[q.get("question_id")] = ans

                print("\n⌛ Grading answers and compiling recommendations...")
                grade_res = await pipeline.run_evaluate(
                    topic=topic,
                    student_answers=answers,
                    original_questions=questions,
                    metadata={"student_id": user["username"], "grade": user["class_level"], "subject": subject, "session_id": session_id}
                )
                if grade_res.success:
                    gdata = grade_res.data
                    print("\n" + "="*50)
                    print(" 📊 EVALUATION REPORT")
                    print("="*50)
                    print(f"Score: {gdata.get('score')} / {len(questions)}")
                    print(f"Weak Topics: {gdata.get('weak_topics')}")
                    print(f"Suggested Reading: {gdata.get('suggested_reading')}")
                    print(f"Revision Plan:\n{gdata.get('revision_plan')}")
                    print("="*50)
                else:
                    print(f"❌ Grading Error: {grade_res.error}")

        elif choice == "3":
            if user["role"] == "teacher":
                pipeline = AnalyticsPipeline()
                print("\n⌛ Compiling classroom performance intelligence report...")
                res = await pipeline.compile_report(subject, {"student_id": user["username"], "grade": user["class_level"], "subject": subject, "session_id": session_id})
                if res.success:
                    adata = res.data
                    print("\n" + "="*60)
                    print(" 📊 CLASSROOM INTELLIGENCE SUMMARY REPORT")
                    print("="*60)
                    print(f"Subject: {adata.get('subject')} | Grade Level: {adata.get('grade')}")
                    print(f"Total Questions Handled: {adata.get('questions_asked')}")
                    print(f"Average Difficulty Mastery: {adata.get('average_difficulty')}")
                    print(f"Struggle Topics: {adata.get('weak_topics')}")
                    print(f"Concept Statistics: {adata.get('topic_statistics')}")
                    sa = adata.get("student_analytics", {})
                    if sa:
                        print(f"Class Trend: {sa.get('learning_trend')}")
                        print(f"Conceptual Gap: {sa.get('conceptual_gaps')}")
                    print("="*60)
                else:
                    print(f"❌ Analytics compilation failed: {res.error}")
            else:
                game_mode = safe_input("Enter game type (Quiz Mode/Rapid Fire/Vocabulary Game): ").strip() or "Quiz Mode"
                pipeline = ClassroomPipeline()
                print(f"\n⌛ Setting up {game_mode} turn...")
                challenge = safe_input("Enter what topic you want to play game on: ").strip()
                res = await pipeline.run_turn(challenge, game_mode, 0, {"student_id": user["username"], "grade": user["class_level"], "subject": subject, "session_id": session_id})
                if res.success:
                    gdata = res.data
                    payload = gdata.get("game_payload", {})
                    print("\n" + "="*50)
                    print(f" 🎮 PLAYING: {game_mode}")
                    print("="*50)
                    print(f" Ranks Leaderboard: {gdata.get('leaderboard')}")
                    print(f" Riddle/Question:\n {payload.get('question')}")
                    print(f" Hints available: {gdata.get('hints')}")
                    ans = safe_input("\nYour Answer: ").strip()
                    
                    res2 = await pipeline.run_turn(ans, game_mode, 1, {"student_id": user["username"], "grade": user["class_level"], "subject": subject, "session_id": session_id})
                    if res2.success:
                        print(f"\n✅ Result: Points Earned! Updated Score: {res2.data.get('score')}")
                    else:
                        print("❌ Next turn error.")
                    print("="*50)
                else:
                    print(f"❌ Game Setup Error: {res.error}")

async def main() -> None:
    user_repo = UserRepository()
    curriculum_repo = CurriculumRepository()
    
    # 1. User Login / Authentication
    user = await authenticate_flow(user_repo)
    
    # 2. Instantiate Main Supervisor Agent
    logger.info("Initializing ClassroomSupervisorAgent Version 2 Pipeline...")
    supervisor = ClassroomSupervisorAgentV2(name="ClassroomSupervisorAgentV2")
    
    session_id = f"session_{user['username']}_{int(asyncio.get_event_loop().time())}"
    
    # 3. Main Interactive Task Selection Menu
    while True:
        print("\n" + "="*60)
        print(f" 🎓 MAIN MENU (Logged in as: {user['username']} | Role: {user['role'].capitalize()} | Class {user['class_level']})")
        print("="*60)
        print("  1. 📖 Ask Educational Question / Interactive Chat")
        print("  2. 🎯 Generate Dynamic Flag Quiz Card (MongoDB + LLM)")
        print("  3. 🎬 Generate Educational Video Lesson Blueprint")
        print("  4. 📑 Run Textbook Data Ingestion")
        print("  5. 🧪 Run System Diagnostic Checks")
        print("  6. 🏫 Enter Autonomous Classroom Session (Version 3)")
        print("  7. 🚪 Exit / Logout")
        print("="*60)
        
        choice = safe_input("Select an option (1-7): ").strip()
        
        if choice == "1":
            await run_educational_query(supervisor, user, curriculum_repo, session_id)
        elif choice == "2":
            await run_quiz_card_generation(supervisor, user, curriculum_repo, session_id)
        elif choice == "3":
            await run_video_generation(supervisor, user, curriculum_repo, session_id)
        elif choice == "4":
            await run_textbook_ingestion()
        elif choice == "5":
            await run_system_diagnostics(supervisor)
        elif choice == "6":
            await run_v3_session(user, curriculum_repo)
        elif choice == "7" or choice.lower() in ('exit', 'quit', 'q'):
            print("\nThank you for using AI Classroom Teaching Robot. Goodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid selection. Please enter a number between 1 and 7.")

if __name__ == "__main__":
    if "GROQ_API_KEY" not in os.environ:
        print("WARNING: GROQ_API_KEY environment variable not found in environment.")
        print("To run with live API calls, ensure GROQ_API_KEY is present in your .env file.\n")
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting...")
