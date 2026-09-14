"""
Flashcard Service - Intelligent Pedagogical Note & Revision Generator (Silicon Project V3)
Generates high-value, age-appropriate, grounded flashcards for Class 1-10 students.
Integrates:
1. Title & Chapter number normalization.
2. MongoDB persistent caching (`FLASHCARDS` collection).
3. Dynamic RAG chunk extraction & LLM Gateway generation (4 Pedagogical Archetypes).
4. Rich topic-specific & subject-aware deterministic fallback matrix (Zero meta-curriculum fluff).
"""

from __future__ import annotations
import re
import json
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager
from models.llm_gateway import LLMGateway

GRADIENT_PALETTES = [
    "from-amber-400 to-orange-500",
    "from-sky-400 to-blue-500",
    "from-emerald-400 to-teal-500",
    "from-purple-400 to-indigo-500",
    "from-rose-400 to-pink-500",
    "from-cyan-400 to-blue-500",
    "from-amber-400 to-yellow-500",
    "from-indigo-400 to-violet-500",
    "from-green-400 to-emerald-500",
    "from-fuchsia-400 to-pink-500",
]

def clean_chapter_title(raw_title: Optional[str]) -> str:
    """Strips chapter numbers, prefixes, and punctuation (e.g. '10: Our Sky' -> 'Our Sky')."""
    if not raw_title:
        return "Core Concepts"
    clean = raw_title.strip()
    clean = re.sub(r'^(?:Chapter\s*)?\d+[\s:.\-–—]+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'^\d+\s*:\s*', '', clean)
    clean = re.sub(r'[*_#]+', '', clean).strip()
    return clean or raw_title.strip()

# Rich Domain Matrix of Real Student Concepts
TOPIC_KNOWLEDGE_MATRIX: Dict[str, List[Dict[str, str]]] = {
    "sky_space": [
        {
            "type": "🌟 Key Vocabulary",
            "term": "Constellation",
            "question": "What is a Constellation?",
            "answer": "A group of stars that forms a recognizable pattern in the night sky, such as Saptarishi (the Great Bear) or Orion the Hunter."
        },
        {
            "type": "💡 Core Concept",
            "term": "Day and Night",
            "question": "What causes day and night on Earth?",
            "answer": "Earth continuously rotates on its own axis once every 24 hours. The side facing the Sun experiences daylight, while the opposite side experiences night."
        },
        {
            "type": "💡 Core Concept",
            "term": "The Sun",
            "question": "Why does the Sun appear so much bigger and brighter than other stars?",
            "answer": "The Sun is a star, but it looks huge and bright because it is about 150 million km away—millions of times closer to Earth than any other star in space!"
        },
        {
            "type": "🚀 Did You Know?",
            "term": "Moonlight",
            "question": "Does the Moon produce its own light?",
            "answer": "No! The Moon is a non-luminous body. It acts like a giant space mirror, reflecting sunlight down to our eyes on Earth."
        },
        {
            "type": "💡 Core Concept",
            "term": "Phases of the Moon",
            "question": "Why does the shape of the Moon seem to change throughout the month?",
            "answer": "As the Moon orbits Earth every 29.5 days, we see varying portions of its sunlit half, creating phases from New Moon (Amavasya) to Full Moon (Purnima)."
        },
        {
            "type": "🚀 Did You Know?",
            "term": "Speed of Sunlight",
            "question": "How long does sunlight take to travel from the Sun to Earth?",
            "answer": "Sunlight travels at the speed of light (300,000 km per second) and takes approximately 8 minutes and 20 seconds to reach Earth."
        },
        {
            "type": "🎯 Quick Revision",
            "term": "Pole Star (Dhruva Tara)",
            "question": "Which star stays in a fixed position and indicates the North direction?",
            "answer": "The Pole Star (Dhruva Tara) stays aligned above Earth's rotational axis and always points to the true North."
        },
        {
            "type": "🌟 Key Vocabulary",
            "term": "Solar System",
            "question": "What celestial bodies make up our Solar System?",
            "answer": "The Sun at the center, along with 8 planets (Mercury to Neptune), their natural satellites (moons), dwarf planets, asteroids, and comets."
        },
        {
            "type": "💡 Core Concept",
            "term": "Shadows",
            "question": "Why are shadows long in the morning and evening, but shortest at noon?",
            "answer": "Shadow length depends on the Sun's angle. Slanted morning and evening rays cast long shadows, while the overhead midday Sun casts the shortest shadow."
        },
        {
            "type": "🎯 Quick Revision",
            "term": "Telescope",
            "question": "What instrument do scientists use to view distant stars and planets?",
            "answer": "A telescope, which uses curved lenses and mirrors to collect and magnify light from distant celestial objects in the universe."
        }
    ],
    "water_nature": [
        {
            "type": "🌟 Key Vocabulary",
            "term": "Evaporation",
            "question": "What is Evaporation?",
            "answer": "The process by which liquid water heats up from sunlight and turns into invisible water vapor (gas) that rises into the air."
        },
        {
            "type": "💡 Core Concept",
            "term": "The Water Cycle",
            "question": "What are the 3 main stages of the continuous Water Cycle?",
            "answer": "1. Evaporation (water turns to vapor), 2. Condensation (vapor cools into clouds), 3. Precipitation (water falls as rain, snow, or hail)."
        },
        {
            "type": "🚀 Did You Know?",
            "term": "Blue Planet",
            "question": "Why is Earth called the 'Blue Planet'?",
            "answer": "About 71% of Earth's surface is covered by oceans, seas, rivers, and lakes, giving it a vibrant blue glow from outer space!"
        },
        {
            "type": "🎯 Quick Revision",
            "term": "Rainwater Harvesting",
            "question": "What is Rainwater Harvesting and why is it important?",
            "answer": "Collecting and storing rooftop rainwater for later use, which conserves clean water and recharges underground water tables."
        },
        {
            "type": "💡 Core Concept",
            "term": "Groundwater",
            "question": "How does water get stored deep under the soil as groundwater?",
            "answer": "Rainwater seeps through soil and porous rocks in a process called infiltration, filling underground aquifers."
        }
    ],
    "plants_biology": [
        {
            "type": "🌟 Key Vocabulary",
            "term": "Photosynthesis",
            "question": "What is Photosynthesis?",
            "answer": "The biological process by which green plants make their own food (glucose) using sunlight, water, carbon dioxide, and chlorophyll."
        },
        {
            "type": "💡 Core Concept",
            "term": "Chlorophyll & Stomata",
            "question": "What role do Chlorophyll and Stomata play in leaves?",
            "answer": "Chlorophyll is the green pigment that captures sunlight, while Stomata are microscopic pores on leaves that allow carbon dioxide in and oxygen out."
        },
        {
            "type": "🚀 Did You Know?",
            "term": "Oxygen Release",
            "question": "Why are green forests called the 'Lungs of the Earth'?",
            "answer": "Because during photosynthesis, plants absorb harmful carbon dioxide and release fresh oxygen that humans and animals breathe to survive."
        },
        {
            "type": "🎯 Quick Revision",
            "term": "Root Functions",
            "question": "What are the two primary functions of a plant's root system?",
            "answer": "1. Anchoring the plant firmly into the soil, and 2. Absorbing water and essential mineral nutrients from the ground."
        }
    ],
    "animals_adaptation": [
        {
            "type": "🌟 Key Vocabulary",
            "term": "Adaptation",
            "question": "What is an Adaptation in living organisms?",
            "answer": "Special physical features or behaviors developed over time that help an animal or plant survive and thrive in its natural environment."
        },
        {
            "type": "💡 Core Concept",
            "term": "Herbivores vs Carnivores",
            "question": "How do Herbivores, Carnivores, and Omnivores differ in their diets?",
            "answer": "Herbivores eat only plants (e.g. Deer, Cow); Carnivores eat other animals (e.g. Tiger, Lion); Omnivores eat both plants and meat (e.g. Bears, Humans)."
        },
        {
            "type": "🚀 Did You Know?",
            "term": "Camel Adaptation",
            "question": "How can camels survive for weeks in hot deserts without drinking water?",
            "answer": "Camels store energy-rich fat in their humps (which metabolizes into energy), produce very little sweat, and have wide padded feet to walk on sand."
        }
    ],
    "math_numbers": [
        {
            "type": "🌟 Key Vocabulary",
            "term": "Place Value",
            "question": "What is Place Value in arithmetic?",
            "answer": "The numerical value that a digit holds based on its position in a number (such as Units, Tens, Hundreds, Thousands)."
        },
        {
            "type": "💡 Core Concept",
            "term": "Prime Numbers",
            "question": "What is a Prime Number and why is 2 unique?",
            "answer": "A prime number has exactly two distinct positive divisors: 1 and itself (e.g. 2, 3, 5, 7, 11). Number 2 is the smallest and ONLY even prime number."
        },
        {
            "type": "🎯 Quick Revision",
            "term": "Perimeter vs Area",
            "question": "What is the difference between Perimeter and Area of a 2D shape?",
            "answer": "Perimeter is the total boundary distance around a shape (sum of sides), while Area is the amount of 2D space enclosed inside the shape."
        }
    ]
}

def match_topic_key(clean_title: str, subject: str) -> str:
    """Matches a title and subject string to the most relevant rich domain topic."""
    t_lower = (clean_title + " " + subject).lower()
    
    if any(k in t_lower for k in ["sky", "sun", "moon", "star", "solar", "planet", "space", "astronomy", "universe", "earth", "day and night", "night"]):
        return "sky_space"
    elif any(k in t_lower for k in ["water", "rain", "river", "cloud", "ocean", "cycle", "drop", "weather", "monsoon"]):
        return "water_nature"
    elif any(k in t_lower for k in ["plant", "leaf", "leaves", "tree", "root", "flower", "seed", "photosynthesis", "crop", "agriculture", "forest"]):
        return "plants_biology"
    elif any(k in t_lower for k in ["animal", "bird", "insect", "habitat", "adaptation", "food chain", "wild", "creature", "organism"]):
        return "animals_adaptation"
    elif any(k in t_lower for k in ["math", "number", "shape", "fraction", "geometry", "perimeter", "area", "equation", "prime", "angle"]):
        return "math_numbers"
    return "sky_space" if "wond" in t_lower or "evs" in t_lower else "plants_biology"


class FlashcardService:
    """Production service for generating, caching, and serving pedagogical flashcards."""

    def __init__(self) -> None:
        self.gateway = LLMGateway()

    async def get_flashcards_for_chapter(
        self,
        class_level: int,
        subject: str,
        chapter_title: str,
        chapter_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clean_title = clean_chapter_title(chapter_title)
        cid = chapter_id or f"fc_cls_{class_level}_{clean_title.replace(' ', '_')}"

        # 1. Check MongoDB persistent cache (Instant <20ms delivery)
        try:
            db = await db_manager.get_db()
            cached_doc = await db["FLASHCARDS"].find_one({
                "class_level": int(class_level),
                "$or": [
                    {"clean_title": clean_title},
                    {"chapter_title": chapter_title},
                    {"chapter_id": chapter_id}
                ]
            })
            if cached_doc and cached_doc.get("cards") and len(cached_doc["cards"]) >= 5:
                logger.info(f"FlashcardService: Serving {len(cached_doc['cards'])} cached flashcards for Class {class_level} '{clean_title}'")
                return cached_doc["cards"]
        except Exception as e:
            logger.warning(f"FlashcardService: DB cache check notice: {e}")

        # 2. Try Dynamic RAG Chunk Retrieval + LLM Flashcard Generation
        try:
            db = await db_manager.get_db()
            chunks = await db["CHUNKS"].find({
                "$or": [
                    {"book_title": re.compile(re.escape(clean_title), re.IGNORECASE)},
                    {"topic": re.compile(re.escape(clean_title), re.IGNORECASE)},
                    {"chapter_name": re.compile(re.escape(clean_title), re.IGNORECASE)}
                ]
            }).limit(3).to_list(None)

            context_text = ""
            if chunks:
                context_text = "\n\n".join([c.get("chunk_text", "") for c in chunks if c.get("chunk_text")])

            cards = await self._generate_cards_with_llm(
                class_level=class_level,
                subject=subject,
                clean_title=clean_title,
                context_text=context_text,
                chapter_id=cid
            )

            if cards and len(cards) >= 5:
                # Save to MongoDB FLASHCARDS collection asynchronously
                asyncio.create_task(self._cache_cards_to_db(class_level, subject, clean_title, chapter_title, cid, cards))
                return cards

        except Exception as ex:
            logger.warning(f"FlashcardService: LLM Generation fallback triggered: {ex}")

        # 3. Deterministic Domain Matrix Fallback (High-Quality, Kid-Friendly, 100% Real Notes)
        return self._get_deterministic_domain_cards(class_level, subject, clean_title, cid)

    async def _generate_cards_with_llm(
        self,
        class_level: int,
        subject: str,
        clean_title: str,
        context_text: str,
        chapter_id: str
    ) -> List[Dict[str, Any]]:
        """Invokes LLMGateway to generate structured revision flashcards from chapter concepts."""
        prompt = (
            f"You are an expert children's educational content creator designing study flashcards for NCERT Class {class_level} {subject}.\n"
            f"Chapter Title: '{clean_title}'\n\n"
            f"{'Chapter Textbook Excerpt:' + context_text if context_text else ''}\n\n"
            f"Task: Create 8 to 10 engaging, kid-friendly revision flashcards for students in Class {class_level}.\n"
            f"Follow these 4 Essential Archetypes:\n"
            f"1. 🌟 KEY VOCABULARY: Define an essential word/term from this chapter in clear, simple words.\n"
            f"2. 💡 CORE CONCEPT: Explain a fundamental process, concept, or mechanism in the chapter.\n"
            f"3. 🚀 DID YOU KNOW?: A fascinating, memorable real-world fact or curiosity question.\n"
            f"4. 🎯 QUICK REVISION: A bite-sized concept check or memorable rule.\n\n"
            f"CRITICAL RULES:\n"
            f"- DO NOT ask meta-questions like 'What is the learning outcome?' or 'What curriculum standard is targeted?'.\n"
            f"- Write REAL educational questions and student revision answers directly about {clean_title}.\n"
            f"- Return ONLY a valid JSON object matching this schema:\n"
            f'{{"cards": [{{"term": "🌟 Key Term: [Name]", "question": "[Engaging question]", "answer": "[Clear, accurate student answer]"}}]}}'
        )

        raw_res = await self.gateway.generate(prompt, response_format={"type": "json_object"})
        data = json.loads(raw_res) if isinstance(raw_res, str) else raw_res
        raw_cards = data.get("cards", [])

        cards = []
        for idx, item in enumerate(raw_cards, 1):
            term = item.get("term") or f"💡 Concept {idx}"
            q = item.get("question") or f"What is the key takeaway of {clean_title}?"
            a = item.get("answer") or f"Fundamental concepts and observations in {clean_title}."
            color = GRADIENT_PALETTES[(idx - 1) % len(GRADIENT_PALETTES)]

            cards.append({
                "id": f"fc_{class_level}_{clean_title.replace(' ', '_')}_{idx}",
                "chapterId": chapter_id,
                "term": term,
                "question": q,
                "answer": a,
                "subject": subject,
                "color": color
            })
        return cards

    def _get_deterministic_domain_cards(
        self,
        class_level: int,
        subject: str,
        clean_title: str,
        chapter_id: str
    ) -> List[Dict[str, Any]]:
        """Returns structured, kid-friendly flashcards from the domain knowledge matrix."""
        topic_key = match_topic_key(clean_title, subject)
        template_items = TOPIC_KNOWLEDGE_MATRIX.get(topic_key, TOPIC_KNOWLEDGE_MATRIX["sky_space"])

        cards = []
        for idx, item in enumerate(template_items, 1):
            term_badge = f"{item['type']}: {item['term']}"
            color = GRADIENT_PALETTES[(idx - 1) % len(GRADIENT_PALETTES)]

            cards.append({
                "id": f"fc_{class_level}_{clean_title.replace(' ', '_')}_{idx}",
                "chapterId": chapter_id,
                "term": term_badge,
                "question": item["question"],
                "answer": item["answer"],
                "subject": subject,
                "color": color
            })
        return cards

    async def _cache_cards_to_db(
        self,
        class_level: int,
        subject: str,
        clean_title: str,
        chapter_title: str,
        chapter_id: str,
        cards: List[Dict[str, Any]]
    ) -> None:
        try:
            db = await db_manager.get_db()
            await db["FLASHCARDS"].update_one(
                {"class_level": int(class_level), "clean_title": clean_title},
                {"$set": {
                    "class_level": int(class_level),
                    "subject": subject,
                    "clean_title": clean_title,
                    "chapter_title": chapter_title,
                    "chapter_id": chapter_id,
                    "cards": cards
                }},
                upsert=True
            )
            logger.info(f"FlashcardService: Cached {len(cards)} flashcards to MongoDB for '{clean_title}'")
        except Exception as e:
            logger.warning(f"FlashcardService: Failed to cache cards to MongoDB: {e}")

flashcard_service = FlashcardService()
