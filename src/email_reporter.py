"""
src/email_reporter.py
======================
Automated email report module.

Builds a formatted HTML email with today's ranked picks
and sends it via SendGrid.

Main functions:
    send_picks_email(hitters)     -> sends the daily picks email
    build_html_email(hitters)     -> returns HTML string
    build_text_email(hitters)     -> returns plain text fallback
"""

import datetime
from src.config import CONFIG
from src.models import Hitter

try:
    import sendgrid
    from sendgrid.helpers.mail import (
        Mail, Email, To, Content, MimeType
    )
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("  [warn] sendgrid not installed — email delivery unavailable")


# ─────────────────────────── HELPERS ───────────────────────────

def _score_color(score: int) -> str:
    """Return hex color based on score range."""
    if score >= 75:
        return "#00b87a"
    if score >= 60:
        return "#f5a623"
    return "#ff4f4f"


def _confidence_badge(confidence: str) -> str:
    """Return HTML badge for confidence level."""
    colors = {
        "high":   ("#00b87a", "#e6f9f3"),
        "medium": ("#f5a623", "#fef6e6"),
        "low":    ("#ff4f4f", "#fff0f0"),
    }
    text_color, bg_color = colors.get(
        confidence, ("#888888", "#f0f0f0")
    )
    label = (confidence or "med").upper()
    return (
        f'<span style="background:{bg_color}; color:{text_color}; '
        f'padding:3px 10px; border-radius:12px; font-size:11px; '
        f'font-weight:600; font-family:monospace;">{label}</span>'
    )


def _recommendation_label(rec: str) -> str:
    """Return human readable recommendation label."""
    labels = {
        "strong_pick": "★ Strong Pick",
        "lean_pick":   "◎ Lean Pick",
        "neutral":     "· Neutral",
        "lean_avoid":  "▽ Lean Avoid",
        "avoid":       "✗ Avoid",
    }
    return labels.get(rec, rec or "")


# ─────────────────────────── HTML BUILDER ───────────────────────────

def build_html_email(hitters: list[Hitter]) -> str:
    """
    Build a full HTML email with ranked picks.

    Args:
        hitters: list of scored Hitter objects sorted by score

    Returns:
        HTML string ready to send
    """
    today = datetime.date.today().strftime("%A, %B %d, %Y")
    threshold = CONFIG.get("score_threshold", 65)
    mode = CONFIG.get("streak_mode", "conservative").upper()
    top_picks = [h for h in hitters if (h.score or 0) >= threshold]

    # Build pick rows
    pick_rows = ""
    for i, h in enumerate(top_picks, 1):
        score = h.score or 0
        color = _score_color(score)
        badge = _confidence_badge(h.confidence or "medium")

        pick_rows += f"""
        <div style="
            background: #f8f9fa;
            border-left: 4px solid {color};
            border-radius: 0 8px 8px 0;
            padding: 16px 20px;
            margin-bottom: 14px;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 8px;
            ">
                <div>
                    <span style="
                        font-size: 12px;
                        color: #999;
                        font-weight: 600;
                        margin-right: 6px;
                    ">#{i}</span>
                    <strong style="font-size: 16px; color: #111;">
                        {h.name}
                    </strong>
                    <span style="font-size: 13px; color: #666; margin-left: 6px;">
                        ({h.team or "?"})
                    </span>
                    <span style="margin-left: 8px;">{badge}</span>
                </div>
                <div style="text-align: right; flex-shrink: 0; margin-left: 16px;">
                    <span style="
                        font-size: 28px;
                        font-weight: 800;
                        color: {color};
                        line-height: 1;
                    ">{score}</span>
                    <span style="font-size: 12px; color: #aaa;">/100</span>
                </div>
            </div>

            <div style="font-size: 12px; color: #888; margin-bottom: 8px;">
                vs {h.opp or "?"} &nbsp;·&nbsp;
                {h.pitcher or "TBD"} ({h.phand or "?"}HP)
                ERA {h.era or "N/A"} &nbsp;·&nbsp;
                {h.park or "?"} &nbsp;·&nbsp;
                {(h.home_away or "?").capitalize()}
            </div>

            <div style="font-size: 12px; color: #666; margin-bottom: 6px;">
                AVG {h.avg:.3f} &nbsp;|&nbsp;
                OBP {h.obp:.3f} &nbsp;|&nbsp;
                SLG {h.slg:.3f}
                {f" &nbsp;|&nbsp; L7: {h.l7:.3f}" if h.l7 else ""}
                {f" &nbsp;|&nbsp; wOBA: {h.woba:.3f}" if h.woba else ""}
            </div>

            {f'''<div style="
                font-size: 12px;
                color: #444;
                line-height: 1.6;
                margin-top: 10px;
                padding-top: 10px;
                border-top: 1px solid #e8e8e8;
            ">{h.reasoning}</div>''' if h.reasoning else ""}

            {f'''<div style="
                font-size: 11px;
                color: {color};
                font-weight: 600;
                margin-top: 8px;
            ">Key: {h.key_factor}</div>''' if h.key_factor else ""}
        </div>"""

    # Build honorable mentions (below threshold)
    mentions = [h for h in hitters if (h.score or 0) < threshold]
    mention_rows = ""
    if mentions:
        mention_rows = """
        <div style="margin-top: 24px;">
            <h3 style="
                font-size: 13px;
                color: #888;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 12px;
            ">Below Threshold</h3>"""
        for h in mentions:
            score = h.score or 0
            color = _score_color(score)
            mention_rows += f"""
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #eee;
                font-size: 13px;
                color: #666;
            ">
                <span>{h.name} ({h.team})</span>
                <span style="color: {color}; font-weight: 600;">
                    {score}/100
                </span>
            </div>"""
        mention_rows += "</div>"

    # No picks message
    if not top_picks:
        pick_rows = """
        <div style="
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 14px;
        ">
            No hitters above threshold today.<br>
            <span style="font-size: 12px;">
                Consider lowering SCORE_THRESHOLD or adding more hitters.
            </span>
        </div>"""

    run_time = datetime.datetime.now().strftime("%I:%M %p ET")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STREAK·AI — Daily Picks</title>
</head>
<body style="
    font-family: Georgia, serif;
    background: #f0f2f5;
    margin: 0;
    padding: 20px;
">
<div style="
    max-width: 640px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
">

    <!-- Header -->
    <div style="background: #0a0c10; padding: 24px 28px;">
        <div style="
            font-family: monospace;
            font-size: 22px;
            font-weight: 700;
            color: #00e5a0;
            letter-spacing: 2px;
        ">STREAK·AI</div>
        <div style="
            font-size: 11px;
            color: #556;
            margin-top: 4px;
            font-family: sans-serif;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        ">Beat the Streak — Daily Picks Report</div>
    </div>

    <!-- Meta bar -->
    <div style="
        background: #111827;
        padding: 10px 28px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <span style="
            color: #9ca3af;
            font-size: 12px;
            font-family: sans-serif;
        ">{today}</span>
        <span style="
            color: #9ca3af;
            font-size: 11px;
            font-family: monospace;
        ">Mode: {mode} &nbsp;·&nbsp; Threshold: {threshold}+</span>
    </div>

    <!-- Body -->
    <div style="padding: 28px;">

        <!-- Summary stats -->
        <div style="
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        ">
            <div style="
                flex: 1;
                background: #f8f9fa;
                border-radius: 8px;
                padding: 14px;
                text-align: center;
            ">
                <div style="
                    font-size: 28px;
                    font-weight: 800;
                    color: #00b87a;
                ">{len(top_picks)}</div>
                <div style="
                    font-size: 11px;
                    color: #888;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-top: 4px;
                ">Top Picks</div>
            </div>
            <div style="
                flex: 1;
                background: #f8f9fa;
                border-radius: 8px;
                padding: 14px;
                text-align: center;
            ">
                <div style="
                    font-size: 28px;
                    font-weight: 800;
                    color: #378ADD;
                ">{len(hitters)}</div>
                <div style="
                    font-size: 11px;
                    color: #888;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-top: 4px;
                ">Hitters Scored</div>
            </div>
            <div style="
                flex: 1;
                background: #f8f9fa;
                border-radius: 8px;
                padding: 14px;
                text-align: center;
            ">
                <div style="
                    font-size: 28px;
                    font-weight: 800;
                    color: #f5a623;
                ">{max((h.score or 0) for h in hitters) if hitters else 0}</div>
                <div style="
                    font-size: 11px;
                    color: #888;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-top: 4px;
                ">Top Score</div>
            </div>
        </div>

        <!-- Section header -->
        <h2 style="
            font-family: sans-serif;
            font-size: 15px;
            font-weight: 700;
            color: #111;
            margin: 0 0 16px;
            padding-bottom: 10px;
            border-bottom: 2px solid #00e5a0;
        ">Today's Top Picks</h2>

        <!-- Pick cards -->
        {pick_rows}

        <!-- Honorable mentions -->
        {mention_rows}

        <!-- Footer -->
        <div style="
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #bbb;
            font-family: sans-serif;
            line-height: 1.7;
        ">
            Generated by STREAK·AI at {run_time}<br>
            Powered by Claude AI · MLB Stats API · Baseball Savant<br>
            <em>Not affiliated with ESPN. For research purposes only.</em>
        </div>

    </div>
</div>
</body>
</html>"""


# ─────────────────────────── TEXT BUILDER ───────────────────────────

def build_text_email(hitters: list[Hitter]) -> str:
    """
    Build a plain text version of the picks email.
    Used as fallback for email clients that don't render HTML.
    """
    today = datetime.date.today().strftime("%A, %B %d, %Y")
    threshold = CONFIG.get("score_threshold", 65)
    top_picks = [h for h in hitters if (h.score or 0) >= threshold]

    lines = [
        "STREAK·AI — Daily Picks Report",
        "=" * 40,
        today,
        "",
        f"Top Picks ({len(top_picks)} above threshold {threshold}):",
        "",
    ]

    for i, h in enumerate(top_picks, 1):
        lines.append(f"{i}. {h.name} ({h.team}) — {h.score}/100 [{(h.confidence or 'med').upper()}]")
        lines.append(f"   vs {h.opp} · {h.pitcher} ({h.phand}HP) ERA {h.era}")
        lines.append(f"   {h.park} · {h.home_away}")
        lines.append(f"   AVG {h.avg:.3f} | OBP {h.obp:.3f} | SLG {h.slg:.3f}")
        if h.reasoning:
            lines.append(f"   {h.reasoning}")
        if h.key_factor:
            lines.append(f"   Key: {h.key_factor}")
        lines.append("")

    if not top_picks:
        lines.append("No picks above threshold today.")
        lines.append("")

    lines += [
        "-" * 40,
        "Generated by STREAK·AI",
        "Not affiliated with ESPN.",
    ]

    return "\n".join(lines)


# ─────────────────────────── SENDING ───────────────────────────

def send_picks_email(hitters: list[Hitter]) -> bool:
    """
    Send the daily picks email via SendGrid.

    Args:
        hitters: list of scored Hitter objects

    Returns:
        True if email sent successfully, False otherwise.
    """
    if not SENDGRID_AVAILABLE:
        print("  [warn] sendgrid not installed — run: pip install sendgrid")
        return False

    api_key = CONFIG.get("sendgrid_api_key", "")
    if not api_key:
        print("  [warn] No SendGrid API key — skipping email")
        return False

    recipients = CONFIG.get("email_recipients", [])
    if not recipients:
        print("  [warn] No email recipients configured")
        return False

    sender = CONFIG.get("email_from", "")
    if not sender:
        print("  [warn] No EMAIL_FROM configured")
        return False

    today = datetime.date.today().strftime("%a %b %d")
    threshold = CONFIG.get("score_threshold", 65)
    top_picks = [h for h in hitters if (h.score or 0) >= threshold]

    # Build subject line
    if top_picks:
        top = top_picks[0]
        subject = (
            f"⚾ STREAK·AI Picks · {today} · "
            f"#{1}: {top.name} {top.score}/100"
        )
    else:
        subject = f"⚾ STREAK·AI Picks · {today} · No picks above threshold"

    html_content  = build_html_email(hitters)
    text_content  = build_text_email(hitters)

    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    success_count = 0

    for recipient in recipients:
        recipient = recipient.strip()
        if not recipient:
            continue
        try:
            message = Mail(
                from_email=Email(sender),
                to_emails=To(recipient),
                subject=subject,
            )
            message.content = [
                Content(MimeType.text, text_content),
                Content(MimeType.html, html_content),
            ]
            response = sg.client.mail.send.post(
                request_body=message.get()
            )
            if response.status_code in (200, 202):
                print(f"  [ok] Email sent to {recipient}")
                success_count += 1
            else:
                print(
                    f"  [warn] Unexpected status {response.status_code} "
                    f"for {recipient}"
                )
        except Exception as e:
            print(f"  [error] Email failed for {recipient}: {e}")

    return success_count > 0


def preview_email(hitters: list[Hitter], output_path: str = "email_preview.html"):
    """
    Write the HTML email to a file so you can preview it in a browser.
    Useful for testing without sending.
    """
    html = build_html_email(hitters)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"  [ok] Email preview saved to {output_path}")
    print(f"  Open in browser: open {output_path}")


if __name__ == "__main__":
    from src.models import Hitter

    # Build sample hitters for preview
    sample = [
        Hitter(
            name="Freddie Freeman", team="LAD", hand="L",
            avg=0.302, obp=0.390, slg=0.510,
            l7=0.340, woba=0.375, babip=0.315,
            opp="SD", pitcher="Yu Darvish", phand="R", era=3.85,
            park="Petco Park", home_away="away", batting_order=3,
            score=78, confidence="high",
            reasoning=(
                "Freeman is on a hot streak hitting .340 over his last 7 "
                "games with a clear platoon advantage against right-handed "
                "Darvish. The suppressive park factor at Petco is a concern "
                "but his elite contact quality and recent form outweigh it."
            ),
            key_factor="Hot streak + platoon advantage vs RHP",
        ),
        Hitter(
            name="Mookie Betts", team="LAD", hand="R",
            avg=0.289, obp=0.368, slg=0.498,
            l7=0.310, woba=0.362,
            opp="SD", pitcher="Yu Darvish", phand="R", era=3.85,
            park="Petco Park", home_away="away", batting_order=1,
            score=71, confidence="medium",
            reasoning=(
                "Betts is hitting solidly from the leadoff spot with good "
                "recent form. Same-hand matchup against Darvish is a slight "
                "negative but his elite contact skills and top of order "
                "plate appearances give him a high floor."
            ),
            key_factor="Elite contact rate and leadoff PAs",
        ),
        Hitter(
            name="Paul Goldschmidt", team="STL", hand="R",
            avg=0.275, obp=0.358, slg=0.468,
            l7=0.220, woba=0.350,
            opp="CHC", pitcher="Jameson Taillon", phand="R", era=4.40,
            park="Wrigley Field", home_away="away", batting_order=4,
            score=58, confidence="low",
            reasoning=(
                "Goldschmidt is in a cold stretch hitting just .220 over "
                "his last 7 games. The favorable park factor at Wrigley "
                "helps but the cold streak is a significant concern."
            ),
            key_factor="Cold streak offsets favorable park",
        ),
    ]

    print("Building email preview...\n")
    preview_email(sample)
    print("\nPlain text version:")
    print("-" * 40)
    print(build_text_email(sample))
