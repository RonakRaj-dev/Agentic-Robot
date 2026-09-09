from typing import Any


def build_content_generation_prompt(
    query: str,
    grade: Any,
    subject: str,
    material_type: str,
    format_type: str,
) -> str:
    return (
        "You are an educational Content Generation Agent. Generate a premium teaching aid based on the request:\n\n"
        f"Topic / Instructions: '{query}'\n"
        f"Grade Level: Class {grade}\n"
        f"Subject: {subject}\n"
        f"Material Type: {material_type}\n"
        f"Requested Format: {format_type}\n\n"
        "Provide complete detailed content. Do not use placeholders.\n"
        "Return a JSON object conforming strictly to the ContentGenerationResponse schema:\n"
        "{\n"
        f'  "material_type": "{material_type}",\n'
        f'  "format": "{format_type}",\n'
        '  "content": "Fully-formed detailed markdown or HTML content string representing the worksheet/notes...",\n'
        '  "file_path": "Optionally generated local file location or URL"\n'
        '}'
    )
