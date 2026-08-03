"""Generate a complete, self-contained demo website for a business.

Plain HTML + CSS + a little JS — no frameworks. Content is auto-filled from the
lead's public data (name, category, address, phone, location). Missing fields
become clearly-marked placeholders. Nothing is fabricated: no owner names, no
reviews, no testimonials — testimonials only appear if the user types in real
ones.

Two outputs are produced:
  - "inline"      : one self-contained HTML file (used for live preview; the
                    contact form is a harmless demo that doesn't submit)
  - "html/css/js" : separate files (used for the ZIP export; the contact form
                    is wired to the free FormSubmit service so it works live)
"""
import html
import re

from .osm import CATEGORY_TAGS, SYNONYMS
from .sales import _singular, service_area


def _canon(category: str) -> str:
    """Normalise a typed/stored category to a known canonical name when possible
    (e.g. 'restaurant' -> 'Restaurants') so Menu/Booking detection works."""
    if not category:
        return "Local Business"
    if category in CATEGORY_TAGS:
        return category
    low = category.strip().lower()
    if low in SYNONYMS:
        return SYNONYMS[low]
    for name in CATEGORY_TAGS:
        if name.lower() == low:
            return name
    return category

MENU_CATS = {"Restaurants", "Cafes", "Bars", "Bakeries"}
BOOKING_CATS = {"Dentists", "Doctors", "Veterinarians", "Hair salons",
                "Beauty salons", "Gyms"}

SERVICES = {
    "Plumbers": [("Emergency Repairs", "Fast response for leaks, bursts and blockages."),
                 ("Drain Cleaning", "Clearing slow and blocked drains and sewers."),
                 ("Water Heaters", "Repair and installation of tanks and tankless units."),
                 ("Fixtures & Fittings", "Taps, toilets, and appliance hook-ups.")],
    "Electricians": [("Wiring & Rewiring", "Safe installation and upgrades for any property."),
                     ("Lighting", "Indoor, outdoor and energy-saving lighting."),
                     ("Panel Upgrades", "Fuse box and breaker panel replacements."),
                     ("Repairs & Safety", "Fault finding and safety inspections.")],
    "Roofing": [("Roof Repairs", "Leak repairs and storm damage fixes."),
                ("Replacement", "Full roof replacement with quality materials."),
                ("Gutters", "Gutter cleaning, repair and installation."),
                ("Inspections", "Free assessments and honest advice.")],
    "Dentists": [("Check-ups & Cleaning", "Routine exams and hygiene visits."),
                 ("Cosmetic Dentistry", "Whitening, veneers and smile makeovers."),
                 ("Fillings & Crowns", "Restorative care for healthy teeth."),
                 ("Emergency Care", "Same-day appointments for urgent problems.")],
    "Auto repair": [("Diagnostics", "Accurate fault finding for any make or model."),
                    ("Brakes & Tires", "Safety-critical repairs done right."),
                    ("Servicing", "Routine maintenance to keep you on the road."),
                    ("Engine Repair", "Experienced repairs and rebuilds.")],
    "Hair salons": [("Cuts & Styling", "Modern cuts for every look."),
                    ("Color", "Balayage, highlights and full color."),
                    ("Treatments", "Conditioning and repair treatments."),
                    ("Special Occasions", "Weddings, events and more.")],
    "Landscapers": [("Lawn Care", "Mowing, feeding and seasonal upkeep."),
                    ("Garden Design", "Planting plans and full makeovers."),
                    ("Hardscaping", "Patios, paths and retaining walls."),
                    ("Clean-ups", "Seasonal and one-off tidy-ups.")],
}
DEFAULT_SERVICES = [
    ("Quality Service", "Reliable, professional work you can count on."),
    ("Experienced Team", "Skilled local specialists who care about the details."),
    ("Fair Pricing", "Honest quotes with no surprises."),
    ("Customer Focused", "Friendly service from first call to finish."),
]

WHY_US = [
    ("Local & Trusted", "A familiar face in the community you can rely on."),
    ("Fast Response", "Quick replies and prompt, dependable service."),
    ("Upfront Pricing", "Clear quotes with no hidden surprises."),
    ("Satisfaction First", "We're not happy until you are."),
]


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "business").lower()).strip("-")
    return s or "business"


def page_structure(category: str) -> list[str]:
    category = _canon(category)
    pages = (["Home", "Menu", "About", "Contact"] if category in MENU_CATS
             else ["Home", "Services", "About", "Contact"])
    if category in BOOKING_CATS:
        pages.append("Book Appointment")
    return pages


def _default_tagline(category, area):
    return f"Trusted {_singular(category)} serving {area}"


def _topbar(phone, hours):
    left = (f'<span>&#9742; <a href="tel:{_esc(phone)}">{_esc(phone)}</a></span>'
            if phone else "")
    right = f'<span>&#9200; {_esc(hours)}</span>' if hours else '<span>Free quotes &middot; Locally owned</span>'
    if not (left or right):
        return ""
    return f'<div class="topbar"><div class="container topbar-inner">{left}{right}</div></div>'


def _nav(name, pages):
    anchors = {"Home": "#top", "Services": "#services", "Menu": "#menu",
               "About": "#about", "Contact": "#contact", "Book Appointment": "#book"}
    links = "".join(f'<a href="{anchors.get(p, "#top")}">{_esc(p)}</a>' for p in pages)
    return (f'<header class="nav" id="top"><div class="container nav-inner">'
            f'<a class="brand" href="#top">{_esc(name)}</a>'
            f'<button class="nav-toggle" aria-label="Menu" onclick="toggleNav()">&#9776;</button>'
            f'<nav class="nav-links" id="navLinks">{links}</nav></div></header>')


def _hero(headline, tagline, phone, hero_img):
    call = (f'<a class="btn btn-light" href="tel:{_esc(phone)}">Call {_esc(phone)}</a>'
            if phone else "")
    style = (f' style="background:linear-gradient(rgba(15,23,42,.55),rgba(15,23,42,.75)),'
             f'url(&#39;{_esc(hero_img)}&#39;) center/cover"' if hero_img else "")
    return (f'<section class="hero"{style}><div class="container">'
            f'<h1>{_esc(headline)}</h1><p class="lede">{_esc(tagline)}</p>'
            f'<div class="cta">{call}'
            f'<a class="btn btn-outline" href="#contact">Get a Free Quote</a></div>'
            f'</div></section>')


def _gallery_section(slug, images, provided):
    tiles = "".join(
        f'<div class="shot"><img loading="lazy" src="{_esc(u)}" alt="Business photo"></div>'
        for u in images)
    note = ("" if provided else
            '<p class="draft-note">Sample photos — replace with the business\'s own '
            'images. Do not use Google/Maps photos (copyright).</p>')
    return (f'<section id="gallery" class="section"><div class="container">'
            f'<h2>Gallery</h2><div class="gallery">{tiles}</div>{note}</div></section>')


def _features_band():
    items = "".join(
        f'<div class="feature"><div class="tick">&#10003;</div>'
        f'<h3>{_esc(t)}</h3><p>{_esc(d)}</p></div>' for t, d in WHY_US)
    return (f'<section class="band"><div class="container">'
            f'<h2>Why Choose Us</h2><div class="features">{items}</div></div></section>')


def _services_section(category):
    items = SERVICES.get(category, DEFAULT_SERVICES)
    heading = "Our Menu" if category in MENU_CATS else "Our Services"
    sec_id = "menu" if category in MENU_CATS else "services"
    cards = "".join(
        f'<div class="card"><div class="card-ico">&#10003;</div>'
        f'<h3>{_esc(t)}</h3><p>{_esc(d)}</p></div>' for t, d in items)
    note = ("Draft menu — replace with your real items and prices."
            if category in MENU_CATS else
            "Draft service list — edit to match what you offer.")
    eyebrow = "On The Menu" if category in MENU_CATS else "What We Do"
    return (f'<section id="{sec_id}" class="section"><div class="container">'
            f'<p class="eyebrow">{eyebrow}</p><h2>{heading}</h2>'
            f'<div class="grid">{cards}</div>'
            f'<p class="draft-note">{note}</p></div></section>')


def _cta_band(name, phone):
    call = (f'<a class="btn btn-light" href="tel:{_esc(phone)}">Call {_esc(phone)}</a>'
            if phone else "")
    return (f'<section class="cta-band"><div class="container">'
            f'<h2>Ready to get started?</h2>'
            f'<p>Get in touch today for a free, no-obligation quote.</p>'
            f'<div class="cta">{call}'
            f'<a class="btn btn-outline" href="#contact">Contact Us</a></div>'
            f'</div></section>')


def _about_section(name, category, area):
    text = (f"{name} is a locally trusted {_singular(category)} proudly serving "
            f"{area}. Our team is committed to quality work, fair pricing, and "
            "friendly service on every job. We treat every customer like a "
            "neighbour — because most of them are.")
    return (f'<section id="about" class="section alt"><div class="container about">'
            f'<h2>About {_esc(name)}</h2><p>{_esc(text)}</p>'
            f'<p class="draft-note">Draft copy — review and personalise before publishing.</p>'
            f'</div></section>')


def _testimonials_section(lead, testimonials):
    """Only rendered when there are REAL, user-supplied testimonials or a real
    rating. Never invents reviews; omitted entirely if there's nothing real."""
    blocks = []
    rating, count = lead.get("rating"), lead.get("review_count")
    if rating and count:
        blocks.append(f'<div class="reviews-summary"><span class="stars">&#9733; '
                      f'{_esc(rating)}</span><span>{_esc(count)} reviews</span></div>')
    for text, author in testimonials:
        by = f'<cite>&mdash; {_esc(author)}</cite>' if author else ""
        blocks.append(f'<blockquote class="testimonial">&ldquo;{_esc(text)}&rdquo;{by}</blockquote>')
    if not blocks:
        return ""
    return (f'<section class="section"><div class="container">'
            f'<h2>What Customers Say</h2><div class="testimonials">{"".join(blocks)}</div>'
            f'</div></section>')


def _service_area_band(lead, category, area):
    return (f'<section class="area-band"><div class="container">'
            f'<p><strong>Proudly serving {_esc(area)}</strong> and the surrounding area. '
            f'Call today for fast, friendly {_esc(_singular(category))} service.</p>'
            f'</div></section>')


def _faq_section(category, area):
    faqs = [
        ("Do you offer free quotes?",
         "Yes — get in touch and we'll provide a free, no-obligation quote."),
        ("What areas do you cover?",
         f"We serve {area} and the surrounding area."),
    ]
    if category in BOOKING_CATS:
        faqs.append(("How do I book an appointment?",
                     "Use the booking form above or give us a call — we'll confirm a time that suits you."))
    elif category in MENU_CATS:
        faqs.append(("Do you take reservations?",
                     "Yes — call ahead or use the contact form to reserve a table."))
    else:
        faqs.append(("How quickly can you help?",
                     "Contact us and we'll respond promptly to arrange a visit."))
    items = "".join(f'<div class="faq-item"><h3>{_esc(q)}</h3><p>{_esc(a)}</p></div>'
                    for q, a in faqs)
    return (f'<section class="section alt"><div class="container">'
            f'<h2>Frequently Asked Questions</h2><div class="faq">{items}</div></div></section>')


def _form_open(live, email, kind):
    """Contact/booking form. Live export posts to free FormSubmit; preview only alerts."""
    if live:
        target = email or "your@email.com"
        return (f'<form class="form" action="https://formsubmit.co/{_esc(target)}" method="POST">'
                f'<input type="hidden" name="_subject" value="New enquiry from your website">'
                f'<input type="hidden" name="_captcha" value="false">')
    return '<form class="form" onsubmit="return demoSubmit(event)">'


def _booking_section(name, live, email):
    return (f'<section id="book" class="section alt"><div class="container">'
            f'<h2>Book an Appointment</h2>'
            f'<p>Request a time that suits you and we\'ll confirm by phone.</p>'
            f'{_form_open(live, email, "booking")}'
            f'<input type="text" name="name" placeholder="Your name" required>'
            f'<input type="tel" name="phone" placeholder="Phone number" required>'
            f'<input type="date" name="preferred_date">'
            f'<button class="btn" type="submit">Request Appointment</button></form>'
            f'</div></section>')


def _map_embed(lat, lon):
    if not (lat and lon):
        return ""
    d = 0.008
    bbox = f"{lon - d},{lat - d},{lon + d},{lat + d}"
    src = (f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}"
           f"&layer=mapnik&marker={lat},{lon}")
    return (f'<div class="map"><iframe loading="lazy" src="{_esc(src)}" '
            f'title="Location map"></iframe></div>')


def _contact_section(lead, phone, email, address, hours, live):
    rows = []
    rows.append(f'<li><strong>Phone:</strong> <a href="tel:{_esc(phone)}">{_esc(phone)}</a></li>'
                if phone else '<li><strong>Phone:</strong> [add your phone number]</li>')
    if email:
        rows.append(f'<li><strong>Email:</strong> <a href="mailto:{_esc(email)}">{_esc(email)}</a></li>')
    rows.append(f'<li><strong>Address:</strong> {_esc(address)}</li>' if address
                else '<li><strong>Address:</strong> [add your address]</li>')
    rows.append(f'<li><strong>Hours:</strong> {_esc(hours) if hours else "Mon-Fri [add your opening hours]"}</li>')
    map_html = _map_embed(lead.get("lat"), lead.get("lon"))
    return (f'<section id="contact" class="section"><div class="container contact-grid">'
            f'<div><h2>Contact Us</h2><ul class="contact-list">{"".join(rows)}</ul>{map_html}</div>'
            f'<div>{_form_open(live, email, "contact")}'
            f'<input type="text" name="name" placeholder="Your name" required>'
            f'<input type="email" name="email" placeholder="Your email" required>'
            f'<textarea name="message" placeholder="How can we help?" rows="4"></textarea>'
            f'<button class="btn" type="submit">Send Message</button></form></div>'
            f'</div></section>')


def _fab(phone):
    if not phone:
        return ""
    return f'<a class="fab" href="tel:{_esc(phone)}" aria-label="Call now">&#9742; Call</a>'


def _footer(name):
    return (f'<footer class="site-footer"><div class="container">'
            f'<p>&copy; <span id="yr"></span> {_esc(name)}. All rights reserved.</p>'
            f'<p class="muted">Website draft — review all content before going live.</p>'
            f'</div></footer>')


def _body(lead, o, testimonials, live):
    real_name = lead.get("name") or "Your Business"
    headline = o.get("headline") or real_name
    category = _canon(lead.get("category"))
    area = service_area(lead)
    phone = o.get("phone") or lead.get("phone") or ""
    email = o.get("email") or lead.get("email") or ""
    address = o.get("address") or lead.get("address") or ""
    hours = o.get("hours") or ""
    tagline = o.get("tagline") or _default_tagline(category, area)

    # Images: use provided URLs (the business's own photos) or free sample stock.
    hero_img = o.get("hero") or ""
    sl = slug(real_name)
    provided_imgs = [o.get("img1"), o.get("img2"), o.get("img3")]
    if any(provided_imgs):
        gallery_imgs = [u for u in provided_imgs if u]
        imgs_provided = True
    else:
        gallery_imgs = [f"https://picsum.photos/seed/{sl}-{i}/600/450" for i in (1, 2, 3)]
        imgs_provided = False

    parts = [
        _topbar(phone, hours),
        _nav(real_name, page_structure(category)),
        _hero(headline, tagline, phone, hero_img),
        _features_band(),
        _services_section(category),
        _gallery_section(sl, gallery_imgs, imgs_provided),
        _about_section(real_name, category, area),
        _testimonials_section(lead, testimonials),
        _service_area_band(lead, category, area),
        _faq_section(category, area),
    ]
    if category in BOOKING_CATS:
        parts.append(_booking_section(real_name, live, email))
    parts.append(_contact_section(lead, phone, email, address, hours, live))
    parts.append(_cta_band(real_name, phone))
    parts.append(_fab(phone))
    parts.append(_footer(real_name))
    return "\n".join(p for p in parts if p)


def _css(color):
    color = color if re.match(r"^#[0-9a-fA-F]{3,6}$", color or "") else "#2563eb"
    return f""":root{{--primary:{color};--dark:#0f172a;--muted:#64748b;--bg:#ffffff;--soft:#f1f5f9}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth;scroll-padding-top:72px}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--dark);line-height:1.6;background:var(--bg)}}
.container{{width:100%;max-width:1080px;margin:0 auto;padding:0 20px}}
a{{color:var(--primary);text-decoration:none}}
.topbar{{background:var(--dark);color:#e2e8f0;font-size:13px}}
.topbar-inner{{display:flex;justify-content:space-between;align-items:center;height:38px}}
.topbar a{{color:#fff}}
.nav{{position:sticky;top:0;z-index:20;background:#fff;border-bottom:1px solid #e2e8f0}}
.nav-inner{{display:flex;align-items:center;justify-content:space-between;height:64px}}
.brand{{font-weight:800;font-size:20px;color:var(--dark)}}
.nav-links{{display:flex;gap:22px}}
.nav-links a{{color:var(--dark);font-weight:600;font-size:15px}}
.nav-links a:hover{{color:var(--primary)}}
.nav-toggle{{display:none;font-size:24px;background:none;border:0;cursor:pointer}}
.hero{{background:linear-gradient(135deg,var(--primary),#1e293b);color:#fff;padding:88px 0;text-align:center}}
.hero h1{{font-size:44px;font-weight:800;margin-bottom:14px}}
.lede{{font-size:20px;opacity:.92;margin-bottom:28px}}
.cta{{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}}
.btn{{display:inline-block;padding:13px 26px;border-radius:8px;font-weight:700;background:var(--primary);color:#fff;border:2px solid var(--primary);cursor:pointer}}
.btn:hover{{opacity:.9}}
.btn-light{{background:#fff;color:var(--primary);border-color:#fff}}
.btn-outline{{background:transparent;color:#fff;border-color:#fff}}
.section{{padding:64px 0}}
.section.alt{{background:var(--soft)}}
h2{{font-size:30px;text-align:center;margin-bottom:32px}}
.eyebrow{{text-align:center;text-transform:uppercase;letter-spacing:2px;font-size:13px;font-weight:700;color:var(--primary);margin-bottom:6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:26px;box-shadow:0 4px 14px rgba(0,0,0,.06);transition:transform .2s ease,box-shadow .2s ease}}
.card:hover{{transform:translateY(-4px);box-shadow:0 12px 28px rgba(0,0,0,.12)}}
.card-ico{{width:42px;height:42px;line-height:42px;text-align:center;border-radius:10px;background:var(--primary);color:#fff;font-size:20px;font-weight:700;margin-bottom:12px}}
.card h3{{color:var(--dark);margin-bottom:8px;font-size:19px}}
.band{{background:var(--dark);color:#e2e8f0;padding:56px 0}}
.band h2{{color:#fff}}
.features{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:24px}}
.feature{{text-align:center}}
.feature .tick{{width:44px;height:44px;line-height:44px;border-radius:50%;background:var(--primary);color:#fff;font-size:22px;margin:0 auto 10px}}
.feature h3{{font-size:17px;margin-bottom:4px;color:#fff}}
.feature p{{font-size:14px;color:#cbd5e1}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.shot{{aspect-ratio:4/3;border-radius:12px;overflow:hidden;background:#e2e8f0}}
.shot img{{width:100%;height:100%;object-fit:cover;display:block}}
.about{{max-width:760px;text-align:center}}
.about p{{font-size:18px;color:#334155;margin-bottom:12px}}
.reviews-summary{{display:flex;gap:18px;justify-content:center;font-size:20px;font-weight:700;margin-bottom:18px}}
.stars{{color:#f59e0b}}
.testimonials{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}}
.testimonial{{background:#fff;border:1px solid #e2e8f0;border-left:4px solid var(--primary);border-radius:10px;padding:20px;font-style:italic;color:#334155}}
.testimonial cite{{display:block;margin-top:10px;font-style:normal;font-weight:700;color:var(--dark)}}
.area-band{{background:var(--primary);color:#fff;padding:26px 0;text-align:center;font-size:18px}}
.faq{{max-width:760px;margin:0 auto;display:flex;flex-direction:column;gap:14px}}
.faq-item{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px}}
.faq-item h3{{color:var(--primary);font-size:17px;margin-bottom:4px}}
.contact-grid{{display:grid;grid-template-columns:1fr 1fr;gap:32px}}
.contact-list{{list-style:none;font-size:17px;margin-bottom:16px}}
.contact-list li{{padding:8px 0;border-bottom:1px solid #e2e8f0}}
.map iframe{{width:100%;height:220px;border:1px solid #e2e8f0;border-radius:10px}}
.form{{display:flex;flex-direction:column;gap:12px}}
.form input,.form textarea{{padding:12px;border:1px solid #cbd5e1;border-radius:8px;font-size:15px;font-family:inherit}}
.muted{{color:var(--muted);text-align:center}}
.draft-note{{margin-top:18px;text-align:center;font-size:13px;color:#b45309;background:#fffbeb;border:1px dashed #f59e0b;border-radius:8px;padding:8px}}
.cta-band{{background:linear-gradient(135deg,var(--primary),#1e293b);color:#fff;padding:56px 0;text-align:center}}
.cta-band h2{{color:#fff;margin-bottom:8px}}
.cta-band p{{margin-bottom:22px;opacity:.92;font-size:18px}}
.cta-band .cta{{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}}
.fab{{position:fixed;right:18px;bottom:18px;z-index:30;background:var(--primary);color:#fff;padding:14px 20px;border-radius:50px;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.25)}}
html.anim .section,html.anim .band,html.anim .cta-band{{opacity:0;transform:translateY(24px);transition:opacity .6s ease,transform .6s ease}}
html.anim .shown{{opacity:1;transform:none}}
.site-footer{{background:var(--dark);color:#cbd5e1;padding:32px 0;text-align:center}}
.site-footer .muted{{color:#94a3b8;font-size:13px;margin-top:6px}}
@media(max-width:760px){{
  .nav-toggle{{display:block}}
  .nav-links{{display:none;position:absolute;top:64px;left:0;right:0;background:#fff;flex-direction:column;padding:12px 20px;border-bottom:1px solid #e2e8f0}}
  .nav-links.open{{display:flex}}
  .hero h1{{font-size:32px}}
  .contact-grid{{grid-template-columns:1fr}}
}}"""


def _js():
    return """function toggleNav(){document.getElementById('navLinks').classList.toggle('open');}
function demoSubmit(e){e.preventDefault();alert('This is a demo form. In the exported website it emails the business automatically (free, via FormSubmit) once the site is published.');return false;}
var yr=document.getElementById('yr'); if(yr) yr.textContent=new Date().getFullYear();
// Gentle scroll-reveal (skipped if the visitor prefers reduced motion)
(function(){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.documentElement.classList.add('anim');
  var els=document.querySelectorAll('.section,.band,.cta-band');
  if(!('IntersectionObserver' in window)){els.forEach(function(e){e.classList.add('shown')});return;}
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(en){if(en.isIntersecting){en.target.classList.add('shown');io.unobserve(en.target);}});
  },{threshold:0.12});
  els.forEach(function(e){io.observe(e);});
})();"""


def _favicon(color):
    color = color if re.match(r"^#[0-9a-fA-F]{3,6}$", color or "") else "#2563eb"
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
           f"<rect width='32' height='32' rx='6' fill='{color}'/></svg>")
    return "data:image/svg+xml," + html.escape(svg, quote=True).replace("#", "%23")


def _parse_testimonials(o):
    out = []
    for i in ("1", "2", "3"):
        text = (o.get("r" + i) or "").strip()
        if text:
            out.append((text, (o.get("r" + i + "by") or "").strip()))
    return out


def _readme(name):
    return f"""# {name} — Website

A ready-to-publish static website generated by LeadScout. Plain HTML/CSS/JS —
no build step, no server.

## Files
- `index.html` — the website
- `style.css` — styling
- `script.js` — small interactions (mobile menu)
- `DEPLOY.md` — **how to put it online for free** (start here)

## Before going live
- Review and personalise all copy (About, Services/Menu).
- Replace every `[ ]` placeholder (phone, address, hours).
- The contact form is pre-wired to **FormSubmit** (free). On first submission
  FormSubmit sends a one-time confirmation email to activate it — see DEPLOY.md.
- Only add real, permitted customer reviews. Do not invent testimonials.
"""


def _deploy(name, email):
    target = email or "your@email.com"
    return f"""# Publish "{name}" online — for FREE

This is a plain static website. You can put it online in a few minutes with no
cost and no coding. Pick ONE method below.

## Preview it first
Double-click `index.html` to open it in any browser.

## Option A — Netlify Drop (easiest, ~2 minutes, free)
1. Go to https://app.netlify.com/drop
2. Drag this whole folder onto the page.
3. Done — you get a live URL like `your-site.netlify.app` instantly.
4. (Optional) Create a free Netlify account to keep it and add a custom domain.

## Option B — Cloudflare Pages (free)
1. Create a free account at https://pages.cloudflare.com
2. "Upload assets" and drop these files in. It goes live on a free domain.

## Option C — GitHub Pages (free)
1. Create a free GitHub account and a new public repository.
2. Upload these files, then Settings → Pages → deploy from the main branch.
3. Your site appears at `username.github.io/repo-name`.

## Custom domain (optional, ~$10/year for the domain only)
Buy a domain (Namecheap, Cloudflare, Porkbun) and point it at your host in the
host's "Custom domain" settings. Hosting stays free; only the domain costs money.

## Make the contact form work (free, no signup)
The form already posts to FormSubmit → `{target}`.
1. Publish the site (Option A/B/C above).
2. Submit the form once yourself. FormSubmit emails a confirmation link to
   `{target}` — click it to activate. After that, every submission is emailed
   automatically. See https://formsubmit.co for details.
3. To change the destination email, edit the `action="https://formsubmit.co/..."`
   line in `index.html`.

## Photos / images
Any sample photos in this site are free stock placeholders. Replace them with
the **client's own photos** (ones they give you, or from their Facebook/site
that they own). Edit the `src="..."` of each `<img>` in `index.html`, or drop
image files in the folder and point to them (e.g. `src="photo1.jpg"`).
Do **not** use photos from Google/Google Maps — those are copyrighted.
Need free stock? Try pexels.com or unsplash.com (free for commercial use).

## Going from demo to a paid client site
1. Get the client's real details (phone, address, hours, services, photos).
2. Replace the placeholders, draft copy, and sample images in `index.html`.
3. Set the form's FormSubmit email to the client's email.
4. Publish with any option above, then connect their custom domain.
"""


def generate_site(lead, overrides=None):
    o = overrides or {}
    category = _canon(lead.get("category"))
    testimonials = _parse_testimonials(o)
    color = o.get("color", "#2563eb")
    email = o.get("email") or lead.get("email") or ""

    css, js = _css(color), _js()
    body_preview = _body(lead, o, testimonials, live=False)
    body_live = _body(lead, o, testimonials, live=True)

    name = lead.get("name") or "Your Business"
    area = service_area(lead)
    meta_desc = f"{name} - {category} serving {area}. Contact us today."
    head = (f'<meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_esc(name)} | {_esc(category)}</title>'
            f'<meta name="description" content="{_esc(meta_desc)}">'
            f'<link rel="icon" href="{_favicon(color)}">')

    html_linked = (f'<!doctype html><html lang="en"><head>{head}'
                   f'<link rel="stylesheet" href="style.css"></head><body>'
                   f'{body_live}<script src="script.js"></script></body></html>')
    html_inline = (f'<!doctype html><html lang="en"><head>{head}'
                   f'<style>{css}</style></head><body>'
                   f'{body_preview}<script>{js}</script></body></html>')

    return {
        "pages": page_structure(category),
        "html": html_linked,
        "inline": html_inline,
        "css": css,
        "js": js,
        "readme": _readme(name),
        "deploy": _deploy(name, email),
    }
