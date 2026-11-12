# Expert rubric - Plumber / Sanitary & Heating Technician (SHK), Klarwasser SHK Technik GmbH

Committed by the analyst BEFORE any Job-Attune engine run on this profile
(see committed_at in expert_ranking.json). The rubric is a holistic HR view
of the same 24 documents the tool will read; it deliberately includes the
kinds of judgment a keyword-based screener cannot make (depth vs presence of
installation experience, transferability of adjacent trades, trade-off
between formal qualification and proven practice, language as enabler).

## Criteria (100 points)

| # | Criterion | Max | What earns points |
|---|---|---|---|
| A | Sanitary & heating installation experience | 30 | Years x domain proximity: full-spectrum drinking-water/drainage/heating installs = full credit; bathroom or heating focus = high; facility minor repairs or self-renovation = partial; none = 0 |
| B | Formal vocational qualification | 15 | Meister (DE) 15; SHK Gesellenbrief 13; foreign trade qualification 11-12; facility-services qualification 8; adjacent-trade apprenticeship 4; none 0 |
| C | Heating & boiler depth | 12 | Condensing-boiler/heat-pump swap + service routine = 10-12; radiators/partial heating = 6-8; none 0 |
| D | Customer-facing service evidence | 15 | Handover routine + complaint handling + on-call = 12-15; supervised or coordination-only = 5-8; presentations only = 0-4 |
| E | Mobility & physical | 8 | Class B licence + van/site routine = 7-8; licence only = 6; none 0 |
| F | German for Berlin customer-facing work | 12 | Native/C2 12; B2 10; B1 7; A2 3; none 0 |
| G | Application quality | 8 | Clarity, specificity, professionalism; messy or single-mixed packets lose points |

## Judgement calls documented up front

- **Trade depth beats formal depth at the same language level**: Stefan's
  Meister + foreman routine edges Aylin's excellent journeywoman profile;
  Marek's 12 years incl. own crew outrank formal German recognition questions
  (his B1 is working proficiency from cross-border crews).
- **Language as enabler, not checkbox**: German is scored as a range. A2
  applicants keep most trade points (their letters show realistic
  self-assessment and a learning plan) but lose the customer-dialogue points
  a customer-facing Berlin crew lives on (Abdul, Anton) - interview only with
  a language plan.
- **Proven practice vs missing certificate**: Julia's six years of hands-on
  repairs plus outstanding tenant-facing evidence (D=15) carry her past the
  missing SHK apprenticeship to #6; Thomas's self-taught renovations keep him
  mid-table (#9) because his evidence is narrower and unverified.
- **Transferability is discounted, not zeroed**: Denis's electrician
  discipline earns real points for safety, service routine and licence - but
  near-zero for installation itself, because laying conduit is not installing
  drinking-water lines.
- **Petra vs Bogdan (near-tie)**: her German qualification + native German
  edge his longer years + Vienna workplace German; both land 68 vs 65.
- **Negative control**: Gordon scores product knowledge and licence only;
  every hands-on criterion is 0.
- The corpus was authored by the analyst, so perfect blindness is
  impossible; mitigation is that this rubric and every sub-score below were
  written down and frozen (sha256) before the tool ran, and the corpus is
  not modified after seeing tool output.
