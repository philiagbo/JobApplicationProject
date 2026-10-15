# API Coverage — Remotive public jobs API

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Surface checked 2026-10-15 against https://github.com/remotive-com/remote-jobs-api and a live response.

| capability | decision | reason |
|---|---|---|
| list-jobs (GET /api/remote-jobs) | INTEGRATE | |
| search param | INTEGRATE | |
| job fields: url, title, company, location, salary, description, job_type | INTEGRATE | |
| attribution (link back to Remotive URL, name Remotive as source) | INTEGRATE | |
| rate limit (max 2 requests per minute) | INTEGRATE | |
| category param | OPT-OUT | not needed — career fields are free text and search covers them |
| company_name param | OPT-OUT | not needed — the app searches by career field, not company |
| limit param | OPT-OUT | not needed — full result set per search is tens of jobs |
| categories endpoint (GET /api/remote-jobs/categories) | OPT-OUT | not needed — no category picker; career fields are free text |
| job fields tags, category, company_logo, publication_date, id | OPT-OUT | not needed yet — tags could feed CV-skill matching in Phase 3 |
