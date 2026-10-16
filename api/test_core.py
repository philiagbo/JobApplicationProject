"""Plain-assert tests for core.py. Run: python api/test_core.py (no pytest)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402


def summ(salary="", description="", **extra):
    job = {"title": "", "description": description, "salary": salary}
    job.update(extra)
    return core.summarize(job)


def test_normalise():
    assert core.normalise("  What is your First Name?* ") == "what is your first name"
    assert core.normalise("first-name") == core.normalise("First  name")


def test_summary_keys():
    s = core.summarize({"title": "", "description": "", "salary": ""})
    assert set(s) == {"salary_text", "salary_annual", "currency", "job_type", "remote",
                      "years_experience", "what_youd_do", "what_they_want"}
    assert s["what_youd_do"] == [] and s["what_they_want"] == [] and s["years_experience"] is None


def test_salary_plain_gbp():
    s = summ("£45,000")
    assert (s["salary_annual"], s["currency"], s["salary_text"]) == (45000, "GBP", "£45,000")


def test_salary_ranges():
    for text in ("£35k - £45k", "£35-45k"):
        s = summ(text)
        assert (s["salary_annual"], s["currency"]) == (40000, "GBP"), text
    s = summ("USD 80,000 - 100,000")
    assert (s["salary_annual"], s["currency"]) == (90000, "USD")
    s = summ("80k-100k USD")
    assert (s["salary_annual"], s["currency"]) == (90000, "USD")


def test_salary_real_remotive_value():
    s = summ("$35,3k- $52k")  # real Remotive value: 43650
    assert (s["salary_annual"], s["currency"]) == (43650, "USD")


def test_salary_periods():
    assert summ("£15 per hour")["salary_annual"] == 30000
    assert summ("£300/day")["salary_annual"] == 69000
    s = summ("€4.000 per month")
    assert (s["salary_annual"], s["currency"]) == (48000, "EUR")


def test_salary_unparseable_keeps_text():
    s = summ("Competitive")
    assert (s["salary_annual"], s["currency"], s["salary_text"]) == (None, None, "Competitive")


def test_salary_from_description():
    s = summ("", "<p>We pay £50,000 - £60,000 a year</p>")
    assert (s["salary_annual"], s["currency"], s["salary_text"]) == (55000, "GBP", "£50,000 - £60,000")


def test_salary_description_skips_out_of_range():
    s = summ("", "We raised $20 million. Salary £50,000.")
    assert (s["salary_annual"], s["currency"], s["salary_text"]) == (50000, "GBP", "£50,000")


def test_bullets_from_headings():
    d = ("<h3>Responsibilities</h3><ul><li>Build dashboards</li><li>Write SQL</li>"
         "<li>Present findings</li><li>Fourth</li></ul>"
         "<h3>Requirements</h3><ul><li>3+ years of experience with SQL</li><li>Python</li></ul>")
    s = summ("", d)
    assert s["what_youd_do"] == ["Build dashboards", "Write SQL", "Present findings"]
    assert s["what_they_want"] == ["3+ years of experience with SQL", "Python"]
    assert s["years_experience"] == 3


def test_bullets_curly_apostrophe_heading():
    d = "<p><strong>What you’ll do:</strong></p><ul><li>Ship things</li></ul>"
    assert summ("", d)["what_youd_do"] == ["Ship things"]


def test_bullets_keyword_fallback():
    s = summ("", "You will build reports. You have experience with Excel.")
    assert s["what_youd_do"] == ["You will build reports."]
    assert s["what_they_want"] == ["You have experience with Excel."]


def test_years_experience():
    assert summ("", "2-4 years' experience in sales")["years_experience"] == 2
    assert summ("", "Company founded 10 years ago")["years_experience"] is None


def test_job_type():
    assert summ("", "This is a full-time role", job_type="Contract")["job_type"] == "Contract"
    s = core.summarize({"title": "Part-time Data Analyst", "description": "", "salary": ""})
    assert s["job_type"] == "Part-time"
    assert summ("", "Fixed term for 6 months")["job_type"] == "Contract"
    assert summ("", "nothing relevant")["job_type"] is None


def test_remote_status():
    assert summ("", "fully on-site", remote="Remote")["remote"] == "Remote"
    s = core.summarize({"title": "Analyst", "location": "London (hybrid)", "description": "", "salary": ""})
    assert s["remote"] == "Hybrid"
    assert summ("", "fully on-site")["remote"] == "On-site"
    assert summ("", "work from home friendly")["remote"] == "Remote"
    assert summ("", "")["remote"] is None


def test_adversarial_description_is_fast():
    nasty = ("£1,1,1," * 14000)[:100000] + ("9 years " * 12500) + ("<a " * 3000)
    assert len(nasty) >= 200000
    t0 = time.time()
    s = core.summarize({"title": "x", "description": nasty, "salary": ""})
    assert time.time() - t0 < 2, "summarize too slow on adversarial input"
    assert s["salary_annual"] is None and s["years_experience"] is None


# --- score -----------------------------------------------------------------

SETTINGS = {"career_fields": ["Data Analyst"], "excluded_words": [], "min_salary": 40000}


def job(title="Analyst", salary="", description="", **extra):
    j = {"title": title, "salary": salary, "description": description, "location": ""}
    j.update(extra)
    j["summary"] = core.summarize(j)
    return j


def sc(j, **overrides):
    s = dict(SETTINGS)
    s.update(overrides)
    return core.score(j, s)


def test_score_salary_above_min():
    n, pros, cons = sc(job(salary="£45,000"))
    assert n == 80
    assert pros == ["Pays £45k, above your £40k minimum"] and cons == []


def test_score_salary_meets_min():
    n, pros, _ = sc(job(salary="£40,000"))
    assert n == 80 and pros == ["Pays £40k, meets your £40k minimum"]
    assert core.k(42500) == "£42.5k"


def test_score_title_match_and_salary_not_listed():
    n, pros, cons = sc(job(title="Senior Data Analyst"))
    assert n == 65
    assert pros == ["Title matches your field 'Data Analyst'"] and cons == ["Salary not listed"]


def test_score_neutral_is_base():
    n, pros, cons = sc(job())
    assert n == 50 and pros == [] and cons == ["Salary not listed"]


def test_score_ordering():
    above = sc(job(salary="£45,000"))[0]
    title_only = sc(job(title="Data Analyst"))[0]
    neutral = sc(job())[0]
    assert above > title_only > neutral
    excl = sc(job(title="Senior Analyst", salary="£45,000"), excluded_words=["senior"])[0]
    assert excl == 55 and excl > neutral


def test_score_below_min_is_scaled():
    n38, _, cons38 = sc(job(salary="£38,000"))
    n15, _, cons15 = sc(job(salary="£15,000"))
    assert n15 < n38 < 50
    assert cons38 == ["Pays £38k, below your £40k minimum"]
    assert cons15 == ["Pays £15k, below your £40k minimum"]


def test_score_other_currency_not_compared():
    n, pros, cons = sc(job(salary="USD 80000"))
    assert n == 50 and pros == []
    assert cons == ["Pays USD 80000, can't compare with your £40k minimum (not in £)"]


def test_score_min_salary_zero_ignores_salary():
    n, pros, cons = sc(job(salary="£45,000"), min_salary=0)
    assert n == 50 and pros == [] and cons == []


def test_score_remote_points():
    n, pros, _ = sc(job(remote="Remote"))
    assert n == 60 and "Fully remote" in pros
    n, pros, _ = sc(job(remote="Hybrid"))
    assert n == 55 and "Hybrid working" in pros
    n, pros, _ = sc(job(remote="On-site"))
    assert n == 50 and pros == []


def test_score_excluded_word_penalty_keeps_job():
    base = sc(job(title="Analyst"))[0]
    res = sc(job(title="Senior Analyst"), excluded_words=["senior"])
    assert isinstance(res, tuple) and res[0] == 25 == base - 25
    assert "Mentions excluded word 'senior'" in res[2]


def test_score_excluded_word_boundaries():
    assert sc(job(description="a seniority ladder"), excluded_words=["senior"])[0] == 50
    n, _, cons = sc(job(description="needs security clearance"), excluded_words=["security clearance"])
    assert n == 25 and "Mentions excluded word 'security clearance'" in cons


def test_score_two_excluded_words_one_penalty():
    n, _, cons = sc(job(title="Senior Lead Analyst"), excluded_words=["senior", "lead"])
    assert n == 25
    assert [c for c in cons if c.startswith("Mentions")] == [
        "Mentions excluded word 'senior'", "Mentions excluded word 'lead'"]


def test_score_clamped():
    assert sc(job(title="Data Analyst", salary="£100,000", remote="Remote"))[0] == 100
    assert sc(job(salary="£10,000", title="Senior Analyst"), excluded_words=["senior"])[0] == 0


def test_score_profile_ignored():
    j = job(title="Data Analyst", salary="£45,000")
    assert core.score(j, SETTINGS, {"skills": ["sql"], "years": 1}) == core.score(j, SETTINGS, None)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
