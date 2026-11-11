"""Generate dummy resumes in ./resumes for testing (TXT, DOCX, PDF)."""

from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path("resumes")

RESUMES = [
    {
        "name": "john_doe", "title": "Backend Engineer", "years": 6,
        "skills": "Python, Django, PostgreSQL, Docker, AWS",
        "education": "B.S. Computer Science, State University (2018)",
        "fmt": "pdf",
    },
    {
        "name": "jane_smith", "title": "Data Analyst", "years": 4,
        "skills": "SQL, Python, Pandas, Tableau, Excel",
        "education": "M.S. Statistics, Northfield College (2020)",
        "fmt": "docx",
    },
    {
        "name": "priya_patel", "title": "Frontend Developer", "years": 3,
        "skills": "JavaScript, React, TypeScript, CSS, Figma",
        "education": "B.S. Information Technology, Tech Institute (2021)",
        "fmt": "txt",
    },
    {
        "name": "marcus_lee", "title": "Machine Learning Engineer", "years": 5,
        "skills": "Python, PyTorch, scikit-learn, Spark, Kubernetes",
        "education": "Ph.D. Computer Science, Coastal Tech (2019)",
        "fmt": "pdf",
    },
    {
        "name": "sara_kim", "title": "DevOps Engineer", "years": 7,
        "skills": "Terraform, Ansible, Linux, Jenkins, Go",
        "education": "B.S. Electrical Engineering, River University (2016)",
        "fmt": "docx",
    },
    {
        "name": "tom_brown", "title": "Product Manager", "years": 8,
        "skills": "Roadmapping, Jira, SQL basics, A/B testing, Stakeholder management",
        "education": "MBA, Lakeside Business School (2017)",
        "fmt": "txt",
    },
]


def resume_text(r: dict) -> str:
    name = r["name"].replace("_", " ").title()
    return (
        f"{name}\n"
        f"{r['title']}\n"
        f"Email: {r['name']}@example.com | Phone: 555-0100\n\n"
        f"SUMMARY\n"
        f"{r['title']} with {r['years']} years of experience building reliable systems "
        f"and collaborating across teams.\n\n"
        f"SKILLS\n{r['skills']}\n\n"
        f"EXPERIENCE\n"
        f"- Senior {r['title']}, Acme Corp ({r['years'] - 2}-present)\n"
        f"  Led projects using {r['skills'].split(',')[0].strip()} and delivered measurable results.\n"
        f"- {r['title']}, Globex Inc ({r['years'] - 4}-{r['years'] - 2})\n"
        f"  Built and maintained core services.\n\n"
        f"EDUCATION\n{r['education']}\n"
    )


def write_txt(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_docx(path: Path, text: str) -> None:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(path)


def write_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for line in text.splitlines():
        c.drawString(50, y, line[:110])
        y -= 16
        if y < 50:
            c.showPage()
            y = 750
    c.save()


WRITERS = {"txt": write_txt, "docx": write_docx, "pdf": write_pdf}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for r in RESUMES:
        path = OUT / f"resume_{r['name']}.{r['fmt']}"
        WRITERS[r["fmt"]](path, resume_text(r))
        print(f"Created {path}")


if __name__ == "__main__":
    main()
