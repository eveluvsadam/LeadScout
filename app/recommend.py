"""Turn analysis findings into a short, human sales recommendation.

Rule-based (no LLM / no paid API) so it runs offline and instantly.
The output reads like a one-line pitch an agency could act on.
"""


def build_recommendation(lead: dict, analysis: dict) -> str:
    name = lead.get("name", "This business")
    has_site = bool(lead.get("website"))
    socials = [s for s in ("facebook", "instagram", "linkedin", "twitter")
               if lead.get(s)]

    # No website at all — the strongest pitch.
    if not has_site:
        if socials:
            where = " and ".join(socials).replace("facebook", "a Facebook page") \
                                         .replace("instagram", "Instagram") \
                                         .replace("linkedin", "LinkedIn") \
                                         .replace("twitter", "X/Twitter")
            return (f"{name} has no website and relies only on {where}. "
                    "A simple professional website would boost credibility and "
                    "capture customers searching on Google.")
        return (f"{name} has no website. A basic professional site plus a Google "
                "Business Profile could significantly improve visibility and "
                "attract new customers.")

    # Site exists but couldn't be loaded / is dead.
    if not analysis["reachable"]:
        return (f"{name} lists a website but it failed to load. A working, modern "
                "site is an easy win to recover lost customers.")

    issues = []
    if not analysis["https"]:
        issues.append("no HTTPS/SSL security")
    if not analysis["mobile_friendly"]:
        issues.append("poor mobile experience")
    if not analysis["meta_title"] or not analysis["meta_description"]:
        issues.append("missing SEO basics (title/description)")
    if analysis["load_ms"] and analysis["load_ms"] > 3000:
        issues.append("slow loading")
    if analysis["broken_links"]:
        issues.append(f"{analysis['broken_links']} broken link(s)")

    if issues:
        joined = ", ".join(issues[:-1]) + (" and " + issues[-1] if len(issues) > 1 else issues[0])
        return (f"{name}'s website has {joined}. A redesign and local SEO campaign "
                "could improve search visibility and conversions.")

    if analysis["modernization_score"] < 70:
        return (f"{name}'s website works but looks dated. A modern refresh would "
                "strengthen their brand and keep them competitive.")

    return (f"{name} already has a solid, modern website. Lower priority — consider "
            "offering ongoing SEO, content, or paid-ads services instead.")
