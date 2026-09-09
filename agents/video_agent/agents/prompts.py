MASTER_NEGATIVE_PROMPT = (
    "No distorted faces, no extra fingers, no malformed hands, no duplicated characters, "
    "no inconsistent character appearance, no incorrect geometry, no mathematically incorrect diagrams, "
    "no incorrect scientific processes, no random symbols, no illegible text, no misspelled words, "
    "no warped objects, no flickering, no jitter, no unstable camera, no excessive motion blur, "
    "no abrupt camera movements, no confusing transitions, no cluttered composition, "
    "no dark or frightening atmosphere, no unnecessary visual effects, no low-resolution textures, "
    "no watermark, no logo, no random subtitles, no irrelevant objects."
)

def build_video_prompt(
    class_prompt: str,
    grade: int,
    topic: str,
    subject: str = "Science",
    chapter_title: str = "Core Concepts"
) -> str:
    topic_escaped = topic.replace('"', '\\"')
    subj_escaped = subject.replace('"', '\\"')
    ch_escaped = chapter_title.replace('"', '\\"')
    
    style_guideline = "3D Pixar-inspired educational animation, bright vibrant colors, 4K UHD, 24fps" if grade <= 5 else "3D photorealistic infographic animation, studio volumetric lighting, 4K UHD"

    return (
        f"{class_prompt}\n\n"
        "==================================================\n"
        "EDUCATIONAL 3D VIDEO GENERATION AGENT — MASTER TEMPLATE INSTRUCTION\n"
        "==================================================\n"
        "Role: Expert AI Educational Video Director, Scriptwriter, 3D Animation Director, and Content Designer.\n"
        f"Goal: Transform Class {grade} {subject} topic '{topic}' (Chapter: {chapter_title}) into a cinematic, curriculum-aligned 3D educational video blueprint for AI Text-To-Video models (Sora, Runway Gen-3, HunyuanVideo, Luma Dream Machine, Kling, Veo).\n\n"
        "You MUST produce ONLY a JSON object matching this exact schema:\n"
        "{\n"
        f'  "topic": "{topic_escaped}",\n'
        f'  "class_level": {grade},\n'
        f'  "subject": "{subj_escaped}",\n'
        f'  "chapter_title": "{ch_escaped}",\n'
        f'  "video_title": "Cinematic 3D Video Title for Class {grade} {subject}",\n'
        '  "concept_summary": "1-2 sentence core educational summary",\n'
        '  "learning_objectives": ["Objective 1", "Objective 2", "Objective 3"],\n'
        f'  "visual_style": "{style_guideline}",\n'
        '  "camera_motion": "Slow cinematic dolly-in with soft volumetric lighting and moderate depth of field",\n'
        '  "total_duration_seconds": 180,\n'
        '  "character_design": "Consistent warm teacher guide and curious student character in colorful attire",\n'
        '  "global_environment": "Bright, modern, welcoming 3D interactive classroom environment",\n'
        '  "structured_prompt": "Complete master generation prompt summarizing style, lighting, character consistency, and topic objectives...",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "scene_number": 1,\n'
        '      "timestamp_start": "00:00",\n'
        '      "timestamp_end": "00:15",\n'
        '      "duration_seconds": 15,\n'
        '      "scene_purpose": "HOOK: Introduce topic using a surprising, visually engaging real-life situation to create curiosity",\n'
        '      "shot_type": "Wide establishing shot + slow dolly-in",\n'
        '      "visual_prompt": "Detailed 3D animation prompt describing visual action and graphics",\n'
        '      "educational_visualization": "3D objects, labeled diagrams, and visual analogies",\n'
        '      "character_action": "Teacher/student gestures and interactions",\n'
        '      "camera": "Camera movement and framing",\n'
        '      "lighting": "Soft volumetric studio lighting",\n'
        '      "on_screen_text": "Minimal, clean, high-contrast educational text label",\n'
        '      "narration": "Age-appropriate voiceover transcript",\n'
        '      "sound_effects": "Subtle educational sound effects",\n'
        '      "transition": "Smooth cinematic cross-dissolve to Scene 2",\n'
        '      "learning_takeaway": "Key takeaway sentence for Scene 1"\n'
        '    }\n'
        '  ],\n'
        '  "recap_summary": "Short visual recap summarizing the main concepts using icons and key terms",\n'
        f'  "negative_prompt": "{MASTER_NEGATIVE_PROMPT}",\n'
        '  "final_generation_instruction": "Generate the video as one cohesive educational experience maintaining character, environment, lighting, and scientific accuracy throughout."\n'
        '}'
    )

