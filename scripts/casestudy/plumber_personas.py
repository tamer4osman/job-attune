# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Case-study personas: fictional applicants for a manual-labor screening run.

Role under test: Plumber / Sanitary & Heating Technician (SHK) at the
fictional Berlin plumbing contractor "Klarwasser SHK Technik GmbH". All
persons and their employment histories are fictional. Employers are
fictional or generic. Profile requirements were modelled on published
criteria for comparable positions: German "Anlagenmechaniker SHK"
(sanitary, heating and climate) postings on the Bundesagentur fuer Arbeit
job board (completed SHK vocational training, drinking-water and drainage
installation, heating systems, on-call rotation, Fuehrerschein Klasse B),
and standard English-language service-plumber postings (installation and
repair of water supply lines, drains and fixtures, water heaters, leak
diagnosis, customer-facing service calls), all retrieved 2026-11-11.

`strength` is the coarse design label written at corpus-authoring time; the
detailed expert ranking is committed separately in
attune-data/casestudy-plumber/expert/ BEFORE any engine run.

German documents use ASCII-folded spellings (ae/oe/ue) consistently, matching
how the profiling corpus handles non-ASCII-safe PDF producers.
"""

PERSONAS = [
    {
        "folder": "stefan_richter",
        "strength": "very high",
        "lang": "de",
        "challenge": "german-language packet; extra document zeugnisse.pdf (certificates, neither CV nor cover letter)",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Stefan Richter
Berlin, Deutschland - stefan.richter@example.org

# Beruflicher Werdegang
Vorarbeiter Service- und Montageteam, Berliner Rohrwerk Neukoelln GmbH, Berlin (2015 - heute): Leitung eines dreikoepfigen Teams,
taegliche Trinkwasser- und Abwasserinstallationen, Badmodernisierung von
der Entwässerung bis zum Waschtisch, Wechsel und Service von
Brennwertthermen und Waermepumpen, Gasleitungsarbeiten mit Abnahme,
Leckagesuche und Rohrbruchsanierung im bewohnten Umfeld, Teilnahme am
Bereitschaftsdienst und Notdienst am Wochenende.
Geselle Anlagenmechaniker SHK, Installateurmeister Brauer, Berlin
(2008 - 2015): Sanitaer- und Heizungsinstallation im Neubau und
Bestand, Kupferloeten und Pressfitting-Technik, Kundenuebergabe und
Reklamationsbearbeitung direkt beim Kunden.

# Ausbildung
Ausbildung zum Anlagenmechaniker SHK, Installateurmeister Brauer,
Berlin (2005 - 2008), Gesellenbrief, Abschlussnote gut.
Meisterpruefung im Sanitaer- und Heizungshandwerk, Handwerkskammer
Berlin (2014).

# Kenntnisse
Trinkwasserinstallation, Abwasserinstallation, Heizungsanlagen
(Brennwerttherme, Waermepumpe, Heizkoerpertausch), Gasinstallation,
Leckagesuche, Pressfitting und Kupferloet, Badmodernisierung,
Arbeitsschutz und Unfallverhuetung auf Montagestellen, Kundengespraech
und Aufmass vor Ort.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (Grundkenntnisse).
Fuehrerschein Klasse B, eigene Werkzeugausstattung, Atemschutz-Zertifikat und Schulung Arbeiten in bewohnten Wohnungen (2023).
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

Ihre Ausschreibung fuer die Stelle als Anlagenmechaniker SHK /
Sanitaer- und Heizungstechniker hat mich sofort angesprochen: saubere
Arbeit an Trinkwasser und Heizung, direkter Kundenkontakt und ein
fester zweikoepfiger Team-Einsatz sind genau die Arbeit, die ich seit
fuenfzehn Jahren mit Vergnuegen mache.

Als Vorarbeiter kenne ich beide Seiten des Handwerks: technische
Qualitaet beim Rohr und eine reibungslose Uebergabe beim Kunden. Ich
plane Material und Ablauf, halte die Baustelle im bewohnten Umfeld
sauber und erklaere der Kundin den Heizungskeller in Ruhe. Sicherheit
geht dabei immer vor - beim Heben, beim Loeten und im
Bereitschaftsdienst, wenn es schnell gehen muss und trotzdem nichts
schiefgehen darf.

Mein Meisterbrief gehoert fuer mich nicht ins Regal, sondern in die
Anleitung der Juengeren: Ich freue mich darauf, Ihr Team zu
verstaerken und Service-Bereitschaft mitzubauen.

Mit freundlichen Gruessen
Stefan Richter
"""},
            {"name": "zeugnisse.pdf", "kind": "certificates", "lang": "de", "title": "Zeugnisse und Nachweise", "body": """
# Zeugnisse und Nachweise - Stefan Richter

Gesellenbrief Anlagenmechaniker SHK, Handwerkskammer Berlin, 2008,
Abschlussnote gut.

Meisterbrief Sanitaer- und Heizungshandwerk, Handwerkskammer Berlin,
2014.

Teilnahmebescheinigung Arbeitsschutz und Unfallverhuetung, BG
Bau, 2023.

Erste-Hilfe-Kurs, DRK Berlin, 2024.

Schulung Brennwerttechnik und Waermepumpeninstallation, Herstellerschulung, 2022.

Nachweis Bereitschaftsdienst und Notdienst, Berliner Rohrwerk
Neukoelln GmbH, 2015 bis heute.
"""},
        ],
    },
    {
        "folder": "marek_kowalczyk",
        "strength": "high",
        "lang": "en",
        "challenge": "baseline English packet; EU-cross-border plumber with German B1 (learned for cross-border crews)",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Marek Kowalczyk
Wroclaw, Poland - marek.kowalczyk@example.org

# Work history
Owner and lead installer, Kowalczyk Sanitary Services, Wroclaw
(2018 - present): two-person firm for bathroom renovation and heating
service; water supply and drainage installation in residential blocks,
boiler replacement and radiator upgrades, leak detection and pipe
repair, direct customer handover and aftercare.
Plumber and heating fitter, Wod-Invest Installation Sp. z o.o.,
Wroclaw (2011 - 2018): sanitary and heating installation in new-build
and refurbishment; copper soldering and press-fitting technique; work
under a site master on gas boiler installs.

# Education and qualification
Vocational qualification as plumbing and sanitary installer
(fitter/journeyman), Technical School Wroclaw (2008 - 2011).
Continuous certification: heating systems and condensing boilers
(manufacturer training, 2022).

# Skills
Water supply installation, drainage installation, heating systems,
bathroom renovation, fixture installation (WC, washbasin, shower),
leak detection, press fittings and copper soldering, work safety on
occupied sites, customer communication and handover.

# Languages and other
Polish (native), German (B1 - daily use on cross-border crews in
Goeppingen and Berlin, 2023-2025), English (fluent).
Driving licence class B (company van routine, EU cross-border).
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
# Cover Letter

Dear Mr Brinkmann,

Your listing for a plumber / sanitary and heating technician caught my
attention because it describes exactly the mix I have been working in
for twelve years: installation quality at the pipe, and a calm,
orderly handover in front of the customer.

Since 2018 I have run a small two-person crew in Wroclaw: full
bathroom renovations, boiler swaps and radiator upgrades, leak repair
on occupied sites. Before that I spent seven years on new-build and
refurbishment sites, where I learned to solder, to press, and to keep
the work area safe and clean around tenants.

My German is at B1 level from two seasons of cross-border installation
crews; I understand instructions on site and can talk a customer
through the handover, and I am currently taking an evening course to
reach B2. I am used to working in a two-person team and to representing
the firm politely and reliably at the customer's home.

I would be glad to bring this routine to your Berlin crews.

Kind regards
Marek Kowalczyk
"""},
        ],
    },
    {
        "folder": "aylin_demir",
        "strength": "high",
        "lang": "de",
        "challenge": "baseline German packet (solid all-round journeywoman with gas, boiler service and on-call routine)",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Aylin Demir
Berlin, Deutschland - aylin.demir@example.org

# Beruflicher Werdegang
Gesellin Sanitaer- und Heizungsinstallation, Spreeinstallation GmbH,
Berlin (2018 - heute): Badmodernisierung im Bestand, Trinkwasser- und
Abwasserinstallation, Wechsel von Gasthermen und Brennwertgeraeten,
Heizkoerpertausch, Leckagesuche, wiederkehrende Montage im
zweikoepfigen Team mit Kundenuebergabe und Reklamationsbearbeitung,
rotation im Bereitschaftsdienst und Notdienst.
Ausbildung Anlagenmechaniker SHK, Spreeinstallation GmbH, Berlin
(2015 - 2018): Sanitaer-, Heizungs- und Klimatechnik, Gesellenbrief,
Abschlussnote gut.

# Kenntnisse
Trinkwasserinstallation, Abwasserinstallation, Heizungsanlagen
(Brennwerttherme, Gasthermenwechsel, Heizkoerper), Pressfitting- und
Loettechnik, Badmodernisierung mit Fliesenanschluss, Leckagesuche,
Arbeitsschutz und Unfallverhuetung, Kundenservice und Aufmass.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Tuerkisch (Muttersprache), Englisch (gute
Kenntnisse).
Fuehrerschein Klasse B, Firmenwagen-Routine auf Berliner Montagestellen.
Hersteller-Schulung Gasthermen und Waermepumpen (2021, 2024).
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

als Gesellin SHK mit neun Jahren Berliner Montagealltag kenne ich Ihre
Arbeit genau: modernisierte Baeder, warme Wohnungen und Kunden, die am
Ende der Uebergabe wissen, was sie bekommen haben. Genau dafuer stehe
ich mit meinem Namen.

Bei Spreeinstallation fuehre ich Badmodernisierungen von der
Entwaesserung bis zum Waschtisch, wechsle Brennwertthermen und halte
im Bereitschaftsdienst auch um drei Uhr nachts einen kuenhlen Kopf.
Wichtig ist mir dabei der Kundendialog: Ich erklaere vor der Arbeit,
was passiert, und danach, was zu tun ist. Reklamationen loese ich
beim ersten Besuch, wenn es geht.

Sicherheit ist fuer mich kein Poster in der Werkstatt, sondern
Arbeitsschutz beim Heben, beim Loeten und auf der Leiter - jeden Tag.
Ich arbeite gerne im zweikoepfigen Team und bringe Erfahrung mit,
Juengere im Handwerk anzuleiten.

Ich freue mich auf ein Gespraech in Ihrem Klarwasser-Team.

Mit freundlichen Gruessen
Aylin Demir
"""},
        ],
    },
    {
        "folder": "abdul_rahimi",
        "strength": "mid-high (language gap)",
        "lang": "de",
        "challenge": "master-level heating technician trained abroad, German A2 (B1 course ongoing) - trade-strong, must-have language gap",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Abdul Rahimi
Berlin, Deutschland - abdul.rahimi@example.org

# Beruflicher Werdegang
Heizungstechniker und Montageleiter, Kombi-Servis Gaziantep,
Tuerkei (2014 - 2023): Installation und Service von
Brennwertkesseln und Heizungsanlagen, Heizkoerpertausch,
Leckagesuche an Heizungsrohren, Kundendienst mit Uebergabe,
Anleitung von zwei Gesellen, Bereitschaftsdienst im Winter.
Geselle Heizungs- und Sanitaerinstallation, Kombi-Servis
Gaziantep, Tuerkei (2012 - 2014): Heizungsinstallation,
Trinkwasserleitungen, Badezimmer-Sanierung.

# Ausbildung
Ausbildung zum Heizungs- und Sanitaerinstallateur, Berufsschule
Gaziantep (2009 - 2012), Abschlusspruefung bestanden.
Meisterpruefung Heizungstechnik, Industrie- und Handelskammer
Gaziantep (2019).

# Kenntnisse
Heizungsanlagen, Brennwerttherme, Heizkoerper, Trinkwasserinstallation, Abwasserinstallation, Leckagesuche, Loet- und
Pressfitting-Technik, Arbeitsschutz, Kundenservice und Uebergabe.

# Sprachen und Sonstiges
Deutsch (A2, B1-Kurs laeuft, zweimal pro Woche), Tuerkisch
(Muttersprache), Arabisch (gute Kenntnisse), Englisch (Grundkenntnisse).
Fuehrerschein Klasse B (2024 in Berlin umgeschrieben).
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

ich bin Heizungstechniker mit Meisterpruefung aus der Tuerkei. Ich
arbeite seit elf Jahren an Heizungsanlagen: Brennwerttherme, Heizkoerper, Leckagesuche, Kundendienst. Jetzt wohne ich in Berlin und
suche eine Stelle als Anlagenmechaniker SHK.

Mein Deutsch ist noch nicht perfekt. Ich lerne jeden Tag und gehe
zweimal pro Woche zum B1-Kurs. Auf der Baustelle verstaende ich die
Anweisungen und ich kann mit Kunden einfach und langsam sprechen.
Mein Kollege sagt: Am Rohr sieht man, was ich kann.

Sicherheit ist mir sehr wichtig. Ich arbeite sauber und ich erklaere
dem Kunden die Uebergabe. Ich moechte gern in Ihrem zweikoepfigen
Team anfangen und mein Deutsch auf der Arbeit verbessern.

Mit freundlichen Gruessen
Abdul Rahimi
"""},
        ],
    },
    {
        "folder": "julia_krause",
        "strength": "mid (no SHK qualification)",
        "lang": "de",
        "challenge": "service-heavy facility-maintenance profile with hands-on minor plumbing repairs, no SHK apprenticeship (must-have qualification gap)",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Julia Krause
Berlin, Deutschland - julia.krause@example.org

# Beruflicher Werdegang
Technische Gebaeudebetreuung, Spree-Immobilien-Service GmbH, Berlin
(2019 - heute): Kleinreparaturen in 340 Verwaltungseinheiten, dazu
taeglich Sanitaerkleinreparaturen: Armaturenwechsel, Spuelkasten,
Siphon und Abflussreinigung, tropfende Leitungen provisorisch
abdichten bis der Installateur kommt, Koordination von Fachfirmen
fuer Badmodernisierung und Heizungsservice, Mieterkommunikation und
Uebergabeprotokolle, Dokumentation im CAFM-System.
Servicekraft Hauswirtschaft und Gebaeudepflege, Seniorenresidenz
Lindenhof, Berlin (2016 - 2019): Gebaeudepflege, Kleinreparaturen,
Kontakt zu Bewohnerinnen und Angehoerigen.

# Ausbildung und Qualifikation
Qualifizierung Gebaeude- und Objektbetreuung, IHK-Profil G (2019).
Erste-Hilfe-Kurs (2024). Teilnahme Arbeitsschutz-Unterweisungen
(BG Bau, jaehrlich).

# Kenntnisse
Sanitaerkleinreparaturen (Armatur, Spuelkasten, Siphon), Abflussreinigung, Fachfirmen-Koordination, Mieterkommunikation und
Beschwerdebearbeitung, Arbeitsschutz, Dokumentation.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (Grundkenntnisse).
Fuehrerschein Klasse B.
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

ich arbeite seit sechs Jahren in der technischen Gebaeudebetreuung und
kenne die Alltagsseite Ihres Handwerks: tropfende Armaturen, verstopfte
Abfluesse, ungeduldige Mieter und Notrufe am Freitagabend. Groessere
Installationsarbeiten lasse ich als Hausmeisterin zwar durch Fachfirmen
ausfuehren - aber vorbereitet, begleitet und abgenommen habe ich sie
selbst, und den Kundenkontakt vor und nach der Arbeit mache ich
selbst.

Ich moechte jetzt den Schritt in ein SHK-Team machen. Was ich
mitbringe: ruhige Haende bei Armaturen und Siphon, sehr viel Erfahrung
im Umgang mit Kundinnen und Kunden, Zuverlaessigkeit und Ordnung auf
der Baustelle. Was mir fehlt: die Ausbildung als Anlagenmechanikerin.
Dafuer bin ich offen: Ich lerne schnell und habe in sechs Jahren
gezeigt, dass ich Verantwortung trage.

Mit freundlichen Gruessen
Julia Krause
"""},
        ],
    },
    {
        "folder": "thomas_schreiber",
        "strength": "mid (career changer)",
        "lang": "de",
        "challenge": "career changer: self-taught bathroom renovations in own rentals plus helper stints, no apprenticeship (must-have qualification gap)",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Thomas Schreiber
Potsdam, Deutschland - thomas.schreiber@example.org

# Beruflicher Werdegang
Selbstaendiger Vermieter und Renovierer, eigene Mietobjekte,
Potsdam (2019 - heute): Komplettsanierung von vier Badezimmern
in eigenen Mietwohnungen - Abwasser- und Trinkwasserleitungen
verlegt, Geraete (WC, Waschbecken, Dusche) installiert,
Fliesenanschluss mit Handwerker-Unterstuetzung, Abnahme mit
Sachverstaendigem; dazu Helfereinsaetze in den Sommermonaten (2021-2024, je 6-8 Wochen) im Installateurbetrieb
Schreiber & Sohn, Potsdam: Rohrverlegung, Pressfitting,
Heizkoerpertausch unter Anleitung des Betriebsleiters.
Kurier- und Lagerleiter, Expresslogistik Potsdam GmbH (2012 -
2019): Tourenplanung, Fuhrpark, Kundenservice, Ausbildungsbetreuung.

# Kenntnisse (praktisch)
Trinkwasser- und Abwasserinstallation (Grundkenntnisse bis
selbstaendige Ausfuehrung unter Pruefung), Pressfitting,
Geraeteinstallation (WC, Waschbecken, Dusche), Heizkoerpertausch, Leckageortung mit Zuhoergeraet, Arbeitsschutz.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (gute Kenntnisse).
Fuehrerschein Klasse B und C.
"""},
            {"name": "motivation.pdf", "kind": "cover", "lang": "de", "title": "Motivationsschreiben", "body": """
# Motivationsschreiben

Sehr geehrter Herr Brinkmann,

ich moechte den Berufwechsel ins SHK-Handwerk machen - und zwar nicht
aus Stimmung, sondern aus Ueberzeugung: In den letzten sechs Jahren
habe ich vier Badezimmer in meinen eigenen Mietwohnungen komplett
saniert, vom Rohr bis zum Waschtisch, mit Pruefung durch den
Sachverstaendigen bei jeder Abnahme. Im Sommer arbeite ich seit vier
Jahren als Helfer im Betrieb meines Vetters, zuletzt bei
Heizkoerpertausch und Rohrverlegung unter Anleitung.

Mir ist klar, dass mir die Ausbildung als Anlagenmechaniker SHK
fehlt. Ich bringe aber mit: handwerkliche Neugier, kundenorientierte
Ruhe aus sechs Jahren Logistik-Kundenservice, Zuverlaessigkeit und
eine gesunde Portion Respekt vor Trinkwasser und Gas. Wenn Sie
wollen, unterstuetze ich eine Externe Pruefung oder Teilzeitausbildung.

Mit freundlichen Gruessen
Thomas Schreiber
"""},
        ],
    },
    {
        "folder": "felix_gruenwald",
        "strength": "junior (thin evidence)",
        "lang": "de",
        "challenge": "junior: freshly completed apprenticeship, thin evidence volume",
        "files": [
            {"name": "lebenslauf.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Felix Gruenwald
Berlin, Deutschland - felix.gruenwald@example.org

# Werdegang
Anlagenmechaniker SHK (Gesellenbrief 2026), Roggentin Haustechnik
GmbH, Berlin: Ausbildung 2022 - 2026, seit Abschluss in der
Festanstellung; Sanitaerinstallation im Neubau, Heizkoerpertausch,
Armaturen, erste Badmodernisierung unter Anleitung.

# Ausbildung
Ausbildung Anlagenmechaniker SHK, Roggentin Haustechnik GmbH,
Berlin (2022 - 2026), Gesellenbrief, Sommer 2026.

# Kenntnisse
Sanitaerinstallation, Heizung, Pressfitting, Arbeitsschutz,
Montage im zweikoepfigen Team.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (Schulenglisch).
Fuehrerschein Klasse B (2025).
"""},
            {"name": "anschreiben.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

ich habe im Sommer 2026 meine Ausbildung als Anlagenmechaniker SHK
abgeschlossen und suche eine Stelle, an der ich viel lernen und
richtig viel arbeiten kann.

In der Ausbildung habe ich vor allem Sanitaerinstallation gemacht,
in den letzten Lehrjahren auch Heizkoerpertausch und eine
Badmodernisierung unter Anleitung. Ich bin puenktlich, ich halte
die Baustelle sauber und ich rede gerne mit Kunden - die Uebergabe
bei der ersten eigenen Badmodernisierung war fuer mich das schoenste
Erlebnis der Ausbildung.

Ich moechte in Ihrem zweikoepfigen Team einsteigen, den
Bereitschaftsdienst frueh mitlernen und langfristig den Meister
machen.

Mit freundlichen Gruessen
Felix Gruenwald
"""},
        ],
    },
    {
        "folder": "denis_marek",
        "strength": "low (switching trades)",
        "lang": "en",
        "challenge": "electrician switching trades: generic installation wording may overmatch aliases, zero real plumbing experience",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Denis Marek
Leipzig, Germany - denis.marek@example.org

# Work history
Electrician / installation technician, Elektro Nova GmbH, Leipzig
(2017 - present): installation of building services systems in
residential new-build; laying supply lines and distribution boards;
conduit and cable routing in walls, floors and shafts; reading
installation plans and building drawings; customer-facing service
calls and handover on occupied sites; two-person crew routine.

# Qualification
Vocational training as electronics technician for energy and
building services (apprenticeship, 2014 - 2017), journeyman
certificate.
Safety training (annual, employer).

# Skills
Building services installation, supply line installation,
installation plan reading, power and system tools, customer
service, team work, work safety.

# Languages and other
German (native), English (good).
Driving licence class B (company van routine).
Note: open to retraining into sanitary and heating installation;
plumber friends describe me as a quick learner.
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
# Cover Letter

Dear Mr Brinkmann,

after eight years as an electrician I would like to switch to the
wet side of building services. My installation routine transfers
directly: I read plans, I keep occupied sites clean and safe, I
install supply lines in walls and shafts, and I hand over to the
customer in an orderly state.

I know that sanitary and heating installation has its own rules -
drinking water, drainage, boilers - and I am honest: I have not done
them yet. What I offer is disciplined installation work, real
customer-facing experience from service calls, and the willingness
to retrain properly, including formal qualification.

Kind regards
Denis Marek
"""},
        ],
    },
    {
        "folder": "anton_velasco",
        "strength": "mid (language gap)",
        "lang": "en",
        "challenge": "experienced sanitary installer from Spain, German A2 (trade-strong, must-have language gap); English packet",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Anton Velasco
Madrid, Spain - anton.velasco@example.org

# Work history
Sanitary and heating installer, Instalaciones Velasco e Hijos S.L.,
Madrid (2016 - present): full bathroom renovation from drainage to
washbasin; water supply and drainage installation in occupied flats;
boiler replacement and heating service; leak detection and pipe
repair; direct customer handover, quotations and aftercare; two-person
crew routine.
Apprentice plumber, family firm (2013 - 2016): fixture installation,
press fittings, copper soldering.

# Qualification
Vocational training, plumbing and heating (instalador de fontaneria y
calefaccion), Madrid (2011 - 2013).
Manufacturer training: condensing boilers (2021).

# Skills
Water supply installation, drainage installation, bathroom
renovation, boiler replacement, leak detection, press fittings,
copper soldering, customer service, work safety.

# Languages and other
Spanish (native), German (A2 - beginner, course ongoing),
English (intermediate).
Driving licence class B.
"""},
            {"name": "motivation.pdf", "kind": "cover", "lang": "en", "title": "Motivation Letter", "body": """
# Motivation Letter

Dear Mr Brinkmann,

nine years of bathroom renovations and boiler service in Madrid have
taught me the two things your listing asks for: careful installation
at the pipe, and a polite, orderly handover in front of the customer.

I have moved to Berlin for family reasons and am looking for a
position as plumber / sanitary and heating technician. My German is
at A2 - beginner level, with an ongoing course. On site I can work
from plans and understand instructions; complex customer dialogue I
will manage with time. What I can show you today: full bathroom
renovations from drainage to washbasin, boiler replacements, leak
repair in occupied flats, and a two-person crew routine since my
apprenticeship.

Kind regards
Anton Velasco
"""},
        ],
    },
    {
        "folder": "petra_lindner",
        "strength": "mid-strong (mistags planted)",
        "lang": "de",
        "challenge": "PLANTED MISTAGS: cv.pdf contains the cover letter, dokumente.pdf contains the CV",
        "files": [
            {"name": "cv.pdf", "kind": "cover", "lang": "de", "title": "Anschreiben", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

als Gesellin SHK mit sieben Jahren Erfahrung in der Sanitaerinstallation moechte ich in Ihr Team wechseln. Bei meinem aktuellen
Arbeitgeber installiere ich Trinkwasser- und Abwasserleitungen im
Bestand, tausche Armaturen und Spuelkaesten aus und begleite
Badmodernisierungen von der Entwässerung bis zur Uebergabe.

Was mich auszeichnet: saubere Arbeit am Rohr, kundenorientierte
Uebergabe und ein guter Umgang im zweikoepfigen Team. Den
Bereitschaftsdienst kenne ich aus dem aktuellen Dienstplan und
arbeite ihn gern.

Mit freundlichen Gruessen
Petra Lindner
"""},
            {"name": "dokumente.pdf", "kind": "cv", "lang": "de", "title": "Lebenslauf", "body": """
# Lebenslauf - Petra Lindner
Berlin, Deutschland - petra.lindner@example.org

# Beruflicher Werdegang
Gesellin Sanitaerinstallation, Badeleben Sanitaertechnik GmbH,
Berlin (2019 - heute): Trinkwasser- und Abwasserinstallation im
Wohnungsbestand, Armaturen- und Spuelkastenwechsel,
Badmodernisierung mit Fliesenanschluss, Kundenuebergabe,
Mitarbeit im Bereitschaftsdienst.
Ausbildung Anlagenmechaniker SHK, Badeleben Sanitaertechnik
GmbH, Berlin (2016 - 2019), Gesellenbrief.

# Kenntnisse
Trinkwasserinstallation, Abwasserinstallation, Badmodernisierung,
Pressfitting, Arbeitsschutz, Kundenservice.

# Sprachen und Sonstiges
Deutsch (Muttersprache), Englisch (Grundkenntnisse).
Fuehrerschein Klasse B.
"""},
        ],
    },
    {
        "folder": "bogdan_ionescu",
        "strength": "mid (mixed single document)",
        "lang": "de",
        "challenge": "single mixed application document bewerbung.pdf (cover letter + CV in one file)",
        "files": [
            {"name": "bewerbung.pdf", "kind": "mixed", "lang": "de", "title": "Bewerbung", "body": """
# Anschreiben

Sehr geehrter Herr Brinkmann,

ich arbeite seit zehn Jahren in der Heizungs- und Sanitaerinstallation, davon zwei Jahre in Wien im Bestand und acht Jahre in
einem Installateurbetrieb in Bukarest. Ich kann Trinkwasser- und
Abwasserinstallationen selbststaendig ausfuehren, Brennwertthermen
wechseln und Badmodernisierungen begleiten. Deutsch spreche ich auf
gutem Niveau, zwei Jahre arbeite ich in einem Wiener Betrieb mit
deutscher Arbeitssprache.

# Lebenslauf - Bogdan Ionescu

Beruflicher Werdegang:
Heizungs- und Sanitaermonteur, Termo-Instal SRL, Bukarest
(2014 - heute): Heizungsinstallation, Trinkwasser- und
Abwasserinstallation, Gasthermenwechsel, Leckagesuche,
Kundenuebergabe, Bereitschaftsdienst im Winter.
Monteur, Wien-Sanitaer GmbH, Wien (2021 - 2023): Sanitaerinstallation im Wohnungsbestand, deutsche Arbeitssprache.

Ausbildung: Installateur (Duales System), Bukarest (2011 - 2014).

Kenntnisse: Trinkwasserinstallation, Abwasserinstallation,
Heizungsanlagen, Brennwerttherme, Pressfitting, Arbeitsschutz,
Kundenservice.

Sprachen: Rumoenisch (Muttersprache), Deutsch (gut, B2, taegliche
Arbeitssprache in Wien 2021-2023), Englisch (gut).

Fuehrerschein Klasse B.
"""},
        ],
    },
    {
        "folder": "gordon_miles",
        "strength": "very low (negative control)",
        "lang": "en",
        "challenge": "negative control: sanitary ceramics sales background without hands-on installation evidence; must-fail on installation, tools, qualification, German",
        "files": [
            {"name": "cv.pdf", "kind": "cv", "lang": "en", "title": "Curriculum Vitae", "body": """
# Curriculum Vitae - Gordon Miles
Manchester, UK - gordon.miles@example.org

# Work history
Regional account manager, Ceramica Bath Group, Manchester
(2018 - present): wholesale account management for bathroom
ceramics; showroom product demonstrations; trade fair stands;
quotation and after-sales coordination with installer partners.
Sales representative, home improvement retail (2013 - 2018).

# Education
BA (Hons) Business Administration, University of Leeds (2009 - 2013).

# Skills
Product knowledge of sanitary ceramics, accounts and quotations,
customer communication, presentations.

# Languages and other
English (native), German (none), Spanish (basic).
Driving licence class B.
"""},
            {"name": "cover_letter.pdf", "kind": "cover", "lang": "en", "title": "Cover Letter", "body": """
# Cover Letter

Dear Mr Brinkmann,

I am writing to apply for the plumber / sanitary and heating
technician position in Berlin. After seven years selling sanitary
ceramics to installer partners I know the product side of the
bathroom trade inside out - I can specify a WC suite, a washbasin
and a shower system from memory, and I regularly spend full days at
customer sites demonstrating products.

I would like to move from sales into hands-on installation work.
While I have not yet carried out installations myself, I have
watched hundreds of installations at trade fairs and partner sites,
and I believe my product knowledge and customer communication would
be an asset to your crews.

Kind regards
Gordon Miles
"""},
        ],
    },
]
