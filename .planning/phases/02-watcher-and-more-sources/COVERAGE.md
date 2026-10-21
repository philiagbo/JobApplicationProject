# API Coverage — Reed (Adzuna removed)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Surface checked 2026-10-19 against https://www.reed.co.uk/developers/jobseeker. Adzuna was integrated in plan 02-02 and removed on 2026-10-21 by quick task 261021-wez; its code and tests are in git history.

| capability | decision | reason |
|---|---|---|
| Reed job search (GET /api/1.0/search) | INTEGRATE | |
| Reed params: keywords, locationName, minimumSalary, resultsToTake=50 | INTEGRATE | |
| Reed HTTP Basic auth (key as username, empty password) | INTEGRATE | |
| Reed fields used by the job dict | INTEGRATE | jobUrl, jobTitle, employerName, locationName, minimumSalary, maximumSalary, jobDescription |
| Reed job details (GET /api/1.0/jobs/{id}) | OPT-OUT | one extra call per job; Phase 4 fetch_details reads the full listing page |
| Reed resultsToSkip paging | OPT-OUT | first page only per field each poll (D-06) |
| Reed filters other than keywords, location and minimum salary | OPT-OUT | the app ranks jobs by score instead of hiding them (distanceFromLocation, employerId, employerProfileId, permanent, contract, temp, partTime, fullTime, maximumSalary, postedBy*, graduate) |
| Reed fields: jobId, currency, date, expirationDate, applications | OPT-OUT | not used by scoring or the job dict |
| Adzuna (all endpoints, params and fields) | OPT-OUT | removed 2026-10-21 by quick task 261021-wez: not used yet; the adapter and its tests stay in git history |
