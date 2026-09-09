import re

def strain_text(text: str) -> str:
    """Strains incoming text to format it cleanly as standard readable Markdown.
    
    Fixes typical formatting anomalies:
    1. Replaces literal '-n', '\\n', '- n' with actual newline characters.
    2. Merges spaced markdown bold asterisks '* *' or '*  *' -> '**'.
    3. Trims whitespace inside markdown formatting markers (e.g. '** text **' -> '**text**').
    4. Converts pseudo-pipes (' I ', ' l ') back to standard pipes ('|') in table layouts.
    """
    if not text:
        return ""

    # 0. Strip reasoning <think>...</think> blocks safely (even if unclosed)
    if "<think>" in text:
        if "</think>" in text:
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        else:
            text = re.sub(r'<think>.*', '', text, flags=re.DOTALL).strip()

    # 0b. Filter out prompt leakage and internal monologue markers
    leakage_patterns = [
        r'\[Self-Correction/.*?\]',
        r'Student Query/Context:.*?\n',
        r'Reference Context Provided:.*?\n',
        r'Source #\d+:.*?\n',
        r'MAGNETIC CONSTRAINT FORCE:.*?\n',
        r'FACTUAL GROUNDEDNESS ATTRACTOR WARNING:.*?\n'
    ]
    for lp in leakage_patterns:
        text = re.sub(lp, '', text, flags=re.IGNORECASE)

    # 1. Clean up literal newlines first
    text = re.sub(r'[ \t]*\\n[ \t]*', '\n', text)
    text = re.sub(r'[ \t]*-n[ \t]*', '\n', text)
    text = re.sub(r'[ \t]*- n[ \t]*', '\n', text)
    
    # 2. Replace merged table row indicators " I I ", " l l ", " I | " etc. with pipe-newline-pipe FIRST
    text = re.sub(r'[ \t]*[Il|][ \t]+[Il|][ \t]*', ' |\n| ', text)
    
    # 3. Handle boundaries before headers or list indicators SECOND
    text = re.sub(r'[ \t]+[Il|][ \t]+(?=(?:###|##|#|\*\*|>\s*\*|-\s*\*))', '\n\n', text)
    
    # 4. Clean up spaced asterisks safely using horizontal spaces
    text = re.sub(r'\*[ \t]+\*(?=\w)', '**', text)
    text = re.sub(r'(\w)\*[ \t]+\*', r'\1**', text)
    text = re.sub(r'\*[ \t]+\*', '**', text)
    
    # 5. Trim interior whitespace inside bolding and italics (horizontal spaces only)
    text = re.sub(r'\*\*[ \t]+(.*?)[ \t]+\*\*', r'**\1**', text)
    text = re.sub(r'\*[ \t]+(.*?)[ \t]+\*', r'*\1*', text)
    
    # 6. Correct pseudo-pipe characters in tables
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
            
        i_count = len(re.findall(r'[ \t]+I[ \t]+', line))
        l_count = len(re.findall(r'[ \t]+l[ \t]+', line))
        
        is_table = False
        if stripped.startswith('|') or stripped.endswith('|'):
            is_table = True
        elif (stripped.startswith('I ') or stripped.endswith(' I')) and i_count >= 1:
            is_table = True
        elif (i_count >= 2 or l_count >= 2) and not re.search(r'\b(i am|i have|i think|i would|i will|i do|i go|i can|i see|i know|i feel|i\'m|i\'ll|i\'ve)\b', line.lower()):
            is_table = True
            
        if is_table:
            line_cleaned = line
            # Ensure line starts/ends with a pipe
            if not line_cleaned.strip().startswith('|'):
                if line_cleaned.strip().startswith('I ') or line_cleaned.strip().startswith('l '):
                    line_cleaned = '| ' + line_cleaned.strip()[2:]
                else:
                    line_cleaned = '| ' + line_cleaned.strip()
            if not line_cleaned.strip().endswith('|'):
                if line_cleaned.strip().endswith(' I') or line_cleaned.strip().endswith(' l'):
                    line_cleaned = line_cleaned.strip()[:-2] + ' |'
                else:
                    line_cleaned = line_cleaned.strip() + ' |'
                
            # Replace internal ' I ' and ' l ' separators with standard pipes
            line_cleaned = re.sub(r'[ \t]+I[ \t]+', ' | ', line_cleaned)
            line_cleaned = re.sub(r'[ \t]+l[ \t]+', ' | ', line_cleaned)
            
            # Clean up duplicate pipes
            line_cleaned = re.sub(r'\|[ \t]*\|', '|', line_cleaned)
            cleaned_lines.append(line_cleaned)
        else:
            cleaned_lines.append(line)
            
    return '\n'.join(cleaned_lines)
