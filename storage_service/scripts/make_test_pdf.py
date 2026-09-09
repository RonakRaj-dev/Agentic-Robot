"""Generate a small 3-page test PDF fixture."""
from pathlib import Path
import fitz


PAGES = [
    ("Chapter 1 - Introduction to Science",
     "Science is the systematic study of the structure and behaviour of the "
     "physical and natural world through observation and experiment. In this "
     "chapter we will explore what makes a question scientific and how "
     "scientific knowledge is built over time."),
    ("Chapter 2 - Materials and Their Properties",
     "Materials can be classified based on their properties such as hardness, "
     "transparency, solubility, and conductivity. Understanding these "
     "properties helps us choose the right material for the right purpose."),
    ("Chapter 3 - Motion and Force",
     "An object is said to be in motion if its position changes with respect "
     "to a reference point over time. Force is any push or pull that can "
     "change the state of motion of an object."),
]


def build_pdf(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for heading, body in PAGES:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 80), heading, fontsize=18, fontname="helv", color=(0, 0, 0))
        page.insert_textbox(fitz.Rect(72, 120, 523, 800), body, fontsize=12, fontname="helv",
                           color=(0, 0, 0), align=0)
    doc.save(str(output_path))
    doc.close()
    return output_path


if __name__ == "__main__":
    out = build_pdf(Path("tests/fixtures/sample_book.pdf"))
    print(f"Wrote fixture: {out} ({out.stat().st_size} bytes)")
