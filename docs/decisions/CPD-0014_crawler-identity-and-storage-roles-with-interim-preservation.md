# CPD-0014 — The crawler identity and its public page; storage roles shared with CO.RA.PAN; an interim primary preservation root

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the O-2 / storage run of 2026-10-08, which gave the four values of the crawler identity, ordered the public pages on `coprepan.hispanistica.com`, ordered the storage roles and path semantics of CO.RA.PAN 3.0 for this repository, and named the interim preservation root. Recorded by that run; subject to the operator's review |
| Kind | policy · architecture |
| Scope | the identity the crawler presents and the page behind it (O-2); the storage roles, the local namespace and the physical roots of this workstation; the interim primary preservation root and the planned move to the new university file system; the role of `D:` afterwards |
| Builds on / amends / supersedes | builds on CPD-0006 (crawler identity, readiness), CPD-0009 (writer lock, operation semantics), CPD-0013 (canary policy). Amends `docs/storage/INDEX.md` §5 (the `BACKUP` role gets a variable and rules). Supersedes nothing |
| Does not change | any identifier, any stored artefact, the layout under a preservation root, the acquisition policy |
| Run report | [`docs/agent-runs/2026-10-08_crawler-site-storage-o2-o3-interim.md`](../agent-runs/2026-10-08_crawler-site-storage-o2-o3-interim.md) |
| Evidence | `web/DEPLOY_RECEIPT_2026-10-08.json`; `tests/test_policy.py`, `tests/test_storage_architecture.py`, `tests/test_storage_roots.py`; the qualification receipts of the run report |

Validation debt: the interim root has carried a probe object and the test suites' temporary files,
never corpus material. The new university file system does not exist yet and is qualified by
nothing here.

## Context

After CPD-0013 two things stood between the built pipeline and a first real request: no crawler
identity a publisher could look up (O-2) and no preservation target (O-3). The operator supplied
the identity and a public address for its page, and named a local volume as an interim primary
because the new 2 TB university file system is not yet available and a group share could not be
used. CO.RA.PAN 3.0 had meanwhile separated checkout, runtime workspace and outage spool and made
storage roles and named roots a design principle; CO.PRE.PAN should not grow a different storage
semantics.

## Decision

### 1. Crawler identity (O-2)

```text
crawler_name   PanhispanicMediaResearchBot
organisation   Marburg University
contact_url    https://coprepan.hispanistica.com/crawler/
contact_email  felix.tacke@uni-marburg.de
```

- The User-Agent is built by the existing contract, not by a second format:
  `<crawler_name>/<package version> (+<contact_url>; <contact_email>)`, today
  `PanhispanicMediaResearchBot/0.3.0 (+https://coprepan.hispanistica.com/crawler/; felix.tacke@uni-marburg.de)`.
  The operator's preferred short form (`…/1.0 (+URL)`) was not adopted because it would have
  needed a second format, a version unrelated to the package and the loss of the address from every
  request. The robots token is the lower-cased name.
- The public pages are versioned in `web/coprepan/` and served as plain files by the existing
  virtual host. **A contact URL is only configured when the page is reachable**; the deployment is
  verified (`scripts/deploy_public_site.py verify`) and its receipt is versioned.
- The pages state what the policy of the canary does (public HTTP(S) only, no access control
  bypassed, `robots.txt`, `Crawl-delay`, `Retry-After`, conditional requests, no automatic public
  redistribution) and give the contact for exclusion and opt-out. They make no claim about a
  corpus, a size or a result, and offer no raw data.

### 2. Roles and names

CO.PRE.PAN uses the storage roles of CO.RA.PAN 3.0 with the names this repository already had; the
mapping, so that nothing is renamed:

| Brief / CO.RA.PAN | Here | Root |
|---|---|---|
| `REPO` | `REPOSITORY` | the checkout (`coprepan`) |
| `DATA_WORKSPACE`, `RUNTIME` | `RUNTIME` — CO.PRE.PAN never had a data workspace inside its checkout | `COPREPAN_WORKSPACE_ROOT` |
| `SPOOL` | `SPOOL` | `COPREPAN_SPOOL_ROOT` |
| `PRESERVATION` | `PRESERVATION` — the only authoritative role | `COPREPAN_PRESERVATION_ROOT` |
| `BACKUP_SECONDARY` | `BACKUP` — now with a variable | `COPREPAN_BACKUP_ROOT` |
| `DISTRIBUTION`, `EXCHANGE` | the same | `COPREPAN_DISTRIBUTION_ROOT`, `COPREPAN_EXCHANGE_ROOT` |
| `REVIEW` | a logical role, bound to `EXCHANGE`; no root of its own | — |

The layout under a preservation root is the one CO.RA.PAN's contract has and this repository
already implemented (`preservation/<area>/…`, `preservation/manifests/<area>/…`); only the areas
CO.PRE.PAN has are materialised. Nothing was restructured.

### 3. Local namespace and roots

```text
C:\dev\panhispanic_media_corpora\
├─ coprepan\                  REPOSITORY
├─ coprepan_workspace\        RUNTIME   (workspace, caches)
├─ coprepan_storage\          SPOOL     (outage spool)
└─ corapan, corapan_workspace, corapan_storage     (the sibling's; not touched)
```

Machine values live in the gitignored `.env` (`workstation_environment()` reads it, `COPREPAN_*`
names only, the process environment wins). `DISTRIBUTION`, `EXCHANGE` and `BACKUP` are
**NOT_CONFIGURED**, and a role that is not configured is a statement, never a fallback.

### 4. Separation rules, enforced

`validate_role_separation` refuses a configuration in which two roles share a root or one lies
inside another (the checkout takes part), and one in which `BACKUP` is on the same volume as
`PRESERVATION` — a copy on the primary's volume is not a backup, whatever it is named. An unknown
volume is a refusal, not a guess. `tests/test_storage_architecture.py` guards these invariants and
the root switch of §7 without reading CO.RA.PAN.

### 5. The interim primary preservation root

```text
INTERIM_PRIMARY_PRESERVATION
D:\projects\panhispanic_media_corpora\coprepan\preservation_interim      (target id coprepan-preservation-interim-d)
```

- The institutional namespace is `projects\panhispanic_media_corpora\{corapan,coprepan}`; the
  root variable points at the actual corpus root, never at an assumed drive. A mount point that is
  itself the `projects` root does not produce `projects\projects`.
- `K:` is not used: no `coprepan` folder can be created there, and CO.PRE.PAN is not placed under
  CO.RA.PAN's root.
- **While `D:` is the primary, `BACKUP` is NOT_CONFIGURED.** `D:` is not its own backup.
- This qualifies `D:` as temporary primary preservation for the small canary only. It does not
  qualify it as the long-term institutional target, as a backup, or for the capacity question
  (O-4).

### 6. The planned move and the later role of `D:`

```text
CURRENT   D:\projects\panhispanic_media_corpora\coprepan\preservation_interim
TARGET    <NEW_UNIVERSITY_FILESYSTEM>\projects\panhispanic_media_corpora\coprepan
```

Sequence: inventory the current primary → verified copy → SHA-256 verification at the
destination → readiness of the new root → crash and concurrency qualification on its file system →
switch `COPREPAN_PRESERVATION_ROOT` → replay and read-back → the new file system is the primary.
**Only then** a backup is made from the new primary to `D:\projects\panhispanic_media_corpora\coprepan\backup`
and verified independently. `preservation_interim` is never renamed and declared a backup.

### 7. Identity does not depend on the root

A persisted reference is an area plus a relative path under a root that has an identity (the
target marker); the drive letter or the mount is machine configuration. Fetch, document and
version ids are derived from content and URL keys, and no stored record names the root
(`tests/test_storage_architecture.py`). The move of §6 is therefore a verified copy and a switch of
one variable: no new id, no rewritten WARC, no rewritten evidence. The copy keeps the logical root
identity (the target marker moves with the data); a copy that does not verify is not switched to.

### 8. The outage spool

`SPOOL` is a real local role on its own root and the module is tested (also on the real roots). It
is **not wired into the acquisition path**: `seal_and_preserve` promotes directly, and an
unavailable target leaves the sealed pack in the workspace as `PRESERVATION_PENDING` — a safe,
resumable state. Wiring the spool in is a separate change.

## Alternatives considered

| Alternative | Why not |
|---|---|
| the short User-Agent form of the brief | a second format; see §1 |
| register the contact page as planned, then deploy | an unreachable contact URL in every request |
| `K:\…\coprepan` or CO.PRE.PAN under CO.RA.PAN's root | cannot be created; mixes two corpora's storage |
| `D:` as primary and a second folder on `D:` as "backup" | one failure takes both |
| a data workspace role | CO.PRE.PAN has no workspace inside its checkout |
| renaming `BACKUP` to `BACKUP_SECONDARY` | a rename without a need; the mapping is recorded |
| a marker for the runtime and spool roots | the architecture has one only for the preservation role (the one that is authoritative) |
| wiring the spool into acquisition now | outside this run's scope; the pipeline is safe without it |

## Consequences

- O-2 is `PASS`; O-3 is `PASS` for the interim scope; the storage architecture is aligned.
- The canary preflight loses the O-2 and O-3 blockers; what remains is the enabling switch of the
  acquisition policy, tests on the commit and the approved baseline.
- A later qualification of the university file system repeats the readiness, crash and concurrency
  checks there, with the procedure of §6.

## Not decided here

- The new university file system: its location, quota, backup semantics. Nothing claims it exists.
- The distribution and exchange roots; any Hessenbox or LinguRep path.
- The capacity for scheduled crawling (O-4).
- Whether the outage spool is wired into acquisition, and its bounds.
- Retention and the hold of exports named by a release on the new root.
