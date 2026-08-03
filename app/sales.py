"""Sales collateral generated from a lead's public data — no paid APIs, no LLM.

Everything here is deterministic template text personalised with the business
name, category, and location. It is DRAFT content for manual review: it never
invents owner names, contact details, reviews, or testimonials.
"""


from .config import SELLER_NAME, SELLER_COMPANY, SELLER_PHONE, SELLER_EMAIL


def _personalize(text: str) -> str:
    """Fill in the seller's details, leaving a [ ] placeholder where unset."""
    for token, value in (
        ("[Your Name]", SELLER_NAME),
        ("[Your Company]", SELLER_COMPANY),
        ("[Your Phone]", SELLER_PHONE),
        ("[Your Email]", SELLER_EMAIL),
    ):
        if value:
            text = text.replace(token, value)
    return text


def _singular(category: str) -> str:
    """'Plumbers' -> 'plumber', 'Law firms' -> 'law firm'."""
    c = (category or "business").strip().lower()
    return c[:-1] if c.endswith("s") else c


def service_area(lead: dict) -> str:
    parts = [lead.get("city"), lead.get("state")]
    area = ", ".join(p for p in parts if p)
    return area or "your local area"


# --------------------------------------------------------------------------- #
#  1. Outreach email draft (subject + body)                                    #
# --------------------------------------------------------------------------- #
def generate_email(lead: dict) -> dict:
    name = lead.get("name", "there")
    category = lead.get("category") or "business"
    noun = _singular(category)
    area = service_area(lead)
    has_site = bool(lead.get("has_website"))

    if not has_site:
        subject = f"A free website demo for {name}"
        opener = (
            f"My name is [Your Name] with [Your Company]. I help local businesses "
            f"in {area} get found and win more customers online, and I'm reaching "
            f"out because I noticed {name} doesn't seem to have a website yet.\n\n"
            "I want to be upfront: that's actually a real opportunity. When someone "
            f"in {area} searches Google for a {noun}, the businesses that turn up "
            "with a clean website and a Google listing tend to get the call — even "
            "when a well-run place like yours has a great local reputation. Right "
            "now, some of those searches may be going to competitors simply because "
            "they're easier to find online."
        )
        value_intro = f"A simple, professional website would let {name}:"
        value_points = (
            "  - Show up on Google and Google Maps when locals search for a "
            f"{noun}\n"
            "  - Look established and trustworthy to first-time customers\n"
            "  - Let people call, message, or find you 24/7 from their phone\n"
            "  - Show off your work, services, and location all in one place\n"
        )
        offer = (
            f"Here's the part I think you'll like: I've already put together a free "
            f"demo website for {name} so you can see exactly what it could look "
            "like — at no cost and with no obligation. If you like it, we can talk "
            "about making it live (hosting can even be free). If it's not for you, "
            "no hard feelings at all."
        )
    else:
        subject = f"A few quick ways to help {name} get more customers online"
        issues = []
        if not lead.get("https"):
            issues.append("it isn't fully secure (no HTTPS)")
        if not lead.get("mobile_friendly"):
            issues.append("it's hard to use on phones")
        if not lead.get("meta_title") or not lead.get("meta_description"):
            issues.append("it's missing some basic Google/SEO setup")
        issue_str = ("; ".join(issues) if issues
                     else "it looks a little dated compared with newer sites")
        opener = (
            f"My name is [Your Name] with [Your Company]. I came across {name} "
            f"while looking for a {noun} in {area}, and I took a quick look at your "
            f"website. It's a good start, but a few things are likely costing you "
            f"customers — for example, {issue_str}.\n\n"
            "Most people check a business online before they call or visit, so "
            "small issues like these can quietly send potential customers to a "
            "competitor's site instead."
        )
        value_intro = f"A modern refresh would help {name}:"
        value_points = (
            "  - Rank higher when locals search on Google\n"
            "  - Keep visitors on mobile instead of losing them\n"
            "  - Look secure, current, and professional\n"
            "  - Turn more visitors into calls and enquiries\n"
        )
        offer = (
            f"To make this easy, I've built a free demo of a refreshed site for "
            f"{name} so you can see the difference side by side — no cost and no "
            "obligation. If you like the direction, we can take it from there."
        )

    body = (
        f"Hi {name},\n\n"
        f"{opener}\n\n"
        f"{value_intro}\n"
        f"{value_points}\n"
        f"{offer}\n\n"
        "Would you be open to a quick 10-minute call this week? I'd be happy to "
        "walk you through the demo and answer any questions — no pressure either "
        "way. Just reply with a time that suits you, or call/text me at "
        "[Your Phone].\n\n"
        "Thanks very much for your time,\n"
        "[Your Name]\n"
        "[Your Company]\n"
        "[Your Phone]  |  [Your Email]\n\n"
        "P.S. If you'd rather take a look first, just reply and I'll send the demo "
        "link over right away.\n\n"
        "---\n"
        "DRAFT — review and replace any remaining [ ] placeholders before sending. "
        "Do not send automatically."
    )
    return {"subject": subject, "body": _personalize(body)}


# --------------------------------------------------------------------------- #
#  1b. Phone call script (for when you reach the owner / manager)             #
# --------------------------------------------------------------------------- #
def call_script(lead: dict) -> list[dict]:
    """A friendly, low-pressure phone script personalised to the lead.
    Returns a list of {title, lines} sections."""
    name = lead.get("name", "the business")
    category = lead.get("category") or "business"
    noun = _singular(category)
    area = service_area(lead)
    has_site = bool(lead.get("has_website"))

    if not has_site:
        situation = (f"I help local businesses get set up online, and I noticed "
                     f"{name} doesn't have a website yet.")
        pitch = (f"When people in {area} search Google for a {noun}, a website is "
                 "usually what decides who gets the call. I'd love to help you not "
                 "miss those customers.")
    else:
        situation = (f"I help local businesses improve how they show up online, and "
                     f"I took a look at your current website for {name}.")
        pitch = ("There are a few quick wins that could help you rank better on "
                 "Google and turn more visitors into customers.")

    sections = [
        {"title": "Before you dial", "lines": [
            "Have the free demo website open in a browser tab, ready to share.",
            "Smile — it comes through in your voice. Keep it relaxed and short (aim for 5 minutes).",
            "Goal of this call: not to 'sell', just to book a time to show the demo.",
        ]},
        {"title": "If someone else answers (gatekeeper)", "lines": [
            f"\"Hi, could I speak with the owner or manager of {name}, please?\"",
            "If asked why: \"I put together something free for the business I'd love to show them — is that them, or is there a better time to catch them?\"",
        ]},
        {"title": "Opening (when you reach the decision-maker)", "lines": [
            f"\"Hi, is this the owner/manager of {name}? Great — my name's [Your Name] from [Your Company].\"",
            "\"Do you have a quick minute? I'll be brief.\"",
            f"\"{situation}\"",
        ]},
        {"title": "Build rapport / get permission", "lines": [
            f"\"First off — how are you getting most of your customers right now? Word of mouth, walk-ins, Facebook?\"",
            "Listen. Whatever they say, acknowledge it genuinely before moving on.",
        ]},
        {"title": "The pitch (keep it short)", "lines": [
            f"\"{pitch}\"",
            f"\"So I actually went ahead and built a free demo website for {name} — no charge, no obligation — just so you could see what it would look like.\"",
        ]},
        {"title": "Book the next step (the real goal)", "lines": [
            "\"Could I send you the link, or spend 10 minutes showing you? What's better — email or text?\"",
            "If keen: get their email/number and confirm a follow-up time.",
            "\"Great, I'll send it over to [their email]. Talk soon!\"",
        ]},
        {"title": "Common objections & how to respond", "lines": [
            "\"I'm too busy\" -> \"Totally understand — that's exactly why I did the work up front. Can I just text you the demo link to look at whenever?\"",
            "\"I already have Facebook\" -> \"That's great for regulars. A website helps the people Googling you who aren't on Facebook — and you own it, not the platform.\"",
            "\"How much does it cost?\" -> \"It depends what you need, and I've got a few options — but honestly, take a look at the free demo first and then we can talk numbers.\"",
            "\"I'm not interested\" -> \"No problem at all — mind if I send the demo link anyway in case it's useful down the road? No follow-up unless you want one.\"",
        ]},
        {"title": "If you get voicemail", "lines": [
            f"\"Hi, this is [Your Name] from [Your Company]. I put together a free website demo for {name} and wanted to show you — no cost or obligation. Give me a call or text back at [Your Phone] and I'll send it over. Thanks!\"",
        ]},
        {"title": "Reminder", "lines": [
            "Be honest and low-pressure. Never promise specific results (rankings, sales) you can't guarantee.",
            "Replace any remaining [ ] placeholder with your real details before calling.",
        ]},
    ]
    for section in sections:
        section["lines"] = [_personalize(line) for line in section["lines"]]
    return sections


def script_to_text(sections: list[dict]) -> str:
    out = []
    for s in sections:
        out.append(s["title"].upper())
        for line in s["lines"]:
            out.append("  - " + line)
        out.append("")
    return "\n".join(out).strip()


# --------------------------------------------------------------------------- #
#  2. Website opportunity report                                               #
# --------------------------------------------------------------------------- #
def opportunity_report(lead: dict) -> dict:
    category = lead.get("category") or "business"
    noun = _singular(category)
    area = service_area(lead)

    if not lead.get("has_website"):
        reasons = [
            "No website detected — customers can't find or verify the business online.",
            f"Missing online presence — most people search Google before choosing a {noun}.",
            "Not appearing professionally online compared with competitors.",
            "Limited lead generation — no 24/7 way for new customers to get in touch.",
        ]
        benefits = [
            f"Show up when locals in {area} search on Google and Google Maps.",
            "Look established and trustworthy to first-time customers.",
            "Capture leads any time with click-to-call and a contact form.",
            "Mobile-friendly pages that work on every phone.",
        ]
        suggestions = [
            "Launch a simple 4-5 page, mobile-friendly website.",
            "Add click-to-call, address, and opening hours prominently.",
            "Create or claim a Google Business Profile.",
            "Add basic local SEO (page title, description, service-area keywords).",
        ]
    else:
        reasons = []
        if not lead.get("https"):
            reasons.append("No HTTPS/SSL — browsers may warn visitors the site is 'Not secure'.")
        if not lead.get("mobile_friendly"):
            reasons.append("Not mobile-friendly — hard to use on phones, where most local searches happen.")
        if not lead.get("meta_title") or not lead.get("meta_description"):
            reasons.append("Missing SEO basics (page title/description) — weaker Google ranking.")
        if lead.get("load_ms") and lead["load_ms"] > 3000:
            reasons.append("Slow loading — visitors often leave before the page appears.")
        if not reasons:
            reasons.append("The website works but looks dated and could convert more visitors with a refresh.")
        benefits = [
            "Rank higher in local Google searches with proper SEO.",
            "Keep mobile visitors instead of losing them to competitors.",
            "Build trust with a secure, modern, professional design.",
            "Turn more visitors into calls and enquiries.",
        ]
        suggestions = [
            "Rebuild on a fast, mobile-first, secure (HTTPS) template.",
            "Add clear page titles and descriptions for every page.",
            "Add click-to-call and an easy contact form.",
            "Improve local SEO for the service area and main services.",
        ]

    return {"reasons": reasons, "benefits": benefits, "suggestions": suggestions}


# --------------------------------------------------------------------------- #
#  3. Website package estimator (editable in the UI)                           #
# --------------------------------------------------------------------------- #
DEFAULT_PACKAGES = [
    {"name": "Starter", "price": 499, "features": [
        "5-page website", "Mobile responsive", "Contact form", "Basic SEO"]},
    {"name": "Professional", "price": 999, "features": [
        "Everything in Starter", "Advanced SEO", "Blog setup", "Analytics"]},
    {"name": "Premium", "price": 1799, "features": [
        "Everything in Professional", "Lead capture system",
        "Booking forms", "Additional pages"]},
]
