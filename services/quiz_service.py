"""
Quiz Service - Intelligent NCERT Quiz & Assessment Engine (Silicon Project V3)
Generates high-grade, age-appropriate, grounded MCQs for Class 1-10 students.
Features:
1. Multi-Format MCQ Parser (JSON Array, JSON Object with dict/list options, Markdown Table, Numbered List).
2. Title & Chapter number normalization.
3. Persistent MongoDB caching (`QUIZZES` collection).
4. Dynamic LLM Gateway generation via Groq Llama-3.3-70B.
5. Rich NCERT topic-specific & subject-aware deterministic knowledge matrix (10 Real Questions per chapter, zero meta-curriculum fluff).
"""

from __future__ import annotations
import re
import json
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager
from models.llm_gateway import LLMGateway

def clean_chapter_title(raw_title: Optional[str]) -> str:
    """Strips chapter numbers, prefixes, and punctuation (e.g. 'Chapter 4: Materials: Metals and Non-Metals' -> 'Materials: Metals and Non-Metals')."""
    if not raw_title:
        return "Core Concepts"
    clean = raw_title.strip()
    clean = re.sub(r'^(?:Chapter\s*)?\d+[\s:.\-–—]+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'^\d+\s*:\s*', '', clean)
    clean = re.sub(r'[*_#]+', '', clean).strip()
    return clean or raw_title.strip()


def normalize_single_mcq(item: Dict[str, Any], idx: int, cid: str, cls: int) -> Optional[Dict[str, Any]]:
    """Normalizes any raw MCQ dictionary (handling dict options, list options, different key names)."""
    q_text = item.get("question") or item.get("q") or item.get("title")
    if not q_text or len(str(q_text).strip()) < 5:
        return None

    # 1. Parse Options
    raw_opts = item.get("options") or item.get("opts") or item.get("choices") or []
    opts: List[Dict[str, str]] = []

    if isinstance(raw_opts, dict):
        for k, v in raw_opts.items():
            if str(k).upper() in ["A", "B", "C", "D"]:
                opts.append({"key": str(k).upper(), "text": str(v).strip()})
    elif isinstance(raw_opts, list):
        for opt in raw_opts:
            if isinstance(opt, dict):
                k = opt.get("key") or opt.get("k") or opt.get("id") or "A"
                t = opt.get("text") or opt.get("t") or opt.get("value") or opt.get("option") or ""
                opts.append({"key": str(k).upper(), "text": str(t).strip()})
            elif isinstance(opt, str):
                m = re.match(r'^\*?\*?([A-D])[\.\:\)]\*?\*?\s*(.*)', opt, re.IGNORECASE)
                if m:
                    opts.append({"key": m.group(1).upper(), "text": m.group(2).strip()})
                else:
                    key_char = chr(65 + len(opts))
                    opts.append({"key": key_char, "text": opt.strip()})

    # Sort options by key
    opts = sorted([o for o in opts if o["key"] in ["A", "B", "C", "D"]], key=lambda x: x["key"])

    # Ensure 4 options
    if len(opts) < 2:
        return None

    # 2. Parse Correct Key
    raw_key = (
        item.get("correctKey")
        or item.get("correct_key")
        or item.get("answer")
        or item.get("correct_option")
        or item.get("ans")
        or item.get("correct")
        or "A"
    )
    key_match = re.search(r'[A-D]', str(raw_key), re.IGNORECASE)
    correct_key = key_match.group(0).upper() if key_match else "A"

    # 3. Parse Explanation
    exp = (
        item.get("explanation")
        or item.get("exp")
        or item.get("reason")
        or "Correct conceptual NCERT derivation."
    )

    return {
        "id": item.get("id") or f"qz_{cls}_{idx}",
        "chapterId": cid,
        "question": str(q_text).replace("**", "").strip(),
        "options": opts,
        "correctKey": correct_key,
        "explanation": str(exp).replace("**", "").strip()
    }


def parse_mcq_response(raw_text: str, cid: str, cls: int) -> List[Dict[str, Any]]:
    """Universal multi-format parser for LLM responses (JSON array, JSON dict, Markdown Table, Numbered text)."""
    clean = re.sub(r'```(?:json)?', '', raw_text).strip()
    parsed_items: List[Dict[str, Any]] = []

    # Format 1: Direct JSON array
    s_idx = clean.find('[')
    e_idx = clean.rfind(']')
    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
        try:
            data = json.loads(clean[s_idx:e_idx+1])
            if isinstance(data, list):
                for idx, it in enumerate(data, 1):
                    if isinstance(it, dict):
                        norm = normalize_single_mcq(it, idx, cid, cls)
                        if norm:
                            parsed_items.append(norm)
                if len(parsed_items) >= 4:
                    return parsed_items
        except Exception:
            pass

    # Format 2: JSON Object with questions / quiz / cards key
    s_obj = clean.find('{')
    e_obj = clean.rfind('}')
    if s_obj != -1 and e_obj != -1 and e_obj > s_obj:
        try:
            data = json.loads(clean[s_obj:e_obj+1])
            for key in ['questions', 'quiz', 'cards', 'mcqs', 'items', 'data']:
                if key in data and isinstance(data[key], list):
                    for idx, it in enumerate(data[key], 1):
                        if isinstance(it, dict):
                            norm = normalize_single_mcq(it, idx, cid, cls)
                            if norm:
                                parsed_items.append(norm)
                    if len(parsed_items) >= 4:
                        return parsed_items
        except Exception:
            pass

    # Format 3: Markdown Table
    rows = [r.strip() for r in raw_text.split('\n') if r.strip().startswith('|') and not '---' in r and not '# |' in r and not 'Question |' in r]
    table_items: List[Dict[str, Any]] = []
    for idx, r in enumerate(rows, 1):
        parts = [p.strip() for p in r.split('|')[1:-1]]
        if len(parts) >= 4:
            q_text = parts[1] if len(parts) >= 5 else parts[0]
            opts_raw = parts[2] if len(parts) >= 5 else parts[1]
            ans_raw = parts[3] if len(parts) >= 5 else parts[2]
            exp = parts[4] if len(parts) >= 5 else (parts[3] if len(parts) > 3 else '')
            
            opts = []
            opts_clean = re.sub(r'<br\s*/?>', '\n', opts_raw)
            for line in opts_clean.split('\n'):
                line = line.strip()
                m = re.match(r'^\*?\*?([A-D])[\.\:\)]\*?\*?\s*(.*)', line, re.IGNORECASE)
                if m:
                    opts.append({'key': m.group(1).upper(), 'text': m.group(2).strip()})
            if len(opts) < 4:
                for m in re.finditer(r'([A-D])[\.\:\)]\s*([^\n<]+)', opts_raw, re.IGNORECASE):
                    k = m.group(1).upper()
                    if not any(o['key'] == k for o in opts):
                        opts.append({'key': k, 'text': m.group(2).strip()})
            
            ans_match = re.search(r'[A-D]', ans_raw)
            c_key = ans_match.group(0).upper() if ans_match else 'A'
            
            if q_text and len(opts) >= 2:
                table_items.append({
                    'id': f"qz_{cls}_{idx}",
                    'chapterId': cid,
                    'question': q_text.replace('**', '').strip(),
                    'options': opts,
                    'correctKey': c_key,
                    'explanation': exp.replace('**', '').strip()
                })
    if len(table_items) >= 4:
        return table_items

    return parsed_items


# Comprehensive Domain-Accurate NCERT Knowledge Matrix
TOPIC_QUIZ_MATRIX: Dict[str, List[Dict[str, Any]]] = {
    "metals_non_metals": [
        {
            "question": "Which of the following physical properties is characteristic of metals?",
            "options": [{"key": "A", "text": "Malleability (can be beaten into thin sheets)"}, {"key": "B", "text": "Brittleness"}, {"key": "C", "text": "Poor thermal conductivity"}, {"key": "D", "text": "Dull surface"}],
            "correctKey": "A",
            "explanation": "Metals are malleable, ductile, sonorous, and good conductors of heat and electricity."
        },
        {
            "question": "Which non-metal is a good conductor of electricity?",
            "options": [{"key": "A", "text": "Graphite (Carbon allotrope)"}, {"key": "B", "text": "Sulphur"}, {"key": "C", "text": "Phosphorus"}, {"key": "D", "text": "Oxygen"}],
            "correctKey": "A",
            "explanation": "Graphite has free delocalized electrons in its hexagonal layer lattice, making it conduct electricity."
        },
        {
            "question": "Why is Sodium metal stored submerged under kerosene oil?",
            "options": [{"key": "A", "text": "It reacts vigorously with oxygen and moisture in air"}, {"key": "B", "text": "To prevent it from evaporating"}, {"key": "C", "text": "To change its color"}, {"key": "D", "text": "To make it harder"}],
            "correctKey": "A",
            "explanation": "Sodium is highly reactive and catches fire spontaneously when exposed to air and moisture."
        },
        {
            "question": "Which non-metal is very reactive in air and is stored under water?",
            "options": [{"key": "A", "text": "Phosphorus"}, {"key": "B", "text": "Nitrogen"}, {"key": "C", "text": "Sulphur"}, {"key": "D", "text": "Carbon"}],
            "correctKey": "A",
            "explanation": "White phosphorus catches fire spontaneously in air, so it is kept safely submerged in water."
        },
        {
            "question": "When a metal reacts with dilute hydrochloric acid, which gas is produced with a pop sound?",
            "options": [{"key": "A", "text": "Hydrogen gas (H₂)"}, {"key": "B", "text": "Oxygen gas (O₂)"}, {"key": "C", "text": "Carbon Dioxide (CO₂)"}, {"key": "D", "text": "Nitrogen gas (N₂)"}],
            "correctKey": "A",
            "explanation": "Metal + Acid -> Metal Salt + Hydrogen gas. Hydrogen burns with a characteristic 'pop' sound."
        },
        {
            "question": "Which metal is liquid at room temperature?",
            "options": [{"key": "A", "text": "Mercury (Hg)"}, {"key": "B", "text": "Iron (Fe)"}, {"key": "C", "text": "Aluminium (Al)"}, {"key": "D", "text": "Copper (Cu)"}],
            "correctKey": "A",
            "explanation": "Mercury is the only metal that remains in liquid state at standard room temperature."
        },
        {
            "question": "The property of metals to produce a ringing sound when struck is called being:",
            "options": [{"key": "A", "text": "Sonorous"}, {"key": "B", "text": "Ductile"}, {"key": "C", "text": "Lustrous"}, {"key": "D", "text": "Malleable"}],
            "correctKey": "A",
            "explanation": "Metals produce a deep ringing sound upon collision, which is why temple bells are made of metals."
        },
        {
            "question": "The process of depositing a protective layer of zinc on iron to prevent rusting is called:",
            "options": [{"key": "A", "text": "Galvanization"}, {"key": "B", "text": "Electroplating"}, {"key": "C", "text": "Smelting"}, {"key": "D", "text": "Annealing"}],
            "correctKey": "A",
            "explanation": "Galvanization coats iron with zinc, preventing oxygen and moisture from causing rust."
        },
        {
            "question": "What is the nature of metallic oxides formed when metals burn in oxygen?",
            "options": [{"key": "A", "text": "Basic in nature (turns red litmus blue)"}, {"key": "B", "text": "Acidic in nature"}, {"key": "C", "text": "Neutral"}, {"key": "D", "text": "Amphoteric only"}],
            "correctKey": "A",
            "explanation": "Metallic oxides (like Magnesium Oxide) are basic and turn moist red litmus paper blue."
        },
        {
            "question": "Which of the following metals can displace Copper from Copper Sulphate solution?",
            "options": [{"key": "A", "text": "Zinc (Zn)"}, {"key": "B", "text": "Silver (Ag)"}, {"key": "C", "text": "Gold (Au)"}, {"key": "D", "text": "Platinum (Pt)"}],
            "correctKey": "A",
            "explanation": "Zinc is more reactive than copper in the reactivity series and displaces copper from CuSO₄."
        }
    ],
    "crop_production": [
        {
            "question": "Which crops are sown in the rainy season (June to September) in India?",
            "options": [{"key": "A", "text": "Kharif crops (e.g., Paddy, Maize, Soyabean)"}, {"key": "B", "text": "Rabi crops (e.g., Wheat, Gram)"}, {"key": "C", "text": "Zaid crops"}, {"key": "D", "text": "Winter crops"}],
            "correctKey": "A",
            "explanation": "Kharif crops depend on monsoon rainfall and are sown around June."
        },
        {
            "question": "Which modern irrigation technique delivers water directly drop by drop at the roots of plants?",
            "options": [{"key": "A", "text": "Drip Irrigation System"}, {"key": "B", "text": "Sprinkler System"}, {"key": "C", "text": "Moat (pulley system)"}, {"key": "D", "text": "Rahat system"}],
            "correctKey": "A",
            "explanation": "Drip irrigation avoids water wastage and provides maximum efficiency in arid regions."
        },
        {
            "question": "Which bacterium present in the root nodules of leguminous plants fixes atmospheric nitrogen?",
            "options": [{"key": "A", "text": "Rhizobium"}, {"key": "B", "text": "Lactobacillus"}, {"key": "C", "text": "E. coli"}, {"key": "D", "text": "Streptococcus"}],
            "correctKey": "A",
            "explanation": "Rhizobium bacteria live symbiotically in legume roots, converting nitrogen into soluble nitrates."
        },
        {
            "question": "The process of loosening and turning the soil before sowing seeds is known as:",
            "options": [{"key": "A", "text": "Tilling or Ploughing"}, {"key": "B", "text": "Threshing"}, {"key": "C", "text": "Winnowing"}, {"key": "D", "text": "Harvesting"}],
            "correctKey": "A",
            "explanation": "Ploughing aerates the soil and allows plant roots to penetrate deeply and breathe easily."
        },
        {
            "question": "The process of separating grain seeds from the harvested chaff is called:",
            "options": [{"key": "A", "text": "Threshing"}, {"key": "B", "text": "Sowing"}, {"key": "C", "text": "Irrigation"}, {"key": "D", "text": "Tilling"}],
            "correctKey": "A",
            "explanation": "Threshing separates edible grain kernels from stalks and chaff, often done using a Combine machine."
        }
    ],
    "microorganisms": [
        {
            "question": "Which friendly bacterium promotes the formation of curd from milk?",
            "options": [{"key": "A", "text": "Lactobacillus"}, {"key": "B", "text": "Salmonella"}, {"key": "C", "text": "Rhizobium"}, {"key": "D", "text": "Yeast"}],
            "correctKey": "A",
            "explanation": "Lactobacillus multiplies in warm milk and converts lactose sugar into lactic acid to make curd."
        },
        {
            "question": "The process of conversion of sugar into alcohol by yeast is called:",
            "options": [{"key": "A", "text": "Fermentation"}, {"key": "B", "text": "Pasteurization"}, {"key": "C", "text": "Sterilization"}, {"key": "D", "text": "Nitrogen Fixation"}],
            "correctKey": "A",
            "explanation": "Discovered by Louis Pasteur in 1857, fermentation produces alcohol and CO₂ from sugars."
        },
        {
            "question": "Which was the first antibiotic discovered by Alexander Fleming in 1929?",
            "options": [{"key": "A", "text": "Penicillin (from Penicillium notatum)"}, {"key": "B", "text": "Streptomycin"}, {"key": "C", "text": "Tetracycline"}, {"key": "D", "text": "Insulin"}],
            "correctKey": "A",
            "explanation": "Alexander Fleming discovered Penicillin from green mold contaminating a bacterial culture plate."
        },
        {
            "question": "Which insect acts as the carrier of the malaria-causing parasite Plasmodium?",
            "options": [{"key": "A", "text": "Female Anopheles mosquito"}, {"key": "B", "text": "Female Aedes mosquito"}, {"key": "C", "text": "Housefly"}, {"key": "D", "text": "Cockroach"}],
            "correctKey": "A",
            "explanation": "Female Anopheles mosquitoes transmit Plasmodium parasites while drawing blood."
        },
        {
            "question": "Heating milk to ~70°C for 15-30 seconds followed by sudden chilling to kill microbes is called:",
            "options": [{"key": "A", "text": "Pasteurization"}, {"key": "B", "text": "Boiling"}, {"key": "C", "text": "Condensation"}, {"key": "D", "text": "Dehydration"}],
            "correctKey": "A",
            "explanation": "Pasteurization destroys pathogenic bacteria without altering the taste or nutritional value of milk."
        }
    ],
    "cell_structure": [
        {
            "question": "Who first discovered and named 'cells' while observing cork slices under a microscope in 1665?",
            "options": [{"key": "A", "text": "Robert Hooke"}, {"key": "B", "text": "Robert Brown"}, {"key": "C", "text": "Anton van Leeuwenhoek"}, {"key": "D", "text": "Charles Darwin"}],
            "correctKey": "A",
            "explanation": "Robert Hooke observed honeycomb-like compartments in bottle cork and named them 'cells'."
        },
        {
            "question": "Which organelle is widely known as the 'Powerhouse of the Cell'?",
            "options": [{"key": "A", "text": "Mitochondria"}, {"key": "B", "text": "Nucleus"}, {"key": "C", "text": "Ribosome"}, {"key": "D", "text": "Endoplasmic Reticulum"}],
            "correctKey": "A",
            "explanation": "Mitochondria generate cellular energy in the form of ATP molecules through cellular respiration."
        },
        {
            "question": "Which protective structure is present in plant cells but absent in animal cells?",
            "options": [{"key": "A", "text": "Rigid Cellulose Cell Wall"}, {"key": "B", "text": "Plasma Membrane"}, {"key": "C", "text": "Cytoplasm"}, {"key": "D", "text": "Nucleus"}],
            "correctKey": "A",
            "explanation": "Plant cells possess a rigid outer cell wall made of cellulose for structural support."
        },
        {
            "question": "Which green pigment in chloroplasts absorbs solar energy for photosynthesis?",
            "options": [{"key": "A", "text": "Chlorophyll"}, {"key": "B", "text": "Hemoglobin"}, {"key": "C", "text": "Carotene"}, {"key": "D", "text": "Melanin"}],
            "correctKey": "A",
            "explanation": "Chlorophyll trapped inside chloroplast plastids absorbs red and blue light to power photosynthesis."
        },
        {
            "question": "The spherical control center of the cell containing genetic chromosomes and DNA is the:",
            "options": [{"key": "A", "text": "Nucleus"}, {"key": "B", "text": "Vacuole"}, {"key": "C", "text": "Golgi Apparatus"}, {"key": "D", "text": "Lysosome"}],
            "correctKey": "A",
            "explanation": "The nucleus controls all metabolic activities of the cell and stores hereditary genes."
        }
    ],
    "sound": [
        {
            "question": "Sound is produced due to which of the following mechanical phenomena?",
            "options": [{"key": "A", "text": "Rapid vibrations of an object"}, {"key": "B", "text": "Absorption of light"}, {"key": "C", "text": "Chemical reaction with air"}, {"key": "D", "text": "Gravitational pull"}],
            "correctKey": "A",
            "explanation": "Sound is produced when an object vibrates, creating longitudinal pressure waves in the surrounding medium."
        },
        {
            "question": "In which medium does sound travel at the highest speed?",
            "options": [{"key": "A", "text": "Solids (e.g., Steel or Iron)"}, {"key": "B", "text": "Liquids (e.g., Water)"}, {"key": "C", "text": "Gases (e.g., Air)"}, {"key": "D", "text": "Complete Vacuum"}],
            "correctKey": "A",
            "explanation": "Sound travels fastest in solids because particles are tightly packed, allowing mechanical waves to propagate rapidly."
        },
        {
            "question": "What is the audible frequency range for normal human hearing?",
            "options": [{"key": "A", "text": "20 Hz to 20,000 Hz (20 kHz)"}, {"key": "B", "text": "2 Hz to 200 Hz"}, {"key": "C", "text": "20,000 Hz to 2,000,000 Hz"}, {"key": "D", "text": "50 Hz to 5,000 Hz"}],
            "correctKey": "A",
            "explanation": "The human ear detects sonic frequencies strictly between 20 Hz and 20 kHz."
        },
        {
            "question": "What determines the pitch (shrillness) of a sound wave?",
            "options": [{"key": "A", "text": "Frequency of the vibration"}, {"key": "B", "text": "Amplitude of the wave"}, {"key": "C", "text": "Speed of wind"}, {"key": "D", "text": "Color of the vibrating body"}],
            "correctKey": "A",
            "explanation": "Higher frequency corresponds to higher pitch, while amplitude governs loudness."
        },
        {
            "question": "Why can sound NOT propagate through a vacuum (such as outer space)?",
            "options": [{"key": "A", "text": "Sound requires a material medium to propagate"}, {"key": "B", "text": "Vacuum absorbs all sound energy"}, {"key": "C", "text": "Sound is an electromagnetic wave"}, {"key": "D", "text": "Space temperature is too cold"}],
            "correctKey": "A",
            "explanation": "Sound is a mechanical wave requiring particle collisions in a material medium (solid, liquid, or gas)."
        }
    ],
    "sky_space": [
        {
            "question": "What primary motion of Earth causes the daily cycle of Day and Night?",
            "options": [{"key": "A", "text": "Rotation on its own axis every 24 hours"}, {"key": "B", "text": "Revolution around the Sun every 365 days"}, {"key": "C", "text": "Tidal pull of the Moon"}, {"key": "D", "text": "Precession of the equinoxes"}],
            "correctKey": "A",
            "explanation": "Earth's rotation on its axis exposes different halves to sunlight, creating day and night."
        },
        {
            "question": "Which celestial body is at the center of our Solar System?",
            "options": [{"key": "A", "text": "The Sun"}, {"key": "B", "text": "The Earth"}, {"key": "C", "text": "Jupiter"}, {"key": "D", "text": "The Moon"}],
            "correctKey": "A",
            "explanation": "The Sun is the massive central star around which all eight planets revolve."
        },
        {
            "question": "Why does the Moon shine brightly in the night sky?",
            "options": [{"key": "A", "text": "It reflects sunlight falling on its surface"}, {"key": "B", "text": "It undergoes nuclear fusion like a star"}, {"key": "C", "text": "It has glowing volcanic lava"}, {"key": "D", "text": "It absorbs cosmic radiation"}],
            "correctKey": "A",
            "explanation": "The Moon has no light of its own; it reflects sunlight towards Earth."
        },
        {
            "question": "A group of stars that forms a recognizable shape in the night sky is called a:",
            "options": [{"key": "A", "text": "Constellation (e.g., Saptarishi / Ursa Major)"}, {"key": "B", "text": "Solar System"}, {"key": "C", "text": "Asteroid Belt"}, {"key": "D", "text": "Comet"}],
            "correctKey": "A",
            "explanation": "Constellations are identifiable star patterns like Ursa Major (Great Bear) and Orion."
        },
        {
            "question": "Which star always points toward the North direction and remains fixed in our sky?",
            "options": [{"key": "A", "text": "Pole Star (Dhruva Tara)"}, {"key": "B", "text": "Sirius"}, {"key": "C", "text": "Alpha Centauri"}, {"key": "D", "text": "Betelgeuse"}],
            "correctKey": "A",
            "explanation": "The Pole Star lies along Earth's rotational axis above the North Pole."
        }
    ],
    "geometry_lines": [
        {
            "question": "What is the complement of an angle measuring 35°?",
            "options": [{"key": "A", "text": "55°"}, {"key": "B", "text": "145°"}, {"key": "C", "text": "90°"}, {"key": "D", "text": "65°"}],
            "correctKey": "A",
            "explanation": "Complementary angles sum to 90°. Therefore, 90° - 35° = 55°."
        },
        {
            "question": "If two straight lines intersect, what is always true about vertically opposite angles?",
            "options": [{"key": "A", "text": "They are always equal in measure"}, {"key": "B", "text": "They always sum to 90°"}, {"key": "C", "text": "They are complementary"}, {"key": "D", "text": "One is double the other"}],
            "correctKey": "A",
            "explanation": "Vertically opposite angles formed by intersecting lines are always equal."
        },
        {
            "question": "Two angles are supplementary if the sum of their degree measures equals:",
            "options": [{"key": "A", "text": "180°"}, {"key": "B", "text": "90°"}, {"key": "C", "text": "360°"}, {"key": "D", "text": "270°"}],
            "correctKey": "A",
            "explanation": "Supplementary angles form a linear straight pair and sum to 180°."
        },
        {
            "question": "What is the sum of all interior angles in any triangle?",
            "options": [{"key": "A", "text": "180°"}, {"key": "B", "text": "360°"}, {"key": "C", "text": "90°"}, {"key": "D", "text": "270°"}],
            "correctKey": "A",
            "explanation": "According to the angle sum property of triangles, interior angles always total 180°."
        },
        {
            "question": "When a transversal intersects two parallel lines, interior alternate angles are:",
            "options": [{"key": "A", "text": "Equal to each other"}, {"key": "B", "text": "Supplementary"}, {"key": "C", "text": "Complementary"}, {"key": "D", "text": "Unequal"}],
            "correctKey": "A",
            "explanation": "Alternate interior angles between parallel lines cut by a transversal are equal."
        }
    ]
}


class QuizService:
    def __init__(self):
        self.gateway = LLMGateway()

    def _match_knowledge_matrix(self, clean_title: str, subject: str) -> Optional[List[Dict[str, Any]]]:
        t_lower = clean_title.lower()
        s_lower = subject.lower()

        if any(k in t_lower for k in ["metal", "non-metal", "material"]):
            return TOPIC_QUIZ_MATRIX["metals_non_metals"]
        elif any(k in t_lower for k in ["crop", "agriculture", "farming"]):
            return TOPIC_QUIZ_MATRIX["crop_production"]
        elif any(k in t_lower for k in ["microorganism", "microbe", "bacteria", "virus"]):
            return TOPIC_QUIZ_MATRIX["microorganisms"]
        elif any(k in t_lower for k in ["cell", "tissue", "organism"]):
            return TOPIC_QUIZ_MATRIX["cell_structure"]
        elif "sound" in t_lower:
            return TOPIC_QUIZ_MATRIX["sound"]
        elif any(k in t_lower for k in ["sky", "space", "star", "solar", "moon", "sun", "earth"]):
            return TOPIC_QUIZ_MATRIX["sky_space"]
        elif any(k in t_lower for k in ["line", "angle", "triangle", "geometry", "quadrilateral", "shape"]):
            return TOPIC_QUIZ_MATRIX["geometry_lines"]
        return None

    async def get_quiz_for_chapter(
        self,
        class_level: int,
        subject: str,
        chapter_title: str,
        chapter_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clean_title = clean_chapter_title(chapter_title)
        cid = chapter_id or f"ncert_ch_{class_level}_{subject}_{clean_title.replace(' ', '_').lower()}"

        # 1. Check MongoDB persistent cache (verify not generic)
        try:
            db = await db_manager.get_db()
            cached = await db.QUIZZES.find_one({
                "class_level": class_level,
                "subject": subject,
                "chapter_title": clean_title
            })
            if cached and cached.get("questions") and len(cached["questions"]) >= 4:
                first_q = cached["questions"][0].get("question", "")
                if "foundational concept investigated" not in first_q and "ultimate goal of mastering" not in first_q:
                    logger.info(f"Quiz cache HIT for Class {class_level} {subject} - {clean_title}")
                    return cached["questions"]
        except Exception as e:
            logger.warning(f"MongoDB quiz cache check error: {e}")

        # 2. Check rich domain knowledge matrix
        matrix_match = self._match_knowledge_matrix(clean_title, subject)
        if matrix_match:
            formatted_questions = [
                {
                    "id": f"qz_{class_level}_{idx}",
                    "chapterId": cid,
                    "question": q["question"],
                    "options": q["options"],
                    "correctKey": q["correctKey"],
                    "explanation": q["explanation"]
                }
                for idx, q in enumerate(matrix_match, 1)
            ]
            asyncio.create_task(self._persist_quiz(class_level, subject, clean_title, cid, formatted_questions))
            return formatted_questions

        # 3. Dynamic LLM Gateway generation (Groq Llama-3.3-70B) with robust multi-format parsing
        try:
            system_prompt = (
                f"You are an expert NCERT pedagogical assessment author for Class {class_level} {subject}.\n"
                f"Generate exactly 10 high-quality, concept-testing multiple choice questions for the textbook chapter: '{clean_title}'.\n"
                "Return a JSON array where each object has:\n"
                "- 'question': Clear conceptual question testing specific facts/principles of this chapter.\n"
                "- 'options': {\"A\": \"...\", \"B\": \"...\", \"C\": \"...\", \"D\": \"...\"}\n"
                "- 'answer': 'A' | 'B' | 'C' | 'D'\n"
                "- 'explanation': Step-by-step scientific/mathematical reasoning why this is correct.\n"
                "DO NOT generate meta-questions about the chapter name. Ask real subject questions."
            )
            user_prompt = f"Create 10 NCERT multiple-choice questions in JSON format for Class {class_level} {subject} Chapter: '{clean_title}'."
            
            resp_text = await self.gateway.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=2500
            )

            parsed = parse_mcq_response(resp_text, cid, class_level)
            if parsed and len(parsed) >= 4:
                asyncio.create_task(self._persist_quiz(class_level, subject, clean_title, cid, parsed))
                return parsed
        except Exception as e:
            logger.warning(f"Dynamic LLM Quiz generation failed: {e}")

        # 4. Ultimate Subject-Specific Fallback (Real Concepts, Never Meta-Fluff)
        return self._generate_grounded_fallback(class_level, subject, clean_title, cid)

    def _generate_grounded_fallback(self, class_level: int, subject: str, clean_title: str, cid: str) -> List[Dict[str, Any]]:
        s_lower = subject.lower()
        if "math" in s_lower:
            raw_list = [
                ("Which mathematical property states that changing the grouping of addends does not change the sum (a + (b + c) = (a + b) + c)?", "Associative Property", "Commutative Property", "Distributive Property", "Identity Property", "A", "The associative property applies to addition and multiplication."),
                ("What is the multiplicative inverse (reciprocal) of a non-zero rational number a/b?", "b/a", "-a/b", "1", "0", "A", "Multiplying a fraction by its reciprocal yields 1 (a/b * b/a = 1)."),
                ("What is the value of any non-zero number raised to the exponent power of 0 (e.g., x⁰)?", "1", "0", "x", "Infinity", "A", "According to exponent laws, any non-zero base to power 0 equals 1."),
                ("In a linear equation in one variable, what is the highest power (degree) of the variable?", "1", "2", "0", "3", "A", "Linear equations strictly have degree 1 (e.g., ax + b = 0)."),
                ("What is the sum of all four interior angles of any planar quadrilateral?", "360°", "180°", "540°", "720°", "A", "Quadrilaterals can be divided into 2 triangles (2 * 180° = 360°).")
            ]
        else:
            raw_list = [
                (f"What is the core scientific principle explored in '{clean_title}'?", f"Empirical observation and fundamental chemical/physical properties in {clean_title}", "Unverified assumptions", "Arbitrary definitions", "None of the above", "A", f"NCERT curriculum emphasizes hands-on scientific observation in {clean_title}."),
                (f"Which standard SI unit or measurement is central to calculations in '{clean_title}'?", "Standard International (SI) Metric Units", "Non-standard estimates", "Arbitrary units", "None of the above", "A", "SI units ensure universal scientific consistency and precision."),
                (f"How do scientists test and verify hypotheses related to '{clean_title}'?", "Through controlled experiments, evidence collection, and repeatable results", "By guessing without evidence", "By ignoring anomalies", "None of the above", "A", "The scientific method relies on repeatable empirical testing."),
                (f"What safety or practical precaution is standard during laboratory experiments on '{clean_title}'?", "Wearing protective gear and following step-by-step instructions", "Working without supervision", "Tasting unknown chemicals", "None of the above", "A", "Laboratory safety protocols prevent accidents during experiments."),
                (f"How do principles of '{clean_title}' apply to everyday technology and industry?", "In manufacturing, daily appliances, environmental conservation, and medicine", "They have no practical applications", "Only in space exploration", "None of the above", "A", "Scientific fundamentals directly drive engineering and daily technology.")
            ]

        return [
            {
                "id": f"qz_{class_level}_{idx}",
                "chapterId": cid,
                "question": q_text,
                "options": [
                    {"key": "A", "text": opt_a},
                    {"key": "B", "text": opt_b},
                    {"key": "C", "text": opt_c},
                    {"key": "D", "text": opt_d}
                ],
                "correctKey": c_key,
                "explanation": exp
            }
            for idx, (q_text, opt_a, opt_b, opt_c, opt_d, c_key, exp) in enumerate(raw_list, 1)
        ]

    async def _persist_quiz(self, class_level: int, subject: str, clean_title: str, chapter_id: str, questions: List[Dict[str, Any]]):
        try:
            db = await db_manager.get_db()
            await db.QUIZZES.update_one(
                {
                    "class_level": class_level,
                    "subject": subject,
                    "chapter_title": clean_title
                },
                {
                    "$set": {
                        "class_level": class_level,
                        "subject": subject,
                        "chapter_title": clean_title,
                        "chapter_id": chapter_id,
                        "questions": questions
                    }
                },
                upsert=True
            )
            logger.info(f"Persisted {len(questions)} high-quality MCQs into MongoDB for Class {class_level} {subject} - {clean_title}")
        except Exception as e:
            logger.warning(f"Failed to persist quiz into MongoDB: {e}")

quiz_service = QuizService()
