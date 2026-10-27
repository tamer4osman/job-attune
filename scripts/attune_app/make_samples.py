#!/usr/bin/env python3
"""Generate the Job Attune demo corpus: 6 candidate folders with PDFs.

Scenarios covered:
  james_okafor   cv.pdf + cover_letter.pdf        strong candidate (top)
  anna_schmidt   lebenslauf.pdf + anschreiben.pdf strong, German aliases
  maria_gomez    resume.pdf                       mid, no cover letter
  david_kim      cv.pdf + motivation.pdf          junior, partial evidence
  lena_braun     cv.pdf + cover.pdf               must-have gap (no Python)
  petr_novak     scan.pdf                         image-only PDF (unreadable)
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[2] / "attune-sample-data" / "candidates"


def make_pdf(path: Path, lines):
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 60
    for line in lines:
        c.setFont("Helvetica", 10)
        c.drawString(50, y, line)
        y -= 16
        if y < 50:
            c.showPage()
            y = height - 60
    c.save()


def image_only_pdf(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFillColorRGB(0.92, 0.92, 0.9)
    c.rect(0, 0, 600, 900, stroke=0, fill=1)
    c.setFillColorRGB(0.7, 0.7, 0.68)
    for i in range(40):
        c.circle(60 + (i * 37) % 480, 60 + (i * 53) % 780, 14, stroke=0, fill=1)
    c.save()


JAMES_CV = [
    "JAMES OKAFOR - Senior Data Engineer",
    "Contact: james.okafor.demo@example.org | +49 170 000 0001 | Berlin",
    "",
    "PROFILE",
    "Senior data engineer with 8 years of experience building batch and streaming",
    "pipelines for energy and mobility platforms. Strong ownership mindset.",
    "",
    "EXPERIENCE",
    "GridWorks Energy - Senior Data Engineer (2019-present)",
    "- Designed 40+ Apache Airflow DAGs orchestrating charge-point telemetry ETL.",
    "- Built streaming pipelines with Kafka and Spark Streaming at 2M events/hour.",
    "- Migrated the warehouse to AWS (Redshift, S3, Lambda); cut cost 30%.",
    "- Mentor two junior engineers; run weekly knowledge-sharing sessions.",
    "TransData GmbH - Data Engineer (2016-2019)",
    "- Developed Python ETL framework (pandas, SQLAlchemy) used by 4 teams.",
    "- Wrote complex SQL window functions for fleet utilisation reporting.",
    "",
    "EDUCATION",
    "MSc Computer Science, Technical University of Munich (2016)",
    "",
    "CERTIFICATIONS",
    "AWS Certified Data Analytics - Specialty (2022)",
    "",
    "SKILLS",
    "Python (expert), SQL (expert), Apache Airflow, Kafka, Spark Streaming,",
    "Docker, Kubernetes, AWS, Terraform, dbt",
    "",
    "LANGUAGES",
    "English C1 fluent | German B2 intermediate",
    "",
    "VALUES",
    "I believe in reliable engineering, open communication with stakeholders and",
    "sustainable infrastructure that lasts.",
]
JAMES_COVER = [
    "Dear Hiring Team,",
    "",
    "I am applying for the Senior Data Engineer position at NovaGrid Energy.",
    "Balancing renewable grid load is exactly the kind of problem I enjoy:",
    "safety first, then reliable engineering, then everything else.",
    "",
    "At GridWorks I own the telemetry platform end to end - from Kafka ingestion",
    "to dbt models to stakeholder dashboards. I communicated weekly with grid",
    "analysts and took accountability for the 99.95% pipeline SLA.",
    "",
    "Sustainability drives me: I want my work to accelerate the energy transition.",
    "",
    "Kind regards,",
    "James Okafor",
]

ANNA_CV = [
    "DR. ANNA SCHMIDT - Data Engineer / Data Platform",
    "Kontakt: anna.schmidt.demo@example.org | +49 171 000 0002 | Munchen",
    "",
    "PROFIL",
    "Data engineer with 6 years of experience in cloud data platforms, pipelines",
    "and analytics engineering. Focus on reliability and open communication.",
    "",
    "BERUFSERFAHRUNG",
    "Stadtwerke Digital - Senior Data Engineer (2021-present)",
    "- Built batch pipelines with Python and Airflow for metering data.",
    "- Modeled the analytical layer in SQL (dbt) on BigQuery and Redshift.",
    "- Containerised all services with Docker; deployed on AWS ECS.",
    "- Mentoring of two working students.",
    "Uni-Rechenzentrum - Data Engineer (2018-2021)",
    "- PostgreSQL administration and query optimisation for research data.",
    "",
    "AUSBILDUNG",
    "M.Sc. Computer Science, LMU Munchen (2018)",
    "",
    "ZERTIFIZIERUNGEN",
    "Google Professional Data Engineer (2023)",
    "",
    "SKILLS",
    "Python, SQL, Apache Airflow, dbt, Docker, AWS, PostgreSQL, GitLab CI",
    "",
    "SPRACHEN",
    "Deutsch Muttersprache | Englisch C1 verhandlungssicher",
    "",
    "WERTE",
    "Zuverlassiges Engineering, offene Kommunikation, Nachhaltigkeit.",
]
ANNA_COVER = [
    "Sehr geehrtes Team,",
    "",
    "hiermit bewirb ich mich als Senior Data Engineer bei NovaGrid Energy.",
    "Themen wie Sicherheit (safety first), verlassliches Engineering und",
    "Nachhaltigkeit entsprechen genau meiner Arbeitsweise.",
    "",
    "In meiner aktuellen Rolle baue ich Pipelines fur Zaehlerdaten und arbeite",
    "eng mit Netzanalysten zusammen. Ownership heisst fuer mich: SERVICE-Level",
    "zusagen und einhalten, Stakeholder frueh einbinden, klar kommunizieren.",
    "",
    "Mit freundlichen Gruessen,",
    "Anna Schmidt",
]

MARIA_CV = [
    "MARIA GOMEZ - Data Engineer",
    "Contact: maria.gomez.demo@example.org | +34 600 000 003 | Valencia",
    "",
    "PROFILE",
    "Data engineer with 4 years of experience in analytics pipelines and SQL",
    "modeling. Keen to move into renewable energy.",
    "",
    "EXPERIENCE",
    "RetailData - Data Engineer (2021-present)",
    "- Maintained 25 Python ETL jobs and SQL dbt models for sales analytics.",
    "- Orchestrated workflows in Apache Airflow; introduced data quality tests.",
    "- Worked with AWS S3 and Lambda for ingestion.",
    "",
    "EDUCATION",
    "BSc Computer Science, Universitat de Valencia (2020)",
    "",
    "SKILLS",
    "Python, SQL, Apache Airflow, dbt, Docker, AWS, Git",
    "",
    "LANGUAGES",
    "Spanish native | English C1",
    "",
    "VALUES",
    "Reliable engineering and clear communication.",
]

DAVID_CV = [
    "DAVID KIM - Junior Data Engineer",
    "Contact: david.kim.demo@example.org | +49 152 000 0004 | Hamburg",
    "",
    "PROFILE",
    "Junior data engineer, 1.5 years of experience, eager to grow in a",
    "sustainability-driven company.",
    "",
    "EXPERIENCE",
    "LogistikWorks - Working Student / Junior Data Engineer (2023-present)",
    "- Supported Python ETL scripts and SQL reports for warehouse ops.",
    "- Helped containerise services with Docker.",
    "",
    "EDUCATION",
    "BSc Business Informatics, HAW Hamburg (2023)",
    "",
    "BOOTCAMP",
    "Data Engineering Bootcamp, neue fische (2022, 12 weeks)",
    "",
    "SKILLS",
    "Python, SQL, Docker, Git, basic Airflow",
    "",
    "LANGUAGES",
    "German native | English B2",
    "",
    "VALUES",
    "Ownership, curiosity, open communication.",
]
DAVID_COVER = [
    "Dear Hiring Team,",
    "",
    "I would love to join NovaGrid Energy as a junior data engineer. Reliable",
    "engineering and sustainability motivate me every day. I am a fast learner,",
    "communicate openly and take ownership of my tasks.",
    "",
    "Best regards,",
    "David Kim",
]

LENA_CV = [
    "LENA BRAUN - Analytics Engineer",
    "Contact: lena.braun.demo@example.example | +49 176 000 0005 | Koeln",
    "",
    "PROFILE",
    "Analytics engineer with 5 years of experience in BI and SQL modeling.",
    "",
    "EXPERIENCE",
    "HandelsCloud - Analytics Engineer (2020-present)",
    "- Built SQL models (dbt) and dashboards for 200 store managers.",
    "- Led stakeholder workshops; strong communication with business teams.",
    "- Java microservices maintenance in an earlier role.",
    "",
    "EDUCATION",
    "MSc Information Systems, Universitaet Koeln (2020)",
    "",
    "SKILLS",
    "SQL, dbt, Tableau, Java, Git, stakeholder management",
    "",
    "LANGUAGES",
    "German native | English C1",
]
LENA_COVER = [
    "Dear Hiring Team,",
    "",
    "As an analytics engineer I bring deep SQL and stakeholder management",
    "skills. I care about reliable engineering and sustainability. I would be",
    "excited to learn Python on the job and grow with your platform team.",
    "",
    "Regards,",
    "Lena Braun",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = [
        ("james_okafor", [("cv.pdf", JAMES_CV), ("cover_letter.pdf", JAMES_COVER)]),
        ("anna_schmidt", [("lebenslauf.pdf", ANNA_CV), ("anschreiben.pdf", ANNA_COVER)]),
        ("maria_gomez", [("resume.pdf", MARIA_CV)]),
        ("david_kim", [("cv.pdf", DAVID_CV), ("motivation.pdf", DAVID_COVER)]),
        ("lena_braun", [("cv.pdf", LENA_CV), ("cover.pdf", LENA_COVER)]),
    ]
    for folder, files in plan:
        d = OUT / folder
        d.mkdir(parents=True, exist_ok=True)
        for name, lines in files:
            make_pdf(d / name, lines)
    d = OUT / "petr_novak"
    d.mkdir(parents=True, exist_ok=True)
    image_only_pdf(d / "scan.pdf")
    print("sample corpus written to", OUT)


if __name__ == "__main__":
    main()
