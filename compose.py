"""
Vera Message Composition Engine
Deterministic compose(category, merchant, trigger, customer?) → message output
"""

import re
from datetime import datetime
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# CATEGORY PROFILES
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_PROFILES = {
    "dentist": {
        "tone": "clinical, reassuring, trust-first",
        "cta_style": "appointment-based",
        "urgency_frame": "health-outcome",
        "avoid": ["discount frenzy", "sales pressure"],
        "seasonal_hooks": {
            "jan": "New Year, fresh smile",
            "feb": "Valentine's – confidence boost",
            "apr": "summer prep",
            "sep": "back-to-school checkups",
            "dec": "year-end benefits",
        },
        "offer_patterns": ["free consultation", "bundled checkup+cleaning", "EMI on braces"],
        "identity": "Doctor",
    },
    "salon": {
        "tone": "visual, aspirational, trend-aware",
        "cta_style": "booking-based",
        "urgency_frame": "limited slots / trending look",
        "avoid": ["overly clinical language", "generic greetings"],
        "seasonal_hooks": {
            "feb": "Valentine's glow-up",
            "mar": "Holi colour protection",
            "oct": "festive season looks",
            "nov": "wedding season prep",
            "dec": "New Year transformation",
        },
        "offer_patterns": ["combo packages", "express services", "loyalty top-up"],
        "identity": "Owner",
    },
    "restaurant": {
        "tone": "warm, sensory, community-rooted",
        "cta_style": "order or reservation",
        "urgency_frame": "time-limited / today-only",
        "avoid": ["formal language", "health scare tactics"],
        "seasonal_hooks": {
            "jan": "Makar Sankranti specials",
            "mar": "Holi thali",
            "aug": "Independence Day meal deals",
            "oct": "Navratri specials",
            "nov": "Diwali sweets & combos",
        },
        "offer_patterns": ["daily specials", "bulk order discounts", "loyalty stamp"],
        "identity": "Chef / Owner",
    },
    "gym": {
        "tone": "energetic, results-driven, peer-motivating",
        "cta_style": "membership or trial",
        "urgency_frame": "transformation / batch starts",
        "avoid": ["guilt framing", "body shaming adjacent"],
        "seasonal_hooks": {
            "jan": "New Year resolution batch",
            "apr": "summer shred",
            "sep": "festive fit",
        },
        "offer_patterns": ["trial pass", "buddy referral", "quarterly discount"],
        "identity": "Coach / Owner",
    },
    "pharmacy": {
        "tone": "utility-first, calm, service-oriented",
        "cta_style": "order or inquiry",
        "urgency_frame": "availability / refill reminder",
        "avoid": ["scare tactics", "over-promising health claims"],
        "seasonal_hooks": {
            "jan": "winter wellness",
            "jun": "monsoon health prep",
            "oct": "festive immunity boost",
        },
        "offer_patterns": ["generic substitution savings", "home delivery", "refill reminder"],
        "identity": "Owner",
    },
}


def _get_category_profile(category: str) -> dict:
    key = category.lower().rstrip("s")  # dentists→dentist, salons→salon
    return CATEGORY_PROFILES.get(key, CATEGORY_PROFILES.get(category.lower(), {
        "tone": "professional, helpful",
        "cta_style": "inquiry-based",
        "urgency_frame": "timely",
        "avoid": [],
        "seasonal_hooks": {},
        "offer_patterns": [],
        "identity": "Owner",
    }))


# ──────────────────────────────────────────────────────────────────────────────
# TRIGGER HANDLERS
# ──────────────────────────────────────────────────────────────────────────────

def _handle_recall(merchant: dict, category_profile: dict, customer: Optional[dict]) -> dict:
    """Lapsed customer or merchant reactivation."""
    name = merchant.get("identity", {}).get("name", "your business")
    perf = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    
    best_offer = _pick_best_offer(offers)
    rating = perf.get("rating", 4.2)
    last_visit = customer.get("last_visit_days_ago", 45) if customer else None
    cust_name = customer.get("name", "") if customer else ""
    
    lapse_hint = f"It's been {last_visit} days" if last_visit else "It's been a while"
    
    offer_line = f" — {best_offer['label']} at ₹{best_offer['price']}" if best_offer else ""
    name_prefix = f"Hi {cust_name}! " if cust_name else ""
    
    return {
        "headline": f"{lapse_hint} since your last visit.",
        "body": (
            f"{name_prefix}{lapse_hint} since your last visit to {name}. "
            f"We're rated {rating}★ by {perf.get('total_reviews', 'many')} customers{offer_line}. "
            f"Want me to book a slot for you this week?"
        ),
        "cta": "Book now",
        "rationale": f"Recall trigger — {lapse_hint} lapse. Best offer surfaced to reduce re-engagement friction.",
    }


def _handle_spike(merchant: dict, category_profile: dict, trigger: dict) -> dict:
    """Search/footfall spike in the area."""
    name = merchant.get("identity", {}).get("name", "your business")
    perf = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    trigger_meta = trigger.get("meta", {})
    
    spike_count = trigger_meta.get("search_count", trigger_meta.get("searchers", 120))
    query_term = trigger_meta.get("query", trigger_meta.get("search_term", "your service"))
    locality = merchant.get("identity", {}).get("locality", "your area")
    
    best_offer = _pick_best_offer(offers)
    offer_line = f" Send them a ₹{best_offer['price']} offer?" if best_offer else " Want me to run a targeted offer?"
    
    return {
        "headline": f'{spike_count} people near you just searched for \u201c{query_term}\u201d.',
        "body": (
            f'{spike_count} people in {locality} are actively searching for \u201c{query_term}\u201d right now. '
            f"{name} has capacity today.{offer_line}"
        ),
        "cta": "Run campaign",
        "rationale": f"Demand spike — {spike_count} live searchers for '{query_term}'. High-intent moment, merchant has capacity.",
    }


def _handle_dip(merchant: dict, category_profile: dict, trigger: dict) -> dict:
    """Revenue or footfall dip."""
    name = merchant.get("identity", {}).get("name", "your business")
    perf = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    trigger_meta = trigger.get("meta", {})
    
    dip_pct = trigger_meta.get("dip_percent", trigger_meta.get("drop_percent", 22))
    vs_what = trigger_meta.get("vs", "last week")
    
    best_offer = _pick_best_offer(offers)
    offer_line = (
        f"A quick flash deal — {best_offer['label']} at ₹{best_offer['price']} — could pull in walk-ins today."
        if best_offer else
        "A targeted flash deal today could recover lost footfall."
    )
    
    return {
        "headline": f"Orders are down {dip_pct}% vs {vs_what}.",
        "body": (
            f"{name}'s orders are down {dip_pct}% vs {vs_what}. "
            f"{offer_line} Should I set it up?"
        ),
        "cta": "Run flash deal",
        "rationale": f"Dip trigger — {dip_pct}% drop vs {vs_what}. Flash deal recommended to recover.",
    }


def _handle_research(merchant: dict, category_profile: dict, trigger: dict) -> dict:
    """User is actively researching (comparing options)."""
    name = merchant.get("identity", {}).get("name", "your business")
    perf = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    trigger_meta = trigger.get("meta", {})
    
    competitor = trigger_meta.get("competitor", None)
    query = trigger_meta.get("query", "your service")
    rating = perf.get("rating", 4.3)
    reviews = perf.get("total_reviews", 80)
    
    differentiator = _pick_differentiator(merchant, perf)
    comp_line = f" (vs {competitor})" if competitor else ""
    
    best_offer = _pick_best_offer(offers)
    offer_line = f" + {best_offer['label']} at ₹{best_offer['price']}" if best_offer else ""
    
    return {
        "headline": f'Someone nearby is comparing options for \u201c{query}\u201d{comp_line}.',
        "body": (
            f'A customer is actively researching \u201c{query}\u201d in your area{comp_line}. '
            f"{name} has {rating}★ from {reviews} reviews and {differentiator}{offer_line}. "
            f"Want me to send them a personalised intro offer?"
        ),
        "cta": "Send intro offer",
        "rationale": f"Research trigger — high-intent comparison. Surfacing differentiator ({differentiator}) + best offer to convert.",
    }


def _handle_festival(merchant: dict, category_profile: dict, trigger: dict) -> dict:
    """Festival / seasonal moment."""
    name = merchant.get("identity", {}).get("name", "your business")
    perf = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    trigger_meta = trigger.get("meta", {})
    
    festival = trigger_meta.get("festival", trigger_meta.get("event", "the upcoming festive season"))
    days_to = trigger_meta.get("days_to_event", trigger_meta.get("days_away", 5))
    
    cat_key = _month_key()
    seasonal_hook = category_profile.get("seasonal_hooks", {}).get(cat_key, f"{festival} special")
    
    best_offer = _pick_best_offer(offers)
    offer_line = f"How about a {festival} special — {best_offer['label']} at ₹{best_offer['price']}?" if best_offer else f"Want me to run a {festival} campaign?"
    
    return {
        "headline": f"{festival} is {days_to} days away.",
        "body": (
            f"{festival} is {days_to} days away and customers are already planning. "
            f"{name}'s {seasonal_hook} could drive pre-bookings this week. "
            f"{offer_line}"
        ),
        "cta": f"Launch {festival} campaign",
        "rationale": f"Festival trigger — {days_to} days to {festival}. Seasonal hook '{seasonal_hook}' aligned with category pattern.",
    }


def _handle_review(merchant: dict, category_profile: dict, trigger: dict) -> dict:
    """New review received (positive or negative)."""
    name = merchant.get("identity", {}).get("name", "your business")
    trigger_meta = trigger.get("meta", {})
    rating_received = trigger_meta.get("rating", 5)
    reviewer = trigger_meta.get("reviewer_name", "a customer")
    review_text = trigger_meta.get("review_text", "")
    
    if rating_received >= 4:
        body = (
            f"{reviewer} just rated {name} {rating_received}★. "
            f"{'They said: \"' + review_text[:60] + '...\"' if review_text else ''} "
            f"Happy customers refer friends — want me to send them a ₹50 referral nudge?"
        )
        cta = "Send referral nudge"
        rationale = "Positive review — high social proof moment. Referral ask is low-friction and timely."
    else:
        body = (
            f"{reviewer} left a {rating_received}★ review. "
            f"A quick personal reply within 2 hours can turn this around. Want me to draft a response?"
        )
        cta = "Draft reply"
        rationale = "Negative review — recovery window is time-sensitive. Draft reply reduces churn risk."
    
    return {"headline": f"New {rating_received}★ review from {reviewer}.", "body": body, "cta": cta, "rationale": rationale}


def _handle_generic(merchant: dict, category_profile: dict, trigger: dict) -> dict:
    """Fallback for unknown triggers."""
    name = merchant.get("identity", {}).get("name", "your business")
    perf = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    
    best_offer = _pick_best_offer(offers)
    rating = perf.get("rating", 4.2)
    
    offer_line = f" Featuring: {best_offer['label']} at ₹{best_offer['price']}." if best_offer else ""
    
    return {
        "headline": "Your customers are ready — are you?",
        "body": (
            f"{name} is rated {rating}★ and customers are searching today.{offer_line} "
            f"Want me to run a targeted campaign to bring them in?"
        ),
        "cta": "Start campaign",
        "rationale": "Generic trigger — surfacing best offer + rating to drive engagement.",
    }


TRIGGER_HANDLERS = {
    "recall": _handle_recall,
    "spike": _handle_spike,
    "dip": _handle_dip,
    "research": _handle_research,
    "festival": _handle_festival,
    "review": _handle_review,
    "seasonal": _handle_festival,  # alias
}


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _pick_best_offer(offers: list) -> Optional[dict]:
    """Pick the offer with the highest discount or lowest price for conversion."""
    if not offers:
        return None
    # Prefer offers with explicit discount_pct, else lowest price
    scored = []
    for o in offers:
        score = o.get("discount_pct", 0) * 2 + (1 / max(o.get("price", 999), 1)) * 100
        scored.append((score, o))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _pick_differentiator(merchant: dict, perf: dict) -> str:
    """Return one sharp differentiator string."""
    hints = []
    if perf.get("response_time_mins"):
        hints.append(f"responds in {perf['response_time_mins']} mins")
    if perf.get("repeat_rate_pct"):
        hints.append(f"{perf['repeat_rate_pct']}% repeat customers")
    if perf.get("orders_last_30d"):
        hints.append(f"{perf['orders_last_30d']} orders in 30 days")
    return hints[0] if hints else "a strong local presence"


def _month_key() -> str:
    return datetime.now().strftime("%b").lower()[:3]


def _build_suppression_key(merchant_id: str, trigger_type: str, customer_id: Optional[str]) -> str:
    base = f"vera:{merchant_id}:{trigger_type}"
    if customer_id:
        base += f":{customer_id}"
    return base


def _get_send_as(category_profile: dict, merchant: dict) -> str:
    identity = category_profile.get("identity", "Owner")
    name = merchant.get("identity", {}).get("name", "")
    return f"Vera (on behalf of {name})" if name else f"Vera ({identity} Assistant)"


# ──────────────────────────────────────────────────────────────────────────────
# MAIN COMPOSE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def compose(
    category: str,
    merchant: dict,
    trigger: dict,
    customer: Optional[dict] = None,
) -> dict:
    """
    Deterministic message composition.
    
    Returns:
        message: str          — The full message text
        cta: str              — Single clear call-to-action label
        send_as: str          — Identity to send from
        suppression_key: str  — Idempotency / rate-limit key
        rationale: str        — Why this message was chosen
        headline: str         — Short punchy opening line
    """
    cat_profile = _get_category_profile(category)
    
    trigger_type = trigger.get("type", "generic").lower()
    merchant_id = merchant.get("identity", {}).get("id", merchant.get("id", "m_unknown"))
    customer_id = customer.get("id") if customer else None
    
    # Route to trigger handler
    handler = TRIGGER_HANDLERS.get(trigger_type)
    
    if trigger_type == "recall" and handler:
        result = handler(merchant, cat_profile, customer)
    elif handler:
        result = handler(merchant, cat_profile, trigger)
    else:
        result = _handle_generic(merchant, cat_profile, trigger)
    
    # Inject category-specific polish
    message = result["body"].strip()
    
    # Append seasonal hook if relevant and not already festival trigger
    if trigger_type not in ("festival", "seasonal"):
        month_key = _month_key()
        seasonal = cat_profile.get("seasonal_hooks", {}).get(month_key)
        if seasonal and seasonal.lower() not in message.lower():
            message += f" 📅 Tip: {seasonal} is a great hook right now."
    
    return {
        "message": message,
        "headline": result.get("headline", ""),
        "cta": result["cta"],
        "send_as": _get_send_as(cat_profile, merchant),
        "suppression_key": _build_suppression_key(merchant_id, trigger_type, customer_id),
        "rationale": result["rationale"],
        "trigger_type": trigger_type,
        "category": category,
        "merchant_id": merchant_id,
    }
