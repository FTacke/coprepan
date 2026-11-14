# The first bounded intake under `intake-controller/2` — preparation (`in2-20261114-canary`)

**State: PREPARED, NOT AUTHORIZED.** Nothing here has made a request. The plan is built and validated offline; the authorization is
the operator's ([draft](in2-20261114-canary_AUTHORIZATION_DRAFT.json), deliberately invalid). Prepared 2026-11-14 by the run
[`2026-11-14_coprepan-backup-calendar-acquisition-readiness-closure`](../../agent-runs/2026-11-14_coprepan-backup-calendar-acquisition-readiness-closure.md)
(decision [CPD-0035](../../decisions/CPD-0035_weekday-maintenance-calendar-transfer-priority-and-bounded-catch-up.md)).

## 1. What it is for

The real chain under the new controller, once and small: discovery → fetch → pack → **preservation on the share** (the first
production write there since 2026-10-18) → verification → finalization, with CO.RA.PAN's priority and the bounded catch-up in force.
It is not a coverage test and authorises no recurring acquisition.

## 2. The plan

`config/intake/plans/in2-20261114-canary.json` — `plan_sha256` `b39ae894057395f20905d3af9c21f75aa6a8e2e04f7d9c250c63d81e1639dc3f`,
`intake-controller/2`, `canary/2026-10-10.1`, built with `scripts/intake_operator.py plan` from
`config/intake/intake_readiness_2026-10-10.1.json` (sha `fd1512a0…a787e`), registry sha `7470d583…b9bb8`.

| Outlet | Country | Mechanism (channels) | Why |
|---|---|---|---|
| `cl_cooperativa` | cl | RSS | the plain feed case |
| `co_el_espectador` | co | RSS + news sitemap | two channels of different kinds for one outlet |
| `uy_ladiaria` | uy | RSS + sitemap index | an index channel (polled every 6 h) |
| `ec_primicias` | ec | news sitemap only | a sitemap without a feed |
| `pr_noticel` | pr | section page (listing with a reviewed rule) | the candidate rule path |
| `ve_correo_del_caroni` | ve | RSS, robots Crawl-delay 20 s observed | pacing above the 10 s floor |
| `es_el_mundo` | es | RSS | a large outlet of another region |

Left out on purpose: every outlet with a held origin or URL (the 17 of the readiness file and `ve_efecto_cocuyo`, whose only channel has
been held since the 24-hour intake); `pe_elperuano` (robots unreachable at every poll in October); `hn_radio_progreso` (no new page in
24 polls); outlets whose open extraction would dominate the reading. Offline validation on 2026-11-14: `validate_plan` **PASS**
against the registry, the acquisition policy and the 20 holds derived from every stored answer of the workspace (none on the plan).

**Limits** (the plan's budget; the draft's ceilings equal them): 3 h (10,800 s), cycles of 1 h, at most 300 requests in all, 15 item
requests per outlet, 6 per outlet and hour, 20 per origin, 5 items per outlet and cycle (1 from the backlog), the discovery limits of
CPD-0029 (4 documents, 4 MiB, depth 2, 200 candidates), one request at a time, at least 10 s per origin. Data volume: at the October
rate (about 176 KiB per pack, one pack per outlet and cycle) about 21 packs and well under 10 MB; the pending bounds of
`config/resource_policy.json` (5,000 packs / 5 GiB / 72 h) are far away.

## 3. Preconditions (each one checked by the operator or by `start`)

1. A weekday; CO.RA.PAN's observation `SHARE_NORMAL` (`python scripts/storage_contract.py status` → `operations.corapan_advisory`)
   and `new_transfers: PERMITTED`.
2. The first scheduled incremental backup (Monday 2026-11-16 08:00) has ended `BACKUP_VERIFIED`
   (`python scripts/preservation_backup.py status`).
3. The manifest cache is seeded from the verified backup: `python scripts/preservation_backup.py seed-cache` (local reads on `D:`, no
   share contact; on a weekday). Without it the controller warms the cache from the share at most 1,200 reads an hour, and the first
   packs stay pending meanwhile — correct, but slower.
4. The authorization record (from the draft), committed once; the plan committed once; the tree clean and `HEAD == origin/main`.
5. Everything else is `start`'s own gate: the switch, the authorization, the plan against the evidence holds, recovery `CLEAN`, the
   spool empty, the full test suite, the frozen baseline (`docs/intake/BASELINE_FROZEN_<date>_in2-20261114-canary.json`, written and
   pushed by `start`), the preflight.

## 4. Running it

```
python scripts/intake_operator.py start --authorization config/intake/authorizations/<date>_in2-canary.json
python scripts/intake_operator.py status --intake in2-20261114-canary
python scripts/storage_contract.py status        # operations: acquisition, pending, gate, CO.RA.PAN, backup
```

The scheduled task of the intake ticks every 5 minutes; after the deadline it drains a remaining backlog (at most 200 packs an hour),
finalizes, disarms and removes itself.

## 5. Abort criteria (stop: `python scripts/intake_operator.py stop --intake in2-20261114-canary`)

- a hold arises on an origin of the plan, or any 403/429 answer;
- more than a third of the outlets fail in one cycle (the controller stops itself);
- `held_because` names a free-space floor, or the pending bounds;
- CO.RA.PAN's observation becomes `SHARE_DEGRADED` for longer than the remaining time (transfers wait by themselves; the intake
  may run to its deadline and be finalized later — stopping is the operator's choice);
- any `preservation_readback_and_fixity` or `raw_preserved_matches_verified_bytes` failure in the receipt;
- the operator's judgement.

## 6. Stop, resume, rollback

- **Stop:** the STOP file (above). The controller ends after the request it is making; the next tick drains, finalizes and disarms.
- **Pause shared I/O only:** create `<RUNTIME>/state/PAUSE_IO` — no request and no transfer at the next decision point; delete it to go
  on. Nothing is killed.
- **Resume after a crash or a reboot:** nothing to do; the next tick resumes from the state file (budgets are recounted from the fetch
  records, the catch-up budget is in the state file).
- **Rollback:** there is none to run and none is needed. Preserved objects are write-once and stay; a failed intake leaves its packs
  honestly `PRESERVATION_PENDING` in the workspace and the spool, and they are preserved later. The switch is disabled at the end
  whatever the outcome. Nothing is deleted on any path.

## 7. The next wave (prepared, not to be started without a separate authorization)

A bounded intake over at least one full day cycle (24–30 h), all qualified outlets without holds (the October 24-hour plan's scope,
rebuilt from a current readiness file), under `intake-controller/2`, to measure what one cycle cannot: scheduler behaviour over a
day, the pending backlog and its catch-up, coverage per country, and the share and `D:` load next to CO.RA.PAN's day and night.

**Criteria under which a recurring acquisition could be proposed** (each one an observed fact, none a default):

1. Source stability: the outlets of the wave answered in every cycle without new holds beyond named exceptions; a rebuilt readiness
   file records them (`OPERATIONALLY_STABLE` needs three verified runs on three days, CPD-0025).
2. Real preservation: every answer of the wave `RAW_PRESERVED` with its bytes read back from the share (the receipt's checks).
3. No uncovered backlog: the pending backlog returned to zero within the wave or its drain, inside the 72 h bound.
4. Backup and recovery: the weekday backups of the wave's days `BACKUP_VERIFIED` and incremental; the new objects in the next
   receipt; a restore sample of them.
5. CO.RA.PAN unharmed: no CO.RA.PAN health problem or escalation that names CO.PRE.PAN during the wave (its own status and logs, read
   only); CO.PRE.PAN's transfers held while CO.RA.PAN was slow or recovering, as its state file shows.
6. Status and errors: `storage_contract.py status` and the intake's state explain every hold and every error without reading logs.
7. A valid acquisition authorization and the open gate O-1 (a production schedule policy) decided by the operator.
