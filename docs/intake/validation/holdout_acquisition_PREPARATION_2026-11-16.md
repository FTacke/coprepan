# Holdout acquisition for the independent BODY/CORE validation — preparation (CPD-0044)

**Status: `BLOCKED` — prepared, not authorised.** The operator's brief of 2026-11-16 welcomes new data for the validation "im
Rahmen der bestehenden Autorisierungs- und Acquisition-Regeln". Those rules (CPD-0023 §2–§4) admit a request only under a delegated
authorisation record that **quotes** the operator's commission — its validity, outlets, request limits and holds — and adds nothing
to it. The brief names no validity window, no request ceiling and no per-outlet limit; an agent that set them itself would widen
the commission. Nothing was requested. Everything else is ready.

## What is to be acquired

- **Outlets:** the 81 qualified outlets of the [weekend matrix](../qualification/weekend_qualification_2026-11-15.md) (72
  `QUALIFIED`, 9 `QUALIFIED_WITH_LIMITS`), all registered, all with development pages, in 20 countries (ar 6, bo 2, cl 4, co 6, cr 2,
  cu 3, do 4, ec 5, es 5, gt 5, hn 5, mx 1, ni 3, pa 7, pe 6, pr 3, py 4, sv 2, uy 4, ve 4). No other outlet is reachable today
  (validation plan §2).
- **Items:** new item pages, as the canary driver selects them from the outlets' channels; at most **4 item requests per outlet**
  (so that at least 2 remain after development addresses, non-2xx answers and non-item pages are excluded).
- **Requests:** measured on the weekend waves — 1,100 transport requests for 99 outlets with 601 item requests, about 1.4–1.7 requests
  per minute per wave, waves of 13–15 outlets taking 65–75 minutes ([capacity](../qualification/weekend_capacity_2026-11-15.json)).
  For 81 outlets with 4 items: robots, channels and items about **8–11 transport requests per outlet**, **about 650–900 in all**
  (*estimate*), in **6 waves of 13–14 outlets**, about **6–8 hours** of wall time (*estimate*).
- **Preservation:** local, deferred (`PRESERVATION_PENDING` in the runtime workspace on `C:`, CPD-0036); no NEW_FS or `D:` write; the
  promotion to shared storage waits for its own gates. The holdout's raw bytes are evidence of the gold: until promoted they exist
  once, on `C:` — a risk to state.
- **Separation:** each wave's run id is entered into `config/validation/holdout_runs.json` in the arming commit, before any page is
  read; from then on no development study sees these pages.
- **After the waves:** `gold_review.py prepare-holdout --per-outlet 2 --seed <the commission's seed>` (the draw reads outlet and
  fetch id only), the package outside the repository, the operator's review.

## The commission to issue (to be quoted in the record)

The operator issues, in a brief, a commission of this form (values to confirm or change):

> Für die unabhängige BODY/CORE-Validierung (CPD-0044) beauftrage ich eine begrenzte Holdout-Erhebung:
> - Zeitraum: von `<Datum, Uhrzeit>` bis `<Datum, Uhrzeit>` Europe/Berlin, nur `<Werktage | Wochenende>`.
> - Outlets: die 81 qualifizierten Outlets der Wochenend-Matrix vom 2026-11-15 (QUALIFIED und QUALIFIED_WITH_LIMITS).
> - Grenzen: höchstens 1.000 Transport-Requests insgesamt, höchstens 12 je Outlet, davon höchstens 4 Item-Requests; ein Request
>   zur Zeit; robots, Crawl-delay und jede Sperre gelten; keine Umgehung von Zugangskontrollen.
> - Ablage: nur lokal (`PRESERVATION_PENDING`), keine NEW_FS- oder `D:`-Schreibvorgänge; CO.RA.PAN hat Vorrang (Advisory, Pausen).
> - Wellen: je eigene Läufe unter einem delegierten Datensatz; jeder Lauf wird vor dem Lesen im Holdout-Register eingetragen.
> - Ziehung: 2 Dokumente je Outlet, Seed `<Zahl>`.
> - Nicht beauftragt: produktiver Intake, Freischaltung, Backfill, neue Outlets oder Registrierungen, kostenpflichtige Dienste.

With it the agent writes the record `DOA-<date>-<n>` (CPD-0023), arms each wave in the delegated mode, verifies, disarms and
registers the runs. The validation plan is frozen before the first wave.

## Not part of this acquisition

Component B (outlets outside the development population) needs registration and qualification first — the 12 `proposed`
outlets and three `NOT_QUALIFIED` outlets with working discovery (`bo_lostiempos`, `pe_el_comercio`, `sv_diario_el_mundo`). Held
outlets (bot challenges, blocks) stay held.
