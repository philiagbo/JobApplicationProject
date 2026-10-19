# API Coverage — Reed, Adzuna

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Surface checked 2026-10-19 against https://www.reed.co.uk/developers/jobseeker and https://developer.adzuna.com/docs/search.

| capability | decision | reason |
|---|---|---|
| Reed job search (GET /api/1.0/search) | INTEGRATE | |
| Reed params: keywords, locationName, minimumSalary, resultsToTake=50 | INTEGRATE | |
| Reed HTTP Basic auth (key as username, empty password) | INTEGRATE | |
| Reed fields: jobUrl, jobTitle, employerName, locationName, minimumSalary, maximumSalary, jobDescription | INTEGRATE | |
| Adzuna job search (GET /v1/api/jobs/gb/search/1) | INTEGRATE | |
| Adzuna params: app_id, app_key, what, where, salary_min, results_per_page=50, sort_by=date | INTEGRATE | |
| Adzuna fields: redirect_url (canonicalised), title, company.display_name, location.display_name, description, salary_min, salary_max, salary_is_predicted, contract_type, contract_time | INTEGRATE | |
| Reed job details (GET /api/1.0/jobs/{id}) | OPT-OUT | one extra call per job; Phase 4 fetch_details reads the full listing page |
| Reed resultsToSkip paging and Adzuna pages beyond 1 | OPT-OUT | first page only per field each poll (D-06) |
| Reed filters: distanceFromLocation, employerId, employerProfileId, permanent, contract, temp, partTime, fullTime, maximumSalary, postedByRecruitmentAgency, postedByDirectEmployer, graduate | OPT-OUT | the app ranks jobs by score instead of hiding them |
| Reed fields: jobId, currency, date, expirationDate, applications | OPT-OUT | not used by scoring or the job dict |
| Adzuna countries other than gb | OPT-OUT | country fixed to gb (D-07) |
| Adzuna filters: what_and, what_or, what_exclude, what_phrase, title_only, distance, max_days_old, category, full_time, part_time, contract, permanent, salary_max, company | OPT-OUT | excluded words and scoring handle this in the app |
| Adzuna categories endpoint | OPT-OUT | career fields are free text |
| Adzuna histogram, history, top_companies and geodata endpoints | OPT-OUT | salary and market statistics are not part of the job feed |
| Adzuna version and jobsworth endpoints | OPT-OUT | not needed |
| Adzuna fields: id, created, latitude, longitude, category, adref | OPT-OUT | not used by scoring or the job dict |
