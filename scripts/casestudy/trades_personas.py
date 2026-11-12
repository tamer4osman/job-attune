# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Case-study personas: fictional applicants for a manual-labor screening run.

Role under test: Furniture Technician (Assembly & Service) at the fictional
Berlin furniture company "Kantholz Einrichtungswerke GmbH". All persons and
their employment histories are fictional. Employers are fictional or generic.
Profile requirements were modelled on published criteria for comparable
positions: Havertys "Furniture Service Technician" (valid driver's licence,
build and repair by hand), Cushman & Wakefield "Workplace Services Technician"
(hand and power tools, customer service, lifting), furniture installer
postings (reading assembly instructions and layout plans), and German
"Kuechen- und Moebelmonteur / Tischler" postings on the Bundesagentur fuer
Arbeit job board (Ausbildung als Tischler/Schreiner, Fuehrerschein Klasse B,
Montage beim Kunden im Team), all retrieved 2026-11-11.

`strength` is the coarse design label written at corpus-authoring time; the
detailed expert ranking is committed separately in
attune-data/casestudy-trades/expert/ BEFORE any engine run.

German documents use ASCII-folded spellings (ae/oe/ue) consistently, matching
how the profiling corpus handles non-ASCII-safe PDF producers.
"""

PERSONAS = [
    {
        "folder": "marcel_dittrich",
        "strength": "very high",
        "lang": "de",
        "challenge": "german-language packet; extra document zeugnisse.pdf (certificates, neither CV nor cover letter)",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Marcel Dittrich
Berlin, Deutschland - marcel.dittrich@example.org

# Beruflicher Werdegang
Montageleiter Kuechen- und Moebelmontage, Kuechenstudio Lichterfelde GmbH,
Berlin (2016 - heute): Leitung eines zweikoepfigen Montageteams, woechentlich
acht bis zehn Kuechen- und Moebelmontagen beim Kunden, Anleitung von zwei
Gesellen, Aufmass vor Ort, Kundenuebergabe und Reklamationsbearbeitung.
Geselle, Schreinerei Baumann, Berlin (2010 - 2016): Innenausbau und
Einbaumoebel, ab 2013 Montage von Einbaukuechen und Schrankwaenden beim
Kunden, einschliesslich Wasser- und Elektroanschluesse nach Herstellerangabe.

# Ausbildung
Tischlerausbildung, Schreinerei Baumann, Berlin (2007 - 2010),
Gesellenbrief, Abschlussnote gut.
Meisterpruefung Tischlerhandwerk, Handwerkskammer Berlin (2013).

# Kenntnisse
Hand- und Elektrowerkzeug jeder Art (Akkuschrauber, Stichsaege, Kreissaege,
Oberfraese), Montageanleitungen, Werkzeichnungen und Aufmassplaene lesen,
Moebelreparatur und Nachjustierung, Arbeitssicherheit auf Montagestellen im
bewohnten Umfeld.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (Grundkenntnisse).
Fuehrerschein Klasse B, Staplerschein (2021), eigene Werkzeugausstattung.
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrte Frau Lang,

Ihre Ausschreibung fuer die Stelle als Moebeltechniker (Montage und
Kundendienst) hat mich sofort angesprochen: genaue Arbeit mit Holz,
direkter Kundenkontakt und ein gut organisiertes Team sind genau die
Mischung, in der ich seit vierzehn Jahren arbeite.

Als Geselle und spaeter als Montageleiter habe ich gelernt, dass
Zuverlaessigkeit bei der Montage beim Kunden alles ist: puenktlich
erscheinen, sauber arbeiten, den Arbeitsplatz geschuetzt hinterlassen und
die Uebergabe in Ruhe erklaeren. Sicherheit geht dabei immer vor, beim
Heben genauso wie beim Arbeiten mit der Stichsaege oder an Wasser- und
Elektroanschluesen der Kueche. Die Zusammenarbeit im zweikoepfigen Team
teile ich so ein, dass Qualitaet und Tempo sich nicht gegenseitig
ausschliessen.

Kommunikation mit Kundinnen und Kunden gehoert fuer mich zum Handwerk:
Ich erklaere Ablauf und Dauer, hoere mir Wuensche an und finde Loesungen,
wenn eine Wand nicht gerade ist oder eine Lieferung fehlt. Sorgfalt bei
Aufmass und Nachjustierung erspart Ihnen Reklamationen.

Ich freue mich darauf, mein Werkzeug und meine Erfahrung in Ihr Team zu
bringen.

Mit freundlichen Gruessen
Marcel Dittrich
"""},
            {"name": "zeugnisse.pdf", "kind": "certificates", "lang": "de", "title": "Zeugnisse", "body": """
# Zeugnisse und Nachweise

Gesellenbrief Tischlerhandwerk, Handwerkskammer Berlin, Pruefungsjahr 2010,
Gesamtergebnis gut.
Meisterpruefungszeugnis Tischlerhandwerk, Handwerkskammer Berlin, 2013.
Staplerschein (Fahrerausweis fuer Flurforderzeuge), 2021.
Bescheinigung Arbeitsschutzunterweisung, Kuechenstudio Lichterfelde GmbH,
jadehrlich erneuert, zuletzt 2026.
"""},
        ],
    },
    {
        "folder": "tobias_lenz",
        "strength": "high",
        "lang": "de",
        "challenge": "baseline German packet",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Tobias Lenz
Berlin, Deutschland - tobias.lenz@example.org

# Berufserfahrung
Kuechen- und Moebelmonteur, Kuechenhaus Neukoelln GmbH, Berlin (2017 -
heute): Montage von Einbaukuechen und Moebeln beim Kunden, zu zweit im
Team, etwa sechs Montagen pro Woche, inklusive Wasser- und
Elektroanschluesse nach Herstellerangabe, Ausrichten und Nachjustieren,
Kundenuebergabe mit Erklaerung von Care-Produkten.
Montagehelfer, Spedition und Kuechenmontage (2015 - 2017): Anlieferung,
Vormontage in der Werkstatt, Mithilfe bei der Montage beim Kunden.

# Ausbildung
Schreinerausbildung, Tischlerei Wendland, Brandenburg (2011 - 2015),
Gesellenbrief, Abschlussnote gut.

# Kenntnisse
Akkuschrauber, Stichsaege, Kreissaege und Handwerkzeug, Montageanleitungen
und Werkzeichnungen lesen, Aufmass vor Ort, Moebelreparatur, Arbeitsschutz
und sicheres Heben, freundlicher Umgang mit Kundinnen und Kunden.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (Grundkenntnisse).
Fuehrerschein Klasse B, Erfahrung mit dem 3,5-t-Transporter des Betriebs.
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Krause,

als Kuechen- und Moebelmonteur mit acht Jahren Erfahrung beim Kunden suche
ich eine Stelle, an der ich mein Handwerk in einem starken Team weiter
entwickeln kann. Deshalb bewerbe ich mich bei Ihnen.

Zuverlaessigkeit ist fuer mich die Basis dieses Berufs: Der Kunde bekommt
 einen verbindlichen Termin, ich erscheine puenktlich und die Montage ist
am vereinbarten Tag fertig. Sicherheit habe ich von Anfang an gelernt -
sicheres Heben, fachgerechte Elektro- und Wasseranschluesse, geschuetzte
Boeden in bewohnten Wohnungen. Qualitaet zeigt sich bei mir im Detail:
gerade Schraenke, saubere Stosskanten und eine Ruhe uebergabe, in der ich
dem Kunden alles erklaere.

Die Zusammenarbeit im Zweierteam kenne ich seit Jahren, zuletzt als
etwas erfahrenerer Kollege, der neue Montagehelfer anlernt. Kommunikation
mit Kundinnen und Kunden ist mir wichtig: Ich hoere zu, erklaere klar und
bleibe auch bei unerwarteten Problemen, etwa einer schiefen Wand, sachlich
und loesungsorientiert.

Ich freue mich auf ein persoenliches Gespraech in Ihrer Schaubude.

Mit freundlichen Gruessen
Tobias Lenz
"""},
        ],
    },
    {
        "folder": "aisha_ndiaye",
        "strength": "high",
        "lang": "en",
        "challenge": "baseline English packet; trade training from warehouse logistics, not carpentry",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Aisha Ndiaye
Berlin, Germany - aisha.ndiaye@example.org

# Experience
Furniture installation technician, Bueroform Systemmoebel GmbH (office
furniture dealer), Berlin (2019 - present): installation of office furniture
systems - desks, benching, storage walls, acoustic panels - typically three
to five rooms per week; reading floor plans and installation drawings;
customer handover walkthroughs and snag fixing on the same day.
Warehouse logistics specialist and service technician, contract logistics
company, Berlin (2016 - 2019): goods receiving, picking, minor assembly of
flat-pack furniture before dispatch.

# Training
Vocational training as warehouse logistics specialist (Fachkraft fuer
Lagerlogistik), Berlin (2016 - 2018).
Forklift certificate (2020). Annual safety training incl. PPE and working
at height (scissor lift user, 2022).

# Skills
Hand and power tools (cordless drill, impact driver, jigsaw), assembly
instructions and floor plans, furniture installation, furniture adjustment
and minor repair, customer handover, safe lifting and load securing.

# Languages
English (fluent), German (B1, conversational; evening course, continuing),
French (native).
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Mr Brecht,

I am applying for the Furniture Technician (Assembly & Service) position.
For the last six years I have installed office furniture for a Berlin
dealer - from single day offices to whole floors - and what I like most is
the mix of precise hands-on work and direct contact with customers.

Reliable delivery is what our project managers praise me for: dates hold,
the site is swept, and the handover is done calmly and completely. Safety
is second nature for me - safe lifting, protecting finished floors, correct
use of PPE, and a tidy, secured work area in occupied buildings. Quality
for me means the snag list is empty on handover day, not next week.

Most installs run as a two-person crew, so teamwork with colleagues,
electricians and facility managers is my daily routine. Communication with
customers matters: I explain what will happen, listen to wishes, and find
a practical solution when a wall is not straight or a part is missing.

I would like to bring this routine to kitchens and fitted wardrobes at
Kantholz and grow with your service team.

Sincerely,
Aisha Ndiaye
"""},
        ],
    },
    {
        "folder": "grzegorz_nowak",
        "strength": "high-mid",
        "lang": "en",
        "challenge": "EU-cross-border joiner; German B1 (good command), English packet",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Grzegorz Nowak
Frankfurt (Oder), Germany - grzegorz.nowak@example.org

# Experience
Installer, furniture installation crews for a Polish kitchen and wardrobe
manufacturer (2018 - present): assembling fitted wardrobes and kitchens at
customer homes across Germany, three to five installations per week, including
water connections for sinks; final adjustment and customer handover.
Cabinetmaker, furniture workshop, Poznan (2012 - 2018): production of
case furniture, veneering, edge banding, pre-assembly of carcases.

# Training
Vocational training in joinery (certified, Poznan, 2010 - 2012).

# Skills
Hand and power tools (cordless drill, jigsaw, circular saw, planer),
assembly instructions and technical drawings, furniture installation,
furniture repair, safe lifting and transport, customer contact in German
and English.

# Languages
Polish (native), German (B1, good command, daily use on German sites),
English (intermediate).

# Other
Driving license class B, regular experience driving a 3.5 t van with
trailer to customer sites.
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Ms Vogel,

I have been installing kitchens and fitted wardrobes in German homes for
seven years, first from Poznan, now living in Frankfurt (Oder). I would
like to bring this experience to your assembly and service team.

My crews are known to be reliable: we keep the promised date, protect the
customer's floors and furniture, and leave a clean site. Safety on site is
a strict routine for us - safe lifting, dust extraction while cutting, and
correct disposal of packaging. Quality is measurable: the door gaps are
even, the carcases sit true, and the handover is only done when everything
is adjusted.

Most of my work is in two-person crews, so teamwork comes naturally, and I
often lead the smaller jobs myself. Clear communication with customers is
part of my daily work - I explain the schedule in simple German, confirm
wishes, and solve problems on site when a wall is uneven or a part is
damaged.

I would be glad to show you my work in a trial week.

Sincerely,
Grzegorz Nowak
"""},
        ],
    },
    {
        "folder": "david_osei",
        "strength": "mid-high",
        "lang": "en",
        "challenge": "service-heavy profile (hotel maintenance), no carpentry apprenticeship",
        "files": [
            {"name": "resume.pdf", "kind": "cv", "lang": "en", "title": "Resume", "body": """
# Resume - David Osei
Berlin, Germany - david.osei@example.org

# Experience
Furniture service and maintenance technician, hotel group, Berlin (2020 -
present): repair and adjustment of guest-room furniture (chairs, desks,
casegoods), furniture installation during refurbishment projects, hanging
doors, lock and hardware replacement, painting and drywall touch-ups;
service requests from guests and direct customer contact during
refurbishment works; documenting work orders in the facility system.
Maintenance assistant, facility services provider (2018 - 2020): minor
repairs, furniture moves and assembly for offices, delivery driving.

# Training
Vocational training in facility services, Berlin (2017 - 2018).
Internal trainings: safe working at height, first aid (2023).

# Skills
Hand and power tools (cordless drill, jigsaw, sander, screwdriver set),
manufacturer assembly instructions, furniture repair and refurbishment,
painting and surface touch-up, customer service in occupied rooms, safe
lifting.

# Languages
English (native), German (B2, fluent), Twi (native).

# Other
Driving license class B.
"""},
            {"name": "letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Ms Lang,

You are looking for a furniture technician who can both install and
repair - that combination has been my daily work in hotels for five years.
When a guest-room wardrobe door no longer closes or a conference chair
wobbles, I am the one who fixes it before the next check-in.

I work with a clear routine: assess, measure, repair or replace, and hand
back on time - guests experience us as reliable, and that is the standard I
would bring to your customers. Safety matters in occupied buildings: safe
lifting, protected walkways, and clean, secured work areas are normal for
me, not an extra. Quality for me is a repair nobody notices afterwards -
even gaps, stable fittings, intact surfaces.

I am used to working alone in a structured way, and I coordinate daily
with housekeeping, reception and external trades. Communication with
guests and customers is part of my job: I explain what I will do, agree
times, and keep promises.

I look forward to showing you my repair book and references.

Sincerely,
David Osei
"""},
        ],
    },
    {
        "folder": "marco_bianchi",
        "strength": "mid-high craft, German must-have gap",
        "lang": "en",
        "challenge": "master-level restorer/cabinetmaker with weak German (A2, B1 in progress)",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Marco Bianchi
Berlin, Germany - marco.bianchi@example.org

# Experience
Cabinetmaker and antique furniture restorer, restoration workshop, Florence
(2009 - 2024): structural repair of case furniture, veneer and marquetry,
French polishing, surface restoration of listed pieces; consultation with
private clients and galleries; fitting restored pieces and built-in
wardrobes at client homes (delivery checks, on-site adjustment).
Joiner, furniture workshop, Florence (2006 - 2009): carcase construction,
assembly, surface work.

# Training
Vocational training in cabinetmaking, Florence (2003 - 2006).
Restoration academy, specialisation in furniture conservation, Florence
(2006 - 2007).

# Skills
Hand and power tools to master level (hand planes, chisels, saws, cordless
drill, jigsaw), workshop drawings and assembly instructions, furniture
repair and restoration, veneer and surface finishing, fitting and
adjustment of fitted furniture.

# Languages
Italian (native), English (fluent), German (basic coursework, A2;
currently attending a B1 course).

# Other
Driving license class B (EU).
"""},
            {"name": "letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Ms Vogel,

After fifteen years restoring antique furniture in Florence, I have moved
to Berlin for family reasons and would like to continue my craft with your
company - in restoration, service, and the fitting of fitted furniture.

My workshop years taught me care and quality at a level that is hard to
learn quickly: reading the material, preparing surfaces, working with
safety around finished and often irreplaceable pieces, and handing work
back only when it is right. Clients rely on us with their most valuable
furniture, and being reliable with dates, quotations and schedules was the
basis of our reputation.

At the workshop I worked alongside two colleagues for many years, so
teamwork in a small crew is familiar to me, and I enjoy communicating with
clients about options, costs and care of their pieces. My German is
currently at an early stage - I attend a B1 course twice a week and use
every opportunity to practise - so I would initially fit best where
technical skill matters most and customer dialogue can grow step by step.

I would be glad to demonstrate my craftsmanship in a practical trial.

Sincerely,
Marco Bianchi
"""},
        ],
    },
    {
        "folder": "julian_reuter",
        "strength": "junior",
        "lang": "en",
        "challenge": "junior: freshly completed apprenticeship, thin evidence volume",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Julian Reuter
Berlin, Germany - julian.reuter@example.org

# Experience
Junior furniture assembly technician, furniture workshop and installation
crew, Berlin (2025 - present): carpentry apprenticeship finished in June
2025; since then six months on a two-person installation crew assembling
fitted wardrobes at customer homes; preparation of parts in the workshop;
customer handovers together with the senior technician.
Apprentice, Tischlerausbildung at the same workshop (2021 - 2025):
workshop production, surface treatment, assembly of custom furniture,
final project graded good (Gesellenbrief).

# Training
Apprenticeship as Tischler (carpenter), Berlin (2021 - 2025),
journeyman certificate, grade good.

# Skills
Hand and power tools (own starter set: cordless drill, jigsaw, hand
tools), assembly instructions and workshop drawings, furniture assembly,
careful surface handling, safe lifting, polite customer contact under
supervision.

# Languages
German (native), English (B1).

# Other
Driving license class B.
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Mr Brecht,

I finished my apprenticeship as a carpenter this summer and have spent the
last six months on your competitor's installation crew - assembling fitted
wardrobes, learning from an experienced technician every day. Now I am
looking for a team where I can grow, and your assembly and service
department is exactly that.

What I can already do: prepare and pre-assemble parts correctly, work from
assembly instructions and drawings, use my tools safely, and keep a tidy,
protected work area in customers' homes. What I am still learning: the
speed of a full working day and handling difficult customers on my own -
my senior colleague currently leads that part and I support the handover.

I am dependable: my trainer could always rely on me to be on site on time
and to check my work twice. Quality matters more to me than speed -
straight cabinets, clean edges, no callbacks. I like working in a
two-person team, I ask questions early, and I am used to clear
communication with the workshop and with customers.

I would be happy to start with service calls and smaller installs.

Sincerely,
Julian Reuter
"""},
        ],
    },
    {
        "folder": "lena_hartmann",
        "strength": "mid, no formal vocational training",
        "lang": "en",
        "challenge": "career changer: proven gig assembly practice, but no apprenticeship (must-have gap)",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Lena Hartmann
Berlin, Germany - lena.hartmann@example.org

# Experience
Team lead, contract logistics warehouse, Berlin (2017 - present): leading a
team of twelve in goods receiving, planning daily work, quality checks,
onboarding new colleagues; weekend side jobs since 2023: flat-pack
assembly for a home-services platform - about 60 furniture assembly jobs
in customer homes (wardrobes, beds, desks, kitchen front swaps), customer
rating 4.9 of 5.
Warehouse assistant, online retailer (2014 - 2017): picking, packing,
furniture deliveries including final placement at customer homes.

# Courses
Evening woodworking course, Volkshochschule Berlin (2023, certificate of
participation): joinery basics, safe tool use (cordless drill, jigsaw,
hand tools).

# Skills
Flat-pack and modular furniture assembly, assembly instructions, hand and
power tools, furniture placement and adjustment, customer communication in
customer homes, safe lifting and manual handling, team leadership.

# Languages
German (native), English (C1).

# Other
Driving license class B; experience renting and loading a transport van
for weekend jobs.
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Ms Vogel,

mine is an unusual path to your advertisement: I lead a warehouse team on
weekdays and assemble furniture on weekends - and the more Saturday jobs I
do, the clearer it becomes that this craft, not logistics, is what I want
to do full-time.

From sixty assembly jobs in customers' homes I bring a simple standard:
arrive prepared, protect floors, check the parts list before starting, and
leave only when everything sits straight and I have walked the customer
through it. My 4.9 rating comes from being reliable - appointments hold,
problems are communicated early - and from treating every home with care.
Safety is part of my logistics training: safe lifting is my daily bread,
and I keep tool use disciplined and clean.

Leading a team of twelve has taught me teamwork from the other side of the
table - planning work, distributing it fairly, and communicating clearly.
I will not pretend I bring a carpentry apprenticeship; I bring proven
practice, an absurd amount of motivation, and the discipline to learn the
theory in evening classes step by step.

I would gladly prove myself in a trial day.

Sincerely,
Lena Hartmann
"""},
        ],
    },
    {
        "folder": "hakan_yilmaz",
        "strength": "mid, adjacent trade (plumber)",
        "lang": "de",
        "challenge": "plumber switching trades: all must-have words present via transferable claims, but zero furniture experience",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Hakan Yilmaz
Berlin, Deutschland - hakan.yilmaz@example.org

# Berufserfahrung
Sanitaer- und Heizungsinstallateur, Gebaeude- und Rohrtechnik Kreuzberg
GmbH, Berlin (2015 - heute): Installation von Bad- und Heizungsanlagen im
Neubau und bei Kunden im Bestand, Verlegung von Rohren, Montage von
Sanitaergegenstaenden, Anschluss von Kuechen und Geraeten an Wasser- und
Abwasserleitungen, Kundenkontakt und Uebergabe der Anlagen.
Auszubildender, Kunden -und Montagedienst (2011 - 2015): Montagehilfe,
Werkstatt, Baustellenvorbereitung.

# Ausbildung
Ausbildung zum Sanitaer- und Heizungsinstallateur, Berlin (2011 - 2014),
Gesellenbrief.

# Kenntnisse
Werkzeug und Maschinen des Installationshandwerks, Bauplaene und
Installationszeichnungen lesen, Aufmass vor Ort, sauberes Arbeiten im
bewohnten Umfeld, Arbeitssicherheit und sicheres Heben.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Tuerkisch (Muttersprache), Englisch
(Grundkenntnisse).
Fuehrerschein Klasse B, Firmenwagen mit Anhaenger.
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Krause,

nach zehn Jahren im Sanitaer- und Heizungshandwerk moechte ich den Beruf
wechseln und in die Moebelmontage einsteigen. Ihr Betrieb verbindet
Montage mit Kundendienst - genau die Arbeit, die ich mir fuer die
naechsten Jahre wuensche.

Was ich mitbringe: Ich lese Bauplaene und Installationszeichnungen seit
zehn Jahren, fuehre Aufmass vor Ort durch und arbeite jeden Tag mit
Werkzeug. Wasser- und Elektroanschluesse an Kuechen sind fuer mich
Alltagsgeschaeft, und ich kenne die Ansprueche beim Kunden: sauberes
Arbeiten in bewohnten Wohnungen, geschuetzte Boeden, verbindliche Termine,
sicheres Heben und eine ruhe Uebergabe mit Erklaerung.

Zuverlaessigkeit war in meinem Beruf immer entscheidend, denn ein
Wasserschaden verzeiht keine schlampige Arbeit. Qualitaet heisst fuer
mich: erst nachdenken, dann bohren. Die Zusammenarbeit im Zweierteam
kenne ich von Grossbaustellen, und Kommunikation mit Kundinnen und
Kunden gehoert seit Jahren zu meiner Taeglichkeit.

Was ich noch lernen muss, ist das Moebel-Handwerk im Detail - da bin ich
bereit, von Ihren erfahrenen Kolleginnen und Kollegen zu lernen und
zunaechst bei kleineren Montagen zu unterstuetzen.

Mit freundlichen Gruessen
Hakan Yilmaz
"""},
        ],
    },
    {
        "folder": "kevin_slomka",
        "strength": "mid-weak",
        "lang": "en",
        "challenge": "PLANTED MISTAGS #1+#2: cv.pdf contains the cover letter, dokumente.pdf contains the CV",
        "files": [
            {"name": "cv.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Hi,

I saw your ad for a furniture technician and here is my application. I
have been putting together furniture since my moving-company days - first
flat-pack assembly at delivery addresses, and since 2023 proper furniture
assembly jobs through a marketplace app, more than 200 of them, 4.7 stars.

I show up on time, I bring my own drill and tools, and I read the assembly
instructions before opening a single box - learned that the hard way once.
Customers like that I explain what I did and take the packaging with me.
My rule is simple: careful work, no scratches, no missing screws.

I grew up in Neukoelln, speak Berlin German natively, and I am used to
hard physical work. I would like to do this for one company now instead of
chasing app jobs all over the city - steady quality work in a team.

Hope to hear from you.

Kevin
"""},
            {"name": "dokumente.pdf", "kind": "cv", "lang": "en", "title": "Dokumente", "body": """
# Kevin Slomka - Documents
Berlin, Germany - kevin.slomka@example.org

# Work
Furniture assembly, self-employed via home-services marketplace app (2023
- present): furniture assembly in customer homes - wardrobes, beds, desks,
kitchen front swaps; own tools (cordless drill, hand tools); reading
assembly instructions; customer homes, rating 4.7 of 5.
Mover and delivery driver, moving company, Berlin (2019 - 2023): packing,
carrying, flat-pack assembly at delivery addresses, customer handover of
furniture, safe lifting and load securing.
Warehouse worker, logistics, Berlin (2017 - 2019).

# School
Realschulabschluss, Berlin (2014).

# Languages
German (native), English (good).

# Other
Driving license class B.
"""},
        ],
    },
    {
        "folder": "colin_murphy",
        "strength": "mid-weak for this role",
        "lang": "en",
        "challenge": "experienced installer with German A2 (beginner) - trade-strong, must-have language gap",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Colin Murphy
Berlin, Germany - colin.murphy@example.org

# Experience
Furniture installation technician, office fit-out contractor, London
(2021 - 2025): commercial furniture installations (desking, storage walls,
meeting booths) from layout plans and manufacturer instructions; site
walkthroughs with clients; snagging and adjustment visits.
Installer, furniture retailer, Dublin (2018 - 2021): home delivery,
furniture assembly and installation in customer homes, customer handover.

# Training
Carpentry apprenticeship, Dublin (2014 - 2018).

# Skills
Hand and power tools (impact driver, jigsaw, saws), installation plans and
assembly instructions, furniture installation, furniture repair, customer
walkthroughs and snagging, safe lifting, van driving.

# Languages
English (native), German (A2 beginner course, continuing weekly).

# Other
Driving license class B, clean record; experience driving 3.5 t vans in
city traffic. Relocated to Berlin in 2025 for family reasons.
"""},
            {"name": "letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Ms Vogel,

I moved to Berlin this year and would like to continue the work I know
best: installing furniture properly. Seven years in Dublin and London
taught me the whole cycle - reading plans, protecting the site, building
true, and walking the customer through the result.

On commercial fit-outs I learned to be reliable against a programme: when
the schedule says handover Friday, the client signs off Friday. Safety on
occupied sites is standard practice for me - safe lifting, protected
routes, PPE, clean areas. Quality is in the adjustments: even reveals,
true doors, no snag list at the end.

Installation is team work - I have run two-person crews as the senior
installer, so teamwork and short, clear communication on site come
naturally, and customers consistently rate my walkthroughs highly.

My German is still at the beginning (A2, weekly course), and I am
committed to improving it quickly - I already understand site instructions
better every week. I would start where the work plan and drawings lead the
way and grow into customer-facing service as my German grows.

Sincerely,
Colin Murphy
"""},
        ],
    },
    {
        "folder": "sofia_popescu",
        "strength": "low (negative control)",
        "lang": "en",
        "challenge": "negative control: design graduate without hands-on assembly evidence; decoy-free but must-fail on assembly, tools, training, German",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Sofia Popescu
Berlin, Germany - sofia.popescu@example.org

# Education
BA Interior Design, Academy of Applied Design, Berlin (2020 - 2023),
thesis on adaptable micro-apartment furniture.

# Experience
Working student, interior architecture studio, Berlin (2022 - 2023):
moodboards, CAD drawings, 3D visualisation, site visits with the project
manager, preparing presentation documents for clients.
Internship, furniture brand showroom (2022): showroom styling, product
presentations, ordering samples.

# Skills
CAD and 3D tools, technical drawings for interiors, material and finish
knowledge, presentation and documentation, project coordination.

# Languages
Romanian (native), English (fluent), German (A2, basic course).

# Interests
Furniture design, visiting workshops, learning about making.
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
Dear Ms Vogel,

I studied interior design because I love furniture - and I would love to
start my career at a company that actually builds and installs it. As a
junior technician I could contribute my drawing skills and my sense for
materials, and learn the workshop side step by step.

During my studio year I visited the workshop weekly, prepared drawings for
custom pieces, and watched our designs being built - my thesis on adaptable
micro-apartment furniture even got prototyped. I can read and produce
technical drawings, check measurements against plans on site, and document
what was built - skills that should help with accurate assembly work.

I know I have not yet worked on site as a fitter - that is exactly the
experience I am looking for. I am a fast learner, careful with materials,
and I communicate openly with clients and colleagues. My German is still
basic (A2), but I am enrolled in an intensive course this autumn.

I would be grateful for the chance to prove my motivation in a trial.

Sincerely,
Sofia Popescu
"""},
        ],
    },
]
