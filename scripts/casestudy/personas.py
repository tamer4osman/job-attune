# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Case-study personas: fictional applicants for a university PhD screening run.

All persons and their employment histories are fictional. Degree-issuing
institutions are used only as realistic alma maters; the hiring university
and its group are fictional. Job requirements were modelled on the published
eligibility criteria of the TU Berlin Machine Learning Group
(https://web.ml.tu-berlin.de/jobs), retrieved 2026-11-11.

Each persona lists its files with the role the CONTENT actually plays
(`kind`), which for the planted-mistag candidates deliberately contradicts
what the filename suggests. `strength` is the screening ground truth used
to sanity-check the engine's ranking.
"""

PERSONAS = [
    {
        "folder": "jana_weber",
        "strength": "high",
        "lang": "en",
        "challenge": "baseline",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Jana Weber
Berlin, Germany - jana.weber@example.org

# Education
MSc Computer Science, Technische Universitaet Berlin (2021 - 2024), grade 1.2.
Thesis: "Efficient Attention Mechanisms for Long-Document Classification",
supervised at the research group for scalable learning systems; the code and
trained checkpoints were released under an open licence.
BSc Computer Science, Universitaet Heidelberg (2017 - 2021).

# Research experience
Student research assistant, research group for scalable learning systems (2022 - 2024).
Implemented and benchmarked transformer baselines for document classification;
built the group's experiment-tracking setup on GitLab and maintained the
reproducibility checklist for all publications.

# Publications
First-author workshop paper: "Sparse Attention Windows for Long-Document
Classification", Workshop on Efficient Methods for Deep Learning (2024).

# Skills
Python (5 years), PyTorch, JAX, NumPy, pandas, Git and GitLab CI, applied
statistics and hypothesis testing, machine learning, deep learning.
Experience presenting research: three group-internal and one workshop talk.

# Teaching
Teaching assistant for the Machine Learning course (2 semesters): weekly
tutorials, supervision of 30 students, grading and exam review sessions.

# Languages
German (native), English (C1, working language of my MSc programme).
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Members of the Selection Committee,

I am writing to apply for the position of Doctoral Researcher in Machine
Learning at your faculty. My Master's thesis on efficient attention
mechanisms convinced me that I want to spend my doctoral years on the design,
development, and analysis of novel machine learning methods rather than only
applying them.

During two years as a student research assistant I learned how collaborative
research works in practice: shared codebases, reproducibility checklists, and
honest reporting of negative results. I presented our workshop paper myself
and enjoy communicating technical content to both experts and
non-specialists - a skill I sharpened while tutoring thirty students in the
Machine Learning course.

Interdisciplinary collaboration attracts me in particular: your group's
projects with medical imaging partners match my interest in methods that
must work outside clean benchmark conditions. I strongly identify with your
stated values of scientific integrity and open science; my thesis artifacts
are publicly archived, and I documented every experimental decision in a
preregistered log.

I would be glad to contribute Python, PyTorch, and JAX expertise, experience
with statistical evaluation, and genuine enthusiasm for teaching assistance
to your group.

Sincerely,
Jana Weber
"""},
        ],
    },
    {
        "folder": "lukas_hoffmann",
        "strength": "high",
        "lang": "de",
        "challenge": "german-language packet",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Lukas Hoffmann
Stuttgart, Deutschland - lukas.hoffmann@example.org

# Bildungsweg
MSc Informatik, Universitaet Stuttgart (2020 - 2023), Abschlussnote 1.5.
Schwerpunkte: maschinelles Lernen, Statistik, verteilte Systeme.
Masterarbeit: "Kalibrierung neuronaler Netze unter Verteilungsverschiebung".
BSc Informatik, Universitaet Stuttgart (2016 - 2020).

# Berufserfahrung
Werkstudent Data Engineering, Automotive-Zulieferer (2021 - 2023): Aufbau von
Datenpipelines und Auswertung von Sensordaten mit Python.
Forschungspraktikum am Institut fuer Statistik und Stochastik (2022):
Bootstrap-Verfahren und Konfidenzintervalle fuer Modellgueten.

# Kenntnisse
Python (4 Jahre), PyTorch, NumPy, Git, Statistik und Wahrscheinlichkeitstheorie,
maschinelles Lernen, quantitative Auswertungsmethoden.

# Lehre
Tutor fuer die Vorlesung Statistik (3 Semester): Uebungsgruppen mit je 20
Studierenden, Korrektur und Klausurnachbereitung.

# Sprachen
Deutsch (Muttersprache), Englisch (C1).
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
Sehr geehrte Damen und Herren,

hiermit bewerbe ich mich um die Position als Doktorand in Ihrer
Machine-Learning-Gruppe. Die Kalibrierung neuronaler Netze unter
Verteilungsverschiebung - das Thema meiner Masterarbeit - hat mir gezeigt,
wie viel spannende Grundlagenforschung zwischen Statistik und Deep Learning
liegt.

In meiner Zeit als Werkstudent und Tutor habe ich gelernt, technische Inhalte
verstaendlich zu kommunizieren und im Team zu arbeiten: Pipelines, die andere
weiterverwenden koennen, Uebungsgruppen, die wirklich fragen. Offene Wissenschaft
ist fuer mich selbstverstaendlich: meine Masterarbeit inklusive Code und Daten
ist oeffentlich dokumentiert.

Ihre interdisziplinaren Projekte und der Anspruch wissenschaftlicher Integritaet
sprechen mich sehr an. Ich bringe solide Python- und PyTorch-Erfahrung,
statistisches Grundverstaendnis und Freude an Lehre mit.

Mit freundlichen Gruessen
Lukas Hoffmann
"""},
        ],
    },
    {
        "folder": "sara_klein",
        "strength": "mid-high",
        "lang": "en",
        "challenge": "PLANTED MISTAG #1: the file named anschreiben.pdf is actually the CV",
        "files": [
            {"name": "anschreiben.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Sara Klein
Berlin, Germany - sara.klein@example.org

# Education
MSc Physics, Humboldt-Universitaet zu Berlin (2020 - 2023), grade 1.3.
Thesis: "Bayesian Deep Learning for Particle Tracking" - developed a
probabilistic deep learning pipeline in PyTorch for tracking detectors.
BSc Physics, Freie Universitaet Berlin (2016 - 2020).

# Work experience
Research intern, national laboratory for high-energy physics (2022 - 2023):
statistical inference for detector data, uncertainty quantification,
code reviews in a 12-person team.

# Skills
Python (4 years), NumPy, PyTorch, Git, probability theory, statistics,
Bayesian inference, machine learning fundamentals.
Presented my thesis results at the laboratory's internal seminar series.

# Languages
German (native), English (C1).
"""},
            {"name": "motivation_final_v2.pdf", "kind": "cover", "lang": "en", "title": "Motivation Letter", "body": """
Dear Hiring Manager,

I am writing to apply for the Doctoral Researcher position in your Machine
Learning group. My background is theoretical and computational physics, and
my Master's work on Bayesian deep learning for particle tracking was the
moment I decided that research in machine learning methods - not only their
application - is what I want to do full time.

Physics taught me statistical rigour: honest error bars, controlled
experiments, and the discipline of writing down what the data can and cannot
support. I bring solid Python and NumPy experience, working knowledge of
PyTorch, and the perseverance of someone who has debugged detector pipelines
at three in the morning.

What draws me to your group is the interdisciplinary collaboration with
medicine and mobility partners; explaining models to domain experts is
communication I genuinely enjoy, as my outreach talks at public science
nights have shown. Open science matters to me: I publish my analysis code
and document my workflows.

Best regards,
Sara Klein
"""},
        ],
    },
    {
        "folder": "daniel_osman",
        "strength": "mid",
        "lang": "en",
        "challenge": "PLANTED MISTAGS #2+#3: cover letter saved as cv.pdf, CV saved as dokumente.pdf",
        "files": [
            {"name": "cv.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Sir or Madam,

I am writing to apply for the doctoral researcher position in machine
learning advertised by your faculty. I completed my Master of Science in
Computer Science at Technische Universitaet Darmstadt in 2023 and have since
been working as a software engineer, where I noticed how much I miss the
research questions of my thesis.

During my studies I focused on machine learning and statistical data
analysis; my thesis evaluated deep learning models for time-series anomaly
detection. Working in industry has made me a careful communicator - I write
design documents, present to stakeholders, and collaborate across teams
daily - and I would bring that professionalism back into academia.

Your group's combination of methodological depth and interdisciplinary
projects, together with its commitment to open science, is exactly the
environment I am looking for. I would be happy to contribute Python
engineering experience, teaching assistance from my tutoring semesters, and
a disciplined, collaborative work style.

Kind regards,
Daniel Osman
"""},
            {"name": "dokumente.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Daniel Osman
Darmstadt, Germany - daniel.osman@example.org

# Education
MSc Computer Science, Technische Universitaet Darmstadt (2020 - 2023).
Focus: machine learning, data mining, statistical data analysis.
Thesis: "Deep Autoencoder Approaches to Time-Series Anomaly Detection".
BSc Computer Science, Hochschule Darmstadt (2016 - 2020).

# Work experience
Software engineer, logistics platform provider (2023 - present): backend
services in Python, code reviews, mentoring of two working students.

# Skills
Python, PyTorch (course projects and thesis), Git, SQL, machine learning,
statistics. Communication: design documents, stakeholder presentations.

# Teaching
Tutor for Algorithms and Data Structures (1 semester).

# Languages
German (native), English (C1).
"""},
        ],
    },
    {
        "folder": "priya_sharma",
        "strength": "high",
        "lang": "en",
        "challenge": "industry-to-PhD switcher",
        "files": [
            {"name": "resume.pdf", "kind": "cv", "lang": "en", "title": "Resume", "body": """
# Priya Sharma
Berlin, Germany - priya.sharma@example.org

# Education
MSc Data Science, Technische Universitaet Muenchen (2020 - 2022).
Thesis: "Spatiotemporal Forecasting with Graph Neural Networks".
BSc Mathematics and Computer Science (2016 - 2020).

# Work experience
Data Scientist, Berlin mobility analytics company (2022 - present).
Demand-forecasting models in PyTorch serving 40 cities; designed and
analysed A/B experiments with proper statistical inference; mentor for two
interns; responsible for the model documentation standard.

# Skills
Python (6 years), PyTorch, pandas, SQL, Git, statistical inference,
experimental design, machine learning, deep learning, communication and
stakeholder presentations, teamwork in cross-functional squads.

# Languages
English (full professional proficiency), German (B1, currently in a B2
course), Hindi (native).
"""},
            {"name": "letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Hiring Team,

after four years in industry I am applying for the Doctoral Researcher
position in your Machine Learning group - because the questions that stayed
with me through every product cycle are research questions. Why does the
forecaster fail on new cities? What is the right uncertainty statement for
a planner? I want to work on the design and analysis of machine learning
methods themselves.

Industry has given me strengths a straight academic path does not always
provide: I ship reliable Python and PyTorch systems, I design experiments
with genuine statistical care, and I have presented model findings to
executives, city administrators, and engineers - communication under real
constraints. I mentor interns and enjoy it; supervision of students is one
of the reasons I am drawn back to a university.

Your group's interdisciplinary projects on urban mobility match my data
background exactly, and your open-science commitment mirrors how I already
work: documented, reproducible, and honest about limitations.

Sincerely,
Priya Sharma
"""},
        ],
    },
    {
        "folder": "tom_brandt",
        "strength": "weak",
        "lang": "en",
        "challenge": "must-have degree failure (BSc only, bootcamp)",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Tom Brandt
Leipzig, Germany - tom.brandt@example.org

# Education
BSc Applied Computer Science, University of Applied Sciences Leipzig
(2020 - 2023).

# Work experience
Frontend developer, digital agency (2023 - present): websites and dashboards
in JavaScript and React for retail clients.

# Further training
Machine Learning Bootcamp, 12 weeks full-time (2024): regression,
classification, model evaluation; final project on churn prediction in
Python using scikit-learn.

# Skills
JavaScript, React, Python (basic), Git, SQL (basic). Completed coursework in
statistics. Motivated to deepen machine learning and deep learning skills,
currently learning PyTorch.

# Languages
German (native), English (fluent).
"""},
            {"name": "cover.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Hiring Manager,

I am excited to apply for the doctoral researcher position in your machine
learning group. I know my path is unusual: I studied applied computer
science, work as a frontend developer, and discovered my enthusiasm for
machine learning through a twelve-week bootcamp, where my final project on
churn prediction was the most fun I have had with code.

I am fully aware that my theoretical foundations in machine learning and
statistics need deepening, and that my degree is a Bachelor's. I am a fast
learner, I communicate well with clients and colleagues every day, and I
bring real software engineering discipline to any team.

If there is any way to contribute to your group - as a doctoral candidate
with preparatory coursework or in another role - I would be grateful for
the chance to prove myself.

Kind regards,
Tom Brandt
"""},
        ],
    },
    {
        "folder": "emine_yildiz",
        "strength": "mid",
        "lang": "de",
        "challenge": "single-document packet (no cover letter)",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Emine Yildiz
Berlin, Deutschland - emine.yildiz@example.org

# Bildungsweg
MSc Informatik, Freie Universitaet Berlin (2021 - 2023), Abschlussnote 1.7.
Masterarbeit: "Federated Learning unter Ressourcenbeschraenkungen".
BSc Informatik, Universitaet Hamburg (2017 - 2021).

# Berufserfahrung
Werkstudentin ML-Engineering, Berliner Energie-Startup (2021 - 2023):
Verbrauchsprognosen mit PyTorch, Feature Engineering, Modellmonitoring.
Studentische Forschungsassistantin, Fachgebiet Verteilte Systeme (2022 - 2023).

# Kenntnisse
Python (4 Jahre), PyTorch, Git, Statistik, maschinelles Lernen,
kommunikation in interdisziplinaren Projekten.

# Lehre
Tutorin fuer Algorithmen und Datenstrukturen (2 Semester).

# Sprachen
Tuerkisch (Muttersprache), Deutsch (fliessend), Englisch (C1).
"""},
        ],
    },
    {
        "folder": "marco_ricci",
        "strength": "mid",
        "lang": "en",
        "challenge": "cryptic filenames (scan.pdf, bewerbung.pdf) - fallback guessing confirmed by F1",
        "files": [
            {"name": "scan.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Marco Ricci
Bologna, Italy - marco.ricci@example.org

# Education
MSc Computer Science, University of Bologna (2020 - 2023), grade 110/110.
Thesis: "Graph Neural Networks for City-Scale Traffic Prediction".
BSc Computer Science, University of Bologna (2016 - 2020).

# Work experience
Research intern, EU Horizon project on urban mobility (2023, 6 months):
built the traffic-prediction baseline, co-authored the project's public
deliverable, presented results at the consortium meeting in Brussels.

# Skills
Python, PyTorch, Git, statistics for spatial data, machine learning,
deep learning. Presentation skills from consortium meetings and two
university seminars.

# Languages
Italian (native), English (C1), German (A2, currently attending a course).
"""},
            {"name": "bewerbung.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Selection Committee,

I am writing to apply for the doctoral researcher position in machine
learning at your faculty. My Master's thesis applied graph neural networks
to city-scale traffic prediction, and the six months inside an EU mobility
project taught me how much careful statistics and clear communication matter
when research meets city administrators.

I enjoy the collaborative part of research: aligning a consortium, writing
deliverables that non-researchers actually read, presenting to a room with
engineers and urban planners in it. Interdisciplinary collaboration is what
I am looking for in a PhD, and your group's mobility projects are exactly
that.

I am learning German with genuine commitment and would value the chance to
deepen both my methods knowledge and my language skills in Berlin.

Best regards,
Marco Ricci
"""},
        ],
    },
    {
        "folder": "anna_kowalska",
        "strength": "top",
        "lang": "en",
        "challenge": "strongest candidate (publications, RA experience)",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Anna Kowalska
Warsaw, Poland - anna.kowalska@example.org

# Education
MSc Computer Science, Warsaw University of Technology (2019 - 2021),
with distinction. Thesis: "Contrastive Representations for Tabular Data".
BSc Computer Science (2015 - 2019).

# Work experience
Research Assistant, applied research institute for data analysis
(2022 - present). Contributions: benchmark suite for statistical learning
methods used in two institute publications; preprocessing library in C++
for performance-critical feature pipelines; mentoring of three bachelor
thesis students on evaluation methodology.

# Publications
First-author conference paper: "Calibrated Ensembles for Imbalanced Tabular
Learning", European conference on machine learning and data mining (2024).
Co-author workshop paper on evaluation practice (2023).

# Skills
Python (6 years), PyTorch, JAX, NumPy, Git, statistical learning, machine
learning, deep learning, C++, scientific writing and communication,
peer review for a workshop programme.

# Summer schools
European summer school on machine learning (2023).

# Languages
Polish (native), English (C1, publication language), German (A1).
"""},
            {"name": "motivation.pdf", "kind": "cover", "lang": "en", "title": "Motivation Letter", "body": """
Dear Members of the Selection Committee,

I am applying for the Doctoral Researcher position in your Machine Learning
group. Two years as a research assistant have shown me both sides of the
research life: the craft of building reliable experiments, and the joy of a
result that survives review. My first-author paper on calibrated ensembles
began as a small calibration bug nobody wanted to own - and became the
benchmark suite our institute now ships.

I want to deepen this into a doctorate: designing and analysing machine
learning methods with the statistical seriousness they deserve. I bring
PyTorch and JAX fluency, C++ where performance matters, and the habit of
documenting everything so that others can reproduce it - open science as
daily practice, not a slogan.

Supervising three bachelor students taught me that responsible supervision
is mostly listening and structuring; I would be glad to assist in teaching
again. Your group's interdisciplinary projects and its standards of
scientific integrity are precisely the environment I am seeking.

Sincerely,
Anna Kowalska
"""},
        ],
    },
    {
        "folder": "felix_baumann",
        "strength": "mid-low",
        "lang": "en",
        "challenge": "physics degree path (tests degree aliases), no publications",
        "files": [
            {"name": "CV_Physics.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Felix Baumann
Karlsruhe, Germany - felix.baumann@example.org

# Education
MSc Physics, Karlsruhe Institute of Technology (2021 - 2024), grade 1.6.
Thesis: "Simulation-Based Inference for Detector Data" - normalizing flows
and posterior estimation; the methodological core is machine learning.
BSc Physics, Karlsruhe Institute of Technology (2017 - 2021).

# Work experience
Student research assistant, detector laboratory (2021 - 2024): data
reduction pipelines, uncertainty propagation, code review in a small team.

# Skills
Python (4 years), NumPy, PyTorch (thesis work, self-taught beyond coursework),
Git, probability theory, statistics, simulation-based inference, machine
learning fundamentals. Presented my thesis at the laboratory colloquium.

# Languages
German (native), English (C1).
"""},
            {"name": "Cover_Letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Hiring Manager,

I am applying for the doctoral researcher position in your Machine Learning
group. My route into machine learning went through physics: my Master's
thesis on simulation-based inference for detector data is, at its core,
applied deep learning, and writing it convinced me that I want to work on
machine learning methods themselves rather than on detectors.

I offer strong probability theory and statistics, solid Python and NumPy,
working knowledge of PyTorch, and the honesty of a trained experimentalist:
I state what the data supports and what it does not. My communication
experience comes from colloquium talks and from explaining inference methods
to detector engineers.

I am realistic about my profile - no publications yet, and my machine
learning depth is self-taught beyond the coursework - but I am ambitious,
collaborative, and ready to grow inside a group that values scientific
integrity.

Best regards,
Felix Baumann
"""},
        ],
    },
    {
        "folder": "nora_falk",
        "strength": "mid-low",
        "lang": "en",
        "challenge": "coursework ML only, honest mid-low profile",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Nora Falk
Potsdam, Germany - nora.falk@example.org

# Education
MSc Computer Science, Universitaet Potsdam (2022 - 2024), grade 2.0.
Focus: machine learning and statistics coursework; thesis "Bias in Word
Embeddings for German News Texts".
BSc Media Informatics (2018 - 2022).

# Work experience
Working student, media analytics startup (2021 - 2024): data cleaning,
dashboards, support of evaluation studies.

# Skills
Python (3 years), scikit-learn, PyTorch (university course project),
Git, statistics coursework, machine learning fundamentals, communication
from client-facing analytics support.

# Languages
German (native), English (C1).
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Hiring Manager,

I am writing to apply for the doctoral researcher position in machine
learning. My Master's thesis on bias in German word embeddings was my first
real research experience, and it taught me two things: that I ask
research-shaped questions, and that I want proper methodological training -
which is exactly what a doctorate in your group would provide.

I will be honest about where I stand: my deep-learning experience so far is
one PyTorch course project and my thesis, and my statistics are solid
coursework rather than research practice. What I bring is curiosity, a
working student habit of careful data cleaning that nobody sees when it is
done well, and communication skills from three years of client contact.

The group's work on fair and interpretable methods is the reason this
position is my first choice; the commitment to responsible supervision
matters to me as much as the research itself.

Sincerely,
Nora Falk
"""},
        ],
    },
    {
        "folder": "omar_haddad",
        "strength": "mid",
        "lang": "en",
        "challenge": "combined letter+CV in one PDF (mixed content)",
        "files": [
            {"name": "application.pdf", "kind": "mixed", "lang": "en", "title": "Application (Letter + CV combined)", "body": """
Dear Hiring Manager,

I am writing to apply for the position of Doctoral Researcher in Machine
Learning at your faculty. I completed my Master of Science in Computer
Science at Technische Universitaet Hamburg in 2024; my thesis developed
anomaly detection with autoencoders in PyTorch for industrial sensor data.
Two semesters as a tutor for mathematics taught me that I enjoy teaching
assistance as much as research. I value your group's commitment to open
science and interdisciplinary collaboration, and I would be proud to
contribute to it.

Sincerely,
Omar Haddad

# Curriculum Vitae - Omar Haddad
# Education
MSc Computer Science, Technische Universitaet Hamburg (2021 - 2024), grade 1.9.
Thesis: "Autoencoder-Based Anomaly Detection for Industrial Sensor Data".
BSc Computer Science, Universitaet Aleppo (2014 - 2019).

# Work experience
Working student, autonomous driving startup (2022 - 2024): sensor data
quality analysis in Python, test automation.

# Skills
Python, PyTorch, Git, statistics, machine learning, communication in
international teams.

# Languages
Arabic (native), German (C1), English (C1).
"""},
        ],
    },
]
