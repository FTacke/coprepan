# CO.PRE.PAN 3.0 — Phase 3 & Cross-Corpus Analysis Contract Architecture Run

**Modell:** Claude Opus 5.5  
**Effort:** Medium

## Ausführungsregel

Dieser Plan ist **der nächste Run nach dem aktuell laufenden Pre-Canary-/Readiness-Run**.

Er darf erst begonnen werden, wenn der laufende Run vollständig abgeschlossen ist:

- alle vorgesehenen Aufgaben abgearbeitet,
- vollständige Tests grün,
- Run-Report geschrieben,
- sinnvoll commitet,
- zu `origin/main` gepusht,
- Working Tree sauber.

Dann diesen Plan aus dem **neuen `HEAD`** ausführen.  
Nicht auf Annahmen aus dem Stand vor Abschluss des laufenden Runs bauen.

Arbeitsrepository:

```text
C:\dev\panhispanic_media_corpora\coprepan
```

CO.RA.PAN 3.0 und die Legacy-/Studies-Bestände bleiben read-only:

```text
C:\dev\panhispanic_media_corpora\corapan
C:\dev\panhispanic_media_corpora\legacy\coprepan
C:\dev\panhispanic_media_corpora\legacy\corapan_coprepan_studies
```

---

## 1. Ziel

Entwirf und prototypisiere die **wissenschaftliche Phase-3-Architektur** von CO.PRE.PAN 3.0 und den **gemeinsamen CO.RA.PAN ↔ CO.PRE.PAN Analysevertrag** so weit, wie dies ohne offene Human-/Operator-Gates methodisch sauber möglich ist.

Der Run soll drei Ebenen verbinden:

1. **Phase 3 CO.PRE.PAN:** Extraction-, Admission- und spätere NLP-Schnittstellen so festlegen, dass reale wissenschaftliche Validierung danach sauber durchgeführt werden kann.
2. **Cross-Corpus Contract:** eine gemeinsame versionierte Analyseebene für CO.RA.PAN und CO.PRE.PAN entwerfen.
3. **Conformance Prototype:** auf beiden Seiten mit Fixtures/Adapter-Prototypen und Tests nachweisen, dass der Vertrag praktisch implementierbar ist, ohne die modality-spezifischen Rohmodelle gleichzumachen.

Kein wissenschaftlicher `PASS` ohne Human Gold oder reale Validierung.

---

## 2. Autoritativer Ausgangsstand

Vor jeder Entscheidung tatsächlich lesen:

```text
AGENTS.md
CLAUDE.md
docs/STATUS.md
docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md
docs/architecture/
docs/extraction/
docs/nlp/
docs/methodology/
docs/corpus_supply/
docs/decisions/
docs/agent-runs/
```

Insbesondere den **unmittelbar vorhergehenden Run-Report** des laufenden Pre-Canary-/Readiness-Runs.

Der jüngste Repository-Stand ist autoritativ.  
Historische Reports dienen nur als Evidenz und werden nicht rückwirkend geändert.

---

## 3. Grundprinzip

Die beiden Korpora bleiben intern modality-spezifisch.

Nicht:

```text
CO.PRE.PAN intern wie CO.RA.PAN modellieren
```

sondern:

```text
CO.RA.PAN interne Daten ──┐
                          ├──> gemeinsamer versionierter Analysevertrag
CO.PRE.PAN interne Daten ─┘
```

Der gemeinsame Vertrag ist ein **Analysis Layer**, kein gemeinsames Raw-/Pipeline-Datenmodell.

---

## 4. Forschungsziel

Der gemeinsame Vertrag soll später mindestens kontrollierte Vergleiche dieser Bedingungen unterstützen:

| Bedingung | Korpus |
|---|---|
| gesprochen + spontan | CO.RA.PAN |
| gesprochen + geskriptet | CO.RA.PAN |
| geschrieben + redigiert | CO.PRE.PAN |

Dabei müssen Instrumentartefakte möglichst von echten Modalitäts-/Registerunterschieden getrennt werden.

---

## 5. Phase A — CO.RA.PAN Read-only Archaeology

Analysiere den aktuellen **kanonischen CO.RA.PAN-3.0-Stand** read-only.

Nicht nur Dokumentation lesen, sondern tatsächliche relevante Schemas, Exporte, IDs, NLP- und Release-nahe Komponenten prüfen.

Mindestens rekonstruieren:

### Release-/Corpus-Ebene
- `corpus_id`
- ggf. Release-/Freeze-Konzepte
- Manifest-/Hash-Semantik
- Coverage-/Selection-Strukturen
- Provenienz

### Dokument-/Einheitenebene
- Recording-/Document-Identität
- Sprecher-/Produzentenidentität
- Turns / technische Segmente / sprachwissenschaftlich relevante Einheiten
- `speech_mode` bzw. ähnliche Variablen
- Rollen
- Scope-/Eligibility-Zustände

### Satz-/Tokenebene
- Satz-IDs
- Token-IDs
- Indexbasis
- Token-Schema
- Lemma/POS/Morph/Dependencies
- Char-/Time-Anker
- NLP-Versionierung
- derived layers

### Wissenschaftliche Layer
- PROFI
- Commercial / Selection soweit relevant
- verbal-complex / tense-bezogene Layer
- LCP nur soweit für Contract-Design relevant
- Register-/Mode-Semantik

Keine Änderungen im CO.RA.PAN-Repository.

---

## 6. Phase B — Studies Archaeology

Analysiere den eingefrorenen Studies-Bestand read-only als **Anforderungskatalog**, nicht als Blueprint.

Suche systematisch nach Workarounds und impliziten Annahmen, insbesondere:

- selbst konstruierte cluster/document ids,
- doppelte ids,
- aus Slugs abgeleitete Länder/Regionen,
- absolute Pfade,
- Dateiname als Datum,
- Containerdatum statt Publikationsdatum,
- `segment_id` mit unterschiedlicher Semantik,
- unterschiedliche `morph`-Formate,
- defensive Parser,
- asymmetrische Counting Rules,
- fehlende Release-Pins,
- duplicated scope constants,
- Satzkontext durch erneutes Scannen,
- unterschiedliche Token-Denominator,
- Legacy-Taxonomien.

Jeden gefundenen Workaround in eine explizite Contract-Anforderung übersetzen.

Beispiel:

```text
Workaround:
source_file|article_id als Cluster-ID

Contract requirement:
globally unique document_id + explizite duplicate/syndication relation
```

---

## 7. Phase C — O-6 entscheiden, soweit Evidenz reicht

O-6 betrifft Cross-Corpus Naming und Semantik.

Entscheide selbstständig, sofern die Evidenz aus beiden aktuellen Repositories reicht.

Mindestens prüfen und möglichst entscheiden:

### Namespace
Arbeitsname:

```text
crosscorpus-
```

Beibehalten oder besseren kanonischen Namen festlegen.

### Shared Register/Production Dimension

CO.RA.PAN hat ggf.:

```text
speech_mode
```

der Masterplan nennt als möglichen gemeinsamen Namen:

```text
production_mode
```

Entscheide:

- welcher gemeinsame Feldname,
- welche closed vocabulary,
- wie modality-spezifische Werte darauf abgebildet werden,
- wie `UNKNOWN`, `NOT_APPLICABLE`, `UNDECIDED` etc. dargestellt werden.

Nicht versuchen, Modalitätsunterschiede wegzunormalisieren.

### Token denominator

Definiere exakt, was bei Cross-Corpus-Zählungen ein Token ist.

Prüfe den aktuellen CO.RA.PAN-NLP-Contract und die geplante CO.PRE.PAN-Pipeline.

Falls ein exakt gemeinsamer Token-Denominator fachlich nicht möglich ist:

- Unterschied explizit machen,
- vergleichbare Teilmenge definieren,
- keinen falschen gemeinsamen Nenner erfinden.

### Release / Freeze semantics

Entscheide die gemeinsame Semantik von:

- corpus release,
- manifest,
- pinned inputs,
- hash,
- annotator-contract version,
- selection policy,
- coverage snapshot.

CO.PRE.PAN soll CO.RA.PAN nicht eigenmächtig ein neues Production-System aufzwingen.

Wenn dafür tatsächlich eine Änderung in CO.RA.PAN nötig wäre, nur Contract/Proposal dokumentieren; CO.RA.PAN nicht ändern.

---

## 8. Phase D — Cross-Corpus Contract v1

Entwirf einen versionierten Contract, z. B.:

```text
crosscorpus-analysis/v1
```

oder den in Phase C entschiedenen Namen.

Mindestens diese Ebenen:

### Release

```text
corpus_id
release_id
contract_version
manifest_hash
annotator_contract_version
selection_policy
coverage_reference
```

### Outlets / Sources

Mindestens:

```text
outlet_id
country_id
display_name
outlet_kind
city
region
scope
outlet_group
```

Mit expliziten value states statt uninterpretierbarer Nulls.

### Documents

Mindestens:

```text
document_id
corpus_id
release_id
outlet_id/source_id
country_id
region
modality
production_mode
date
date_basis
cohort
section/programme fields
provenance_class
language
token counts
duplicate/syndication relations
```

### Units

Mindestens:

```text
unit_id
document_id
unit_kind
order_index
production_mode
producer_id
producer_role
scope_status
scope_reason
```

`unit_kind` muss technisch/linguistisch eindeutig sein.

Technische Segmentgrenzen nie still als linguistische Äußerungsgrenzen deklarieren.

### Sentences

Mindestens:

```text
sentence_id
unit_id
order_index
previous_sentence_id
next_sentence_id
```

plus notwendige modality-spezifische Anker.

### Tokens

Mindestens:

```text
token_id
sentence_id
unit_id
order_index
form
lemma
upos
xpos if justified
morph typed
dependency fields
```

plus:

CO.PRE.PAN:
```text
char_start
char_end
```

CO.RA.PAN:
```text
start_ms
end_ms
```

oder eine sauber typisierte medium-specific anchor structure.

### Derived layers

Separate versionierte Tabellen/Layers, keine Mutation des Token-Basisvertrags.

---

## 9. Value-state-System

Keine stillen `NULL`-Semantiken.

Entwirf eine kleine konsistente closed vocabulary für Zustände wie:

```text
KNOWN
UNKNOWN
NOT_APPLICABLE
NOT_OBSERVED
NOT_AVAILABLE
UNDECIDED
```

Nur so viele Zustände wie fachlich nötig.

Semantik schriftlich definieren und testen.

---

## 10. Phase E — CO.PRE.PAN Phase-3 Architecture

Auf Basis des inzwischen gebauten Extraction-/Admission-Gerüsts festlegen:

### Extraction Contract

- typed blocks,
- TITLE,
- BODY,
- non-BODY blocks,
- metadata + basis,
- extractor/version,
- provenance,
- raw input identity,
- replay.

### Admission Labels

Technische Admission Labels von wissenschaftlichen Taxonomien strikt trennen.

### Language

Definiere, wie spätere Language-ID als eigener versionierter Layer angeschlossen wird.

Keine wissenschaftliche Validierung vortäuschen.

### Normalisation

Definiere nur Contract und Position im Pipeline-Modell.

Published wording darf niemals still normalisiert werden.

### NLP Input Surface

Explizit festlegen:

```text
BODY = primary linguistic surface
```

Titel und andere Blocks bleiben verfügbar, werden aber nicht still in denselben NLP-Text gemischt.

---

## 11. NLP Alignment Audit

Vergleiche den aktuellen CO.RA.PAN-NLP-Stack mit dem geplanten CO.PRE.PAN-NLP-Stack.

Ziel:

> möglichst gleicher linguistischer Messapparat, wo fachlich sinnvoll; explizite Abweichung, wo Modalität sie verlangt.

Mindestens prüfen:

- tokenizer,
- sentence segmentation,
- lemma,
- POS,
- morphology,
- dependency parser,
- token ids,
- sentence ids,
- version pins,
- verbal-complex layer,
- counting rules.

Nicht automatisch denselben Parser erzwingen, wenn die Modalitäten unterschiedliche Anforderungen haben.

Aber jede Abweichung muss später als mögliche Instrumentenquelle sichtbar sein.

---

## 12. Shared-text equivalence design

Phase 4 verlangt später Annotation-Äquivalenz mit CO.RA.PAN auf einem gemeinsamen Textsample.

Entwirf jetzt das Evaluationsdesign.

Ziel:

Dasselbe geschriebene spanische Textmaterial wird durch beide relevanten Instrumentpfade geschickt, soweit sinnvoll.

Vergleiche mindestens:

- tokenisation,
- sentence boundaries,
- lemma,
- POS,
- morphology,
- dependencies,
- derived verbal-complex output.

Definiere:

- Sample-Construction,
- Gold-/Reference-Rolle,
- equivalence metrics,
- tolerable vs. substantive differences,
- provenance,
- freeze,
- human review bei Grenzfällen.

Noch keine wissenschaftliche Äquivalenz behaupten.

---

## 13. Verbal-complex / tense bridge

Die alten Studies und der Masterplan zeigen Bedarf an konsistenteren Tense-/Verbal-Complex-Regeln.

Entwirf den späteren Bridge-Test:

```text
legacy tense-v3
↔
current verbal-complex layer
```

Nicht alte Regeln blind portieren.

Erst:

- Semantik rekonstruieren,
- Unterschiede explizit benennen,
- Bridge-Sample-Design definieren.

Implementierung nur, wenn ohne wissenschaftliche Vorentscheidung möglich.

---

## 14. Register / Genre / Section

Nur Architektur, keine Validierung.

Trenne mindestens:

```text
publication section
production_mode
register
genre/article_type
opinion
```

Keine dieser Variablen darf still als Proxy für eine andere dienen.

Definiere:

- separate Layer,
- versioning,
- provenance,
- human-gold hooks,
- unknown/value states.

Keine Klassifikationsmodelle aktivieren.

---

## 15. Compatibility Layer

Entwirf eine explizite Alias-/Compatibility-View für Legacy-Studien.

Diese darf z. B. bereitstellen:

- alpha-3 country labels,
- legacy slugs,
- legacy register groups,
- frühere Feldnamen.

Wichtig:

> Compatibility values sind niemals kanonische Werte.

Sie dienen nur Reproduzierbarkeit alter Studien und Migration neuer Studien.

---

## 16. Conformance Prototype

Implementiere im CO.PRE.PAN-Repository einen **Contract-Prototypen** samt Schemas/Validatoren/Fixtures.

Ziel:

- CO.PRE.PAN-Beispieldaten können in `crosscorpus-analysis/v1` exportiert werden;
- ein read-only aus CO.RA.PAN abgeleitetes Fixture kann denselben Contract erfüllen;
- beide laufen durch denselben Validator.

Kein Produktions-Export von CO.RA.PAN verändern.

Das CO.RA.PAN-Fixture darf aus beobachteter aktueller Semantik erzeugt bzw. synthetisch nach ihr modelliert werden, muss aber klar als Fixture gekennzeichnet sein.

---

## 17. Contract Conformance Tests

Mindestens testen:

- globally unique IDs,
- parent-child integrity,
- order indices,
- value-state vocabulary,
- medium-specific anchors,
- token/sentence relationships,
- duplicate/syndication relations,
- release pinning,
- manifest hash format,
- unknown/not-applicable semantics,
- compatibility aliases separated from canonical values.

Fehlerhafte Fixtures müssen fail closed abgelehnt werden.

---

## 18. Cross-Corpus Query Fixtures

Baue wenige kleine, vollständig synthetische Queries/Checks, die zeigen, dass beide Modalitäten über denselben Contract analysierbar sind.

Beispiele:

- Tokenzahl nach `country_id × production_mode`,
- Verbformen nach Modality,
- Dokument-/Unit-Zählung,
- Satzkontext via `previous_sentence_id` / `next_sentence_id`.

Nur Contract-Funktionalität demonstrieren.

Keine wissenschaftlichen Ergebnisse ableiten.

---

## 19. Scientific comparability matrix

Erzeuge eine Matrix der Measure Families:

```text
directly comparable
comparable with declared caveat
modality-specific
not comparable
undecided
```

Mindestens für:

- token frequencies,
- lemma frequencies,
- POS,
- morphology,
- verbal-complex measures,
- sentence-level syntax,
- lexical diversity,
- unit-length measures,
- temporal anchors,
- production/register variables.

Begründung knapp, aber explizit.

---

## 20. Risiken / Hypothesen

Explizit prüfen:

### H1
Ein gemeinsamer Token-Contract ist ohne wesentliche Instrumentartefakte möglich.

### H2
`production_mode` kann als gemeinsame Dimension dienen, ohne `speech_mode` semantisch zu verfälschen.

### H3
Eine gemeinsame sentence/token analysis layer kann modality-spezifische Anchors aufnehmen, ohne separate Parallelverträge zu benötigen.

### H4
Legacy Studies lassen sich über eine Compatibility View reproduzierbar bedienen, ohne Legacy-Semantik kanonisch zu machen.

### H5
CO.PRE.PAN kann auf denselben NLP-Pins wie CO.RA.PAN aufbauen, oder Abweichungen können explizit instrumentiert werden.

Für jede Hypothese:

```text
supported
partially_supported
rejected
undecided
```

mit Evidenzgrenze.

---

## 21. Entscheidungen und CPDs

Dauerhafte Architekturentscheidungen als neue CPD(s) dokumentieren.

Keine trivialen Implementierungsdetails als CPD.

Historische CPDs nicht still überschreiben.

O-6 nur dann als technisch entschieden markieren, wenn:

- Naming,
- Semantik,
- Token denominator,
- Release/freeze semantics

hinreichend geklärt sind.

Falls ein Teil echte gemeinsame Entscheidung mit CO.RA.PAN erfordert:

```text
TECHNICAL_PROPOSAL_READY
HUMAN/JOINT_DECISION_OPEN
```

statt fälschlich `PASS`.

---

## 22. Keine Änderungen in CO.RA.PAN

Strikt:

- read-only,
- keine Commits,
- keine Statusänderung,
- kein Branch,
- kein Exportumbau,
- kein Backfill.

Wenn der Contract dort später Implementierungsarbeit verlangt:

- konkrete Change Proposal dokumentieren,
- Dateien/Komponenten benennen,
- separaten Folgerun empfehlen.

---

## 23. Keine voreilige Studies-Neuentwicklung

`legacy\corapan_coprepan_studies` ist Evidenz.

Noch nicht:

- neue gemeinsame Studies-Library bauen,
- alte Studien portieren,
- fertige Studien umschreiben.

Erst Contract stabilisieren.

---

## 24. Validierungsklassen

Jeden Claim kennzeichnen:

- `reproducibility`
- `replicability`
- `robustness`
- `generalisability`

Erwartung für diesen Run:

- starke `reproducibility` des Contract-Prototyps,
- `robustness` durch invalid fixtures,
- keine wissenschaftliche `generalisability`,
- keine `replicability`, sofern keine unabhängige zweite Implementierung vorliegt.

---

## 25. Tests

Vollständige bestehende Suite plus neue Tests.

Mindestens:

```text
python -m pytest
```

Weitere repo-kanonische Suites/Gates nach aktuellem Stand.

Keine Regression des vorherigen Acquisition-/Preservation-Stacks.

---

## 26. Dokumentation

Erzeuge einen zentralen Run-Report unter:

```text
docs/agent-runs/
```

mit eindeutigem Namen, z. B.:

```text
2026-10-08_phase3-crosscorpus-analysis-contract.md
```

Datum nach tatsächlichem Run-Zeitpunkt wählen.

Aktualisiere bei Bedarf:

```text
docs/STATUS.md
docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md
docs/architecture/
docs/nlp/
docs/extraction/
docs/methodology/
docs/decisions/
```

Historische Reports nicht ändern.

---

## 27. Git

Nach Abschluss des vorherigen Runs auf dessen neuem `HEAD` arbeiten.

Sinnvolle Commits erlaubt.

Vor Push:

- vollständige Tests,
- Working Tree prüfen,
- keine fremden Änderungen vereinnahmen.

Bei sauberem Stand:

```text
git push origin main
```

Kein Force-Push, kein History-Rewrite.

---

## 28. Nicht-Ziele

Nicht in diesem Run:

- reale Outlet-Akquisition,
- Registry-Promotion,
- O-1/O-2/O-3 eigenmächtig schließen,
- Phase-2 Real-Canary,
- Human Gold erzeugen,
- Extractor wissenschaftlich validieren,
- NLP-Qualität behaupten,
- Register-/Genre-/Opinion-Modell aktivieren,
- Studies neu bauen,
- CO.RA.PAN verändern,
- Production Activation.

---

## 29. Abschlussstatus

Ein `PASS` darf bedeuten:

> Phase-3-/Cross-Corpus-Architektur und Contract-Prototyp sind intern konsistent, dokumentiert und reproduzierbar getestet.

Es bedeutet nicht:

- wissenschaftliche Validierung,
- Annotation-Äquivalenz auf realem Gold,
- Contract-Activation in CO.RA.PAN,
- reale Cross-Corpus-Studienfähigkeit auf veröffentlichten Releases.

---

## Operator Report

Am Ende knapp:

1. entscheidendes Ergebnis,
2. `PASS`, `PARTIAL`, `FAIL` oder `BLOCKED`,
3. O-6 Status,
4. Contract-Name und Version,
5. wichtigste gemeinsame Felder/Semantiken,
6. Token-/Sentence-/Anchor-Entscheidung,
7. Phase-3-Architektur,
8. Studies-Workarounds → Contract-Anforderungen,
9. Comparability Matrix,
10. Conformance-Prototyp und Tests,
11. notwendige spätere Änderungen in CO.RA.PAN,
12. verbleibende echte Human-/Scientific-Gates,
13. Commit(s) + Push,
14. nächster sinnvoller Run.

Explizit beantworten:

> Ist der gemeinsame CO.RA.PAN↔CO.PRE.PAN-Analysevertrag jetzt technisch reif genug, um nach dem ersten realen CO.PRE.PAN-Canary und der Phase-3-Gold-Validierung gemeinsam implementiert zu werden?
