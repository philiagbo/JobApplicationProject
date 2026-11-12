# API Coverage — Reed Jobseeker API (www.reed.co.uk/api/1.0)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Surface: the two Jobseeker API endpoints, `GET /api/1.0/search` (with its query parameters) and `GET /api/1.0/jobs/{jobId}`, per reed.co.uk/developers/jobseeker. Phase 2 built `fetch_reed` on the search endpoint; Phase 04.1 adds the description lookup (search + job details). LinkedIn and Indeed are not APIs the app calls (Phase 4 D-18).

| capability | decision | reason |
|---|---|---|
| search | INTEGRATE | |
| search.keywords | INTEGRATE | |
| search.locationName | INTEGRATE | |
| search.minimumSalary | INTEGRATE | |
| search.resultsToTake | INTEGRATE | |
| job_details | INTEGRATE | |
| search.distanceFromLocation | OPT-OUT | not needed — Reed's default radius is used for the feed, and the lookup never filters on location (D-04: location only breaks ties) |
| search.maximumSalary | OPT-OUT | not needed — the app ranks on a minimum salary only (settings have no maximum) |
| search.employerId | OPT-OUT | not needed — alert jobs carry an employer name, not a Reed employer ID; the company match is done locally with core.company_key (D-04) |
| search.employerProfileId | OPT-OUT | not needed — same reason as employerId |
| search.permanent / contract / temp / partTime / fullTime | OPT-OUT | not needed — job type is a ranking signal read from the result, never a search filter |
| search.postedByRecruitmentAgency / postedByDirectEmployer | OPT-OUT | not needed — no setting asks to filter by poster |
| search.graduate | OPT-OUT | not needed — no setting asks for graduate-only jobs |
| search.resultsToSkip | OPT-OUT | not needed — first page only for the feed (Phase 2 PAGE_SIZE ponytail) and one try per lookup (D-03) |
| recruiter_api (posting and managing ads) | OPT-OUT | explicitly out of scope — a separate Reed product for employers; the app only reads jobs |
