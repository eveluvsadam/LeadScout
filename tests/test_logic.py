from app.analyze import classify_opportunity
from app import sales, website

GOOD = {"reachable": True, "website_score": 90, "seo_score": 85, "mobile_friendly": True, "https": True}


def test_no_website_is_high_opportunity():
    assert classify_opportunity(False, {**GOOD, "reachable": False}) == "High"


def test_opportunity_levels():
    assert classify_opportunity(True, GOOD) == "Low"
    assert classify_opportunity(True, {**GOOD, "website_score": 70}) == "Medium"
    assert classify_opportunity(True, {**GOOD, "https": False}) == "High"
    assert classify_opportunity(True, {**GOOD, "mobile_friendly": False}) == "High"


def test_slug_is_filename_safe():
    s = website.slug("Joe's Café & Bar / Downtown")
    assert s and all(c.isalnum() or c in "-_" for c in s)


def test_demo_site_escapes_business_data():
    site = website.generate_site({"name": "<script>alert(1)</script>", "category": "Bakeries"})
    assert "<script>alert(1)</script>" not in site["html"]


def test_email_draft_has_subject_and_body():
    e = sales.generate_email({"name": "Test Bakery", "category": "Bakeries", "city": "Montpelier"})
    assert e["subject"] and "Test Bakery" in e["body"]
