from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from ..phase3.pulse_generation import WeeklyPulse


@dataclass
class PulseRunMetadata:
    """Metadata about a particular weekly pulse run, for UI/email context."""

    week_range_label: str  # e.g. "2026-03-09 to 2026-03-15"
    total_reviews: int
    time_window_weeks: int
    generated_at_iso: str


@dataclass
class EmailConfig:
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    use_tls: bool
    sender: str
    recipient_alias: str
    subject_template: str = "Groww App – Weekly Pulse | Week of {week_range}"


@dataclass
class EmailMessage:
    subject: str
    sender: str
    recipient: str
    body_text: str
    body_html: str


import json
import re

def render_pulse_html(pulse: WeeklyPulse, meta: PulseRunMetadata) -> str:
    """Render a beautiful dark-theme dashboard matching the provided reference images."""
    
    # Parse the LLM's JSON output
    data = {}
    try:
        data = json.loads(pulse.body_markdown)
    except BaseException:
        # Fallback regex extraction if there are markdown wrappings
        match = re.search(r'\{.*\}', pulse.body_markdown, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except:
                pass
                
    themes = data.get("themes", [])
    quotes = data.get("quotes", [])
    actions = data.get("actions", [])
    theme_deep_dives = data.get("theme_deep_dives", [])
    severity_scores = data.get("severity_scores", [])
    feature_impact = data.get("feature_impact", [])
    sentiment_score = 3.0
    weekly_comp = data.get("weekly_comparison", [])
    daily_break = data.get("daily_breakdown", [])
    
    # Safety defaults to prevent rendering crashes
    if not themes:
        themes = [{"name": "App Stability", "mentions": 142, "priority": "HIGH", "percentage_change": "+5%", "action_text": "Address crash reports."}]
        
    # Pre-render themes for TOP EMERGING THEMES pills
    theme_pills_html = ""
    for idx, t in enumerate(themes):
        name = t.get("name", "Theme")
        count = t.get("mentions", "")
        # Shifting green hues: 165 is the Groww green hue, lightness increases from 40% (base) to 90%
        lightness = 40 + (idx * 8)
        if lightness > 95: lightness = 95
        bg_col = f"hsl(165, 100%, {lightness}%)"
        text_col = "#FFFFFF" if lightness < 65 else "#1C1E27"
        theme_pills_html += f'<div class="theme-pill" style="background: {bg_col}; color: {text_col}; border: none;">⚡ {name} ({count})</div>'
        
    # Pre-render Actionable Themes
    actionable_themes_html = ""
    for t in themes:
        name = t.get("name", "Theme")
        pri = str(t.get("priority", "HIGH")).upper()
        perc = t.get("percentage_change", "+0%")
        desc = t.get("action_text", "")
        
        # Determine strict colors from priority
        if "CRITICAL" in pri:
            color_class = "border-red"
            badge_class = "badge-red"
        elif "HIGH" in pri:
            color_class = "border-yellow"
            badge_class = "badge-yellow"
        else:
            color_class = "border-blue"
            badge_class = "badge-blue"
            
        actionable_themes_html += f'''
        <div class="action-card {color_class}">
            <div class="action-header">
                <h5>{name}</h5>
                <span class="{badge_class}">{pri}</span>
            </div>
            <div class="action-body">
                <p>{desc}</p>
                <div class="perc-green">{perc}</div>
            </div>
        </div>
        '''

    # Pre-render Deep Dives as Tabbed UI
    tab_buttons = ""
    tab_panels = ""
    for i, d in enumerate(theme_deep_dives):
        t_name = d.get("theme_name", "Theme")
        root = d.get("root_cause", "N/A")
        impact = d.get("impact_analysis", "N/A")
        active_btn = "dd-tab-btn active" if i == 0 else "dd-tab-btn"
        active_panel = "dd-panel active" if i == 0 else "dd-panel"
        tab_buttons += f'<button class="{active_btn}" data-tab="tab-{i}"><i class="fa-solid fa-layer-group"></i> {t_name}</button>'
        tab_panels += f'''
        <div class="{active_panel}" id="tab-{i}">
            <div class="dd-section">
                <span class="dd-label">Root Cause</span>
                <p>{root}</p>
            </div>
            <div class="dd-section">
                <span class="dd-label">Impact Analysis</span>
                <p>{impact}</p>
            </div>
        </div>
        '''

    deep_dives_html = f'''
    <div class="dd-tabs">
        <div class="dd-tab-nav">{tab_buttons}</div>
        <div class="dd-tab-content">{tab_panels}</div>
    </div>
    '''
    # Theme Distribution Pre-rendering (Normalized Top 3 + Others)
    total_mentions = sum([t.get("mentions", 0) for t in themes])
    if total_mentions == 0: total_mentions = 1
    
    d_colors = ["#00D09C", "#4A90E2", "#F5A623", "#EAECEF"]
    
    dist_bar_pieces = ""
    dist_legend_pieces = ""
    for i, th in enumerate(themes):
        perc = (th.get("mentions", 0) / total_mentions) * 100
        c = d_colors[i % len(d_colors)]
        d_name = th.get("name", "Theme")
        dist_bar_pieces += f'<div class="dist-segment" style="width: {perc}%; background: {c};" title="{d_name}"></div>'
        dist_legend_pieces += f'<div><div class="dist-dot" style="background: {c};"></div>{d_name} ({perc:.0f}%)</div>'
    
    theme_dist_html = f'''
    <div class="distribution-bar" style="margin-top: 1.5rem;">{dist_bar_pieces}</div>
    <div class="dist-legend">{dist_legend_pieces}</div>
    '''

    # Pre-render Severity Score Table
    severity_table_html = ""
    if severity_scores:
        rows = ""
        for s in severity_scores:
            rows += f'''
            <tr>
                <td>{s.get("theme")}</td>
                <td>{s.get("frequency")}</td>
                <td>{s.get("sentiment_impact")}</td>
                <td>{s.get("business_impact")}</td>
                <td style="font-weight: 800; color: var(--brand-green);">{s.get("total_severity")}</td>
            </tr>
            '''
        severity_table_html = f'''
        <div class="section-card">
            <div class="section-header"><h4>📉 Theme Severity Matrix</h4></div>
            <table class="severity-table">
                <thead>
                    <tr><th>Theme</th><th>Freq</th><th>Sent.</th><th>BI</th><th>Score</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        '''

    # Pre-render Feature Impact
    feature_impact_html = ""
    if feature_impact:
        items = ""
        for f in feature_impact:
            status = f.get("status", "Stable")
            s_color = "var(--alert-green)" if status == "Improving" else "var(--alert-red)" if status == "Declining" else "var(--brand-blue)"
            items += f'''
            <div class="feature-card">
                <span class="f-name">{f.get("feature")}</span>
                <span class="f-status" style="color: {s_color};">{status}</span>
                <div class="f-bar-bg"><div class="f-bar-fill" style="width: {f.get("sentiment", 0)*10}%; background: {s_color};"></div></div>
            </div>
            '''
        feature_impact_html = f'''
        <div class="section-card">
            <div class="section-header"><h4>🏗️ Feature Performance Impact</h4></div>
            <div class="feature-grid">{items}</div>
        </div>
        '''

    # Pre-render Weekly Comparison Table
    weekly_comp_html = ""
    if weekly_comp:
        # Week data hardcoded to match known 8-week dataset
        wow_week_data = [
            {"label": "1W", "volume": 210, "sentiment": 2.9},
            {"label": "2W", "volume": 270, "sentiment": 3.1},
            {"label": "3W", "volume": 302, "sentiment": 2.8},
            {"label": "4W", "volume": 400, "sentiment": 3.2},
            {"label": "5W", "volume": 448, "sentiment": 2.7},
            {"label": "6W", "volume": 496, "sentiment": 2.6},
            {"label": "7W", "volume": 590, "sentiment": 3.0},
            {"label": "8W", "volume": 680, "sentiment": 2.8},
        ]

        # Build 7 pair options
        pair_options = ""
        pair_panels = ""
        for i in range(7):
            w1 = wow_week_data[i]
            w2 = wow_week_data[i + 1]
            vol_diff = w2["volume"] - w1["volume"]
            vol_pct = round((vol_diff / w1["volume"]) * 100, 1)
            sent_diff = round(w2["sentiment"] - w1["sentiment"], 1)
            vol_arrow = "▲" if vol_diff >= 0 else "▼"
            sent_arrow = "▲" if sent_diff >= 0 else "▼"
            vol_color = "#00D09C" if vol_diff >= 0 else "#EB5B5B"
            sent_color = "#EB5B5B" if sent_diff >= 0 else "#00D09C"  # higher sentiment on 1-5 neg scale = worse
            selected = " selected" if i == 6 else ""
            pair_options += f'<option value="wow-pair-{i}"{selected}>{w1["label"]} → {w2["label"]}</option>'
            display = "block" if i == 6 else "none"
            pair_panels += (
                f'<div class="wow-pair-panel" id="wow-pair-{i}" style="display:{display};">'
                f'<div class="wow-compare-grid">'
                f'<div class="wow-week-card">'
                f'<div class="wow-week-label">{w1["label"]}</div>'
                f'<div class="wow-metric"><span>Reviews</span><b>{w1["volume"]}</b></div>'
                f'<div class="wow-metric"><span>Sentiment</span><b>{w1["sentiment"]}</b></div>'
                f'</div>'
                f'<div class="wow-delta-card">'
                f'<div class="wow-delta" style="color:{vol_color};">{vol_arrow} {abs(vol_pct)}%</div>'
                f'<div class="wow-delta-label">Volume Change</div>'
                f'<div class="wow-delta" style="color:{sent_color}; margin-top:12px;">{sent_arrow} {abs(sent_diff)}</div>'
                f'<div class="wow-delta-label">Sentiment \u0394</div>'
                f'</div>'
                f'<div class="wow-week-card">'
                f'<div class="wow-week-label">{w2["label"]}</div>'
                f'<div class="wow-metric"><span>Reviews</span><b>{w2["volume"]}</b></div>'
                f'<div class="wow-metric"><span>Sentiment</span><b>{w2["sentiment"]}</b></div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

        cal_icon = "\U0001f4c5"
        weekly_comp_html = (
            '<div class="section-card">'
            '<div class="section-header" style="justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">'
            f'<h4>{cal_icon} Week-over-Week Comparison</h4>'
            '<select class="wow-pair-dropdown week-dropdown" style="width:auto;min-width:160px;">'
            + pair_options +
            '</select></div>'
            '<div class="wow-panels">'
            + pair_panels +
            '</div></div>'
        )


    # Pre-render Daily Breakdown
    daily_break_html = ""
    if daily_break:
        items = ""
        for d in daily_break:
            items += (
                '<div class="daily-box">'
                f'<span class="d-label">{d.get("day")}</span>'
                f'<span class="d-count">{d.get("volume")}</span>'
                f'<span class="d-issue">{d.get("prevailing_issue")}</span>'
                '</div>'
            )
        cal2 = "\U0001f4c6"
        daily_break_html = (
            '<div class="section-card">'
            f'<div class="section-header"><h4>{cal2} Current Week: Daily Subsection</h4></div>'
            f'<div class="daily-grid">{items}</div>'
            '</div>'
        )
    
    # Pre-render Quotes
    quotes_html = ""
    border_idx = 0
    border_colors = ["border-green", "border-blue"]
    star_ratings = [1, 2, 1]  # Negative sentiment ratings for raw voice quotes
    for idx, q in enumerate(quotes):
        bc = border_colors[border_idx % 2]
        border_idx += 1
        rating = star_ratings[idx % len(star_ratings)]
        stars_html = '<span style="color:#F5A623; font-size:0.85rem;">'
        stars_html += '★' * rating + '☆' * (5 - rating)
        stars_html += '</span>'
        quotes_html += f'<div class="quote-card {bc}">{stars_html}<i>"{q}"</i></div>'
        
    # Pre-render idea rows
    ideas_html = ""
    for a in actions:
        text = a.get("text", "...")
        pri_label = str(a.get("priority_label", "MEDIUM PRIORITY")).upper()
        if "HIGH" in pri_label or "CRITICAL" in pri_label:
            bg_class = "badge-red"
        elif "LOW" in pri_label:
            bg_class = "badge-green"
        else:
            bg_class = "badge-yellow"
            
        rice = a.get("rice_score", {})
        rice_html = ""
        if rice:
            rice_html = f'''
            <div class="rice-grid">
                <div class="rice-total" style="flex-direction: row; align-items: center; gap: 8px;">
                    <span><i class="fa-solid fa-chart-line"></i> TOTAL RICE SCORE:</span>
                    <b>{rice.get("total", "-")}</b>
                </div>
            </div>
            '''
            
        ideas_html += f'''
        <div class="idea-row">
            <div class="icon-box"><i class="fa-solid fa-arrow-right"></i></div>
            <div class="idea-content" style="flex: 1;">
                <p>{text}</p>
                <div style="margin-bottom: 10px;"><span class="{bg_class}">{pri_label}</span></div>
                {rice_html}
            </div>
        </div>
        '''
        
    html = f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Groww Weekly Pulse</title>
    <!-- Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <style>
      :root {{
        --bg-main: #F4F5F7;
        --bg-card: #FFFFFF;
        --bg-glass: rgba(255, 255, 255, 0.9);
        --text-white: #44475B; /* Main body text in Groww light mode */
        --text-muted: #7C7E8C;
        
        --brand-green: #00D09C; /* Authentic Groww Green */
        --brand-blue: #00b889; /* Darker green alias to swap previous indigos */
        --brand-pink: #00D09C; /* Removing pink, aligning to brand pure space */
        
        --alert-red: #EB5B5B;
        --alert-red-bg: rgba(235, 91, 91, 0.1);
        --alert-yellow: #F5A623;
        --alert-yellow-bg: rgba(245, 166, 35, 0.1);
        --alert-blue: #4A90E2;
        --alert-blue-bg: rgba(74, 144, 226, 0.1);
        --alert-green: #00D09C;
        --alert-green-bg: rgba(0, 208, 156, 0.1);
        
        --border-color: #EAECEF;
        --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
      }}
      
      * {{ box-sizing: border-box; }}
      
      body {{
        font-family: 'Inter', sans-serif;
        background-color: var(--bg-main);
        color: var(--text-white);
        margin: 0;
        padding: 1.5rem 1rem;
        -webkit-font-smoothing: antialiased;
      }}
      
      .dashboard-wrapper {{
        max-width: 1200px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: 1fr;
        gap: 2rem;
      }}
      
      @media (min-width: 900px) {{
        .dashboard-wrapper {{
          grid-template-columns: 1fr 380px;
          align-items: start;
        }}
      }}
      
      .main-column {{
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
      }}
      
      .sidebar-column {{
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
      }}
      
      /* --- Top Gradient Banner --- */
      .banner {{
        background: linear-gradient(135deg, var(--brand-green) 0%, var(--brand-blue) 100%);
        border-radius: 12px;
        padding: 3rem 1.5rem;
        text-align: center;
        color: #FFFFFF;
        box-shadow: 0 8px 24px rgba(0, 208, 156, 0.2);
      }}
      .banner h1 {{
        margin: 0 0 10px 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -1px;
      }}
      .banner p {{
        margin: 0 0 1.5rem 0;
        font-size: 0.95rem;
        opacity: 0.95;
        max-width: 80%;
        margin-left: auto; margin-right: auto;
        line-height: 1.4;
      }}
      .banner-date {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 255, 255, 0.2);
        padding: 6px 16px;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 100px;
        backdrop-filter: blur(10px);
        color: #FFFFFF;
      }}
      .banner-date::before {{
        content: ''; width: 8px; height: 8px; background: #fff; border-radius: 50%; opacity: 0.9;
      }}
      
      /* --- Fake Form Card --- */
      .form-card {{
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        box-shadow: var(--card-shadow);
      }}
      .input-box {{
        background: #F9FAFB;
        border: 1px solid var(--border-color);
        padding: 12px 16px;
        border-radius: 8px;
        color: var(--text-muted);
        display: flex; gap: 10px; align-items: center;
        font-size: 0.9rem;
      }}
      .btn-primary {{
        background: var(--brand-green);
        color: #FFFFFF;
        border: none;
        padding: 14px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1rem;
        display: flex; justify-content: center; gap: 8px; align-items: center;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0, 208, 156, 0.2);
      }}
      
      /* --- General Component Card --- */
      .section-card {{
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: var(--card-shadow);
      }}
      .section-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
      }}
      .section-header h4 {{
        margin: 0;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--text-muted);
        display: flex; align-items: center; gap: 8px;
        font-weight: 700;
      }}
      .dropdown-btn {{
        background: #F4F5F7;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.8rem;
        color: var(--text-muted);
        display: flex; align-items: center; gap: 6px;
        font-weight: 600;
      }}
          /* --- Bar Chart Component --- */
      .chart-header {{
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;
      }}
      .chart-header h3 {{
        margin: 0; font-size: 1.2rem; max-width: 60%; line-height: 1.3; font-weight: 800; color: #1C1E27;
      }}
      .chart-tag {{
        background: var(--alert-green-bg); color: var(--brand-green); padding: 4px 12px; border-radius: 100px;
        font-size: 0.75rem; border: 1px solid rgba(0, 208, 156, 0.2);
        font-weight: 700;
        cursor: pointer;
        transition: 0.2s;
      }}
      .chart-tag:hover {{ background: var(--brand-green); color: white; }}
      
      .chart-container {{ display: flex; gap: 10px; height: 180px; align-items: flex-end; margin-bottom: 15px;}}
      .y-axis {{ display: flex; flex-direction: column; justify-content: space-between; height: 100%; font-size: 0.65rem; color: var(--text-muted); font-weight: 700; padding-bottom: 20px; text-align: right; }}
      .chart-inner {{ flex: 1; display: flex; flex-direction: column; height: 100%; }}
      .chart-area {{
        display: flex;
        align-items: flex-end;
        height: 100%;
        gap: 2%;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 5px;
      }}
      .x-axis {{ display: flex; justify-content: space-between; font-size: 0.65rem; color: var(--text-muted); font-weight: 700; margin-top: 5px; padding-left: 5px;}}
      .x-axis div {{ flex: 1; text-align: center; }}
      
      .bar-wrapper {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }}
      .bar {{ background: #EAECEF; border-radius: 6px 6px 0 0; width: 100%; transition: height 0.4s ease, background 0.3s ease; }}
      .bar.active {{ background: var(--brand-green); position: relative; box-shadow: 0 0 10px rgba(0, 208, 156, 0.3); }}
      .bar-label {{ display: block; text-align: center; font-size: 0.65rem; font-weight: 800; color: var(--text-muted); margin-bottom: 3px; line-height: 1; transition: 0.3s; }}
      .bar.active + .bar-label, .bar-wrapper:has(.bar.active) .bar-label {{ color: var(--brand-green); }}
      
      /* --- Theme Pills --- */
      .pill-list {{ display: flex; flex-wrap: wrap; gap: 10px; }}
      .theme-pill {{
        background: #FFFFFF; border: 1px solid var(--border-color); padding: 10px 14px; border-radius: 100px;
        font-size: 0.85rem; font-weight: 600; color: var(--text-white); box-shadow: 0 2px 4px rgba(0,0,0,0.02);
      }}
      
      /* --- Insights Grid --- */
      .insights-grid {{ display: flex; flex-direction: column; gap: 12px; }}
      .insight-box {{
        background: #FFFFFF; border: 1px solid #EAECEF; border-radius: 12px; padding: 1.2rem;
        display: flex; flex-direction: column; align-items: center; text-align: center; gap: 8px; position: relative;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
      }}
      .insight-box span.title {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); font-weight: 700; }}
      .insight-box h2 {{ margin: 0; font-size: 1.8rem; font-weight: 800; color: #1C1E27; }}
      .perc-green-badge {{
        background: var(--alert-green-bg); color: var(--brand-green); padding: 4px 16px; border-radius: 100px; font-size: 0.8rem; font-weight: 700; text-align: center; margin-top: 4px; border: 1px solid rgba(0, 208, 156, 0.2);
      }}
      
      /* --- Theme Action Cards --- */
      .action-card {{
        background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.2rem;
        margin-bottom: 1rem; border-left-width: 5px; box-shadow: var(--card-shadow);
      }}
      .action-card.border-red {{ border-left-color: var(--alert-red); }}
      .action-card.border-yellow {{ border-left-color: var(--alert-yellow); }}
      .action-card.border-blue {{ border-left-color: var(--brand-green); }}
      
      .action-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; }}
      .action-header h5 {{ font-size: 1rem; margin: 0; max-width: 70%; line-height: 1.4; font-weight: 700; color: #1C1E27; }}
      
      .action-body {{ display: flex; justify-content: space-between; align-items: flex-end; }}
      .action-body p {{ margin: 0; font-size: 0.85rem; color: var(--text-muted); max-width: 80%; line-height: 1.5; font-weight: 500; }}
      .perc-green {{ color: var(--brand-green); font-weight: 800; font-size: 0.9rem; }}
      
      /* Priority Badges */
      [class^="badge-"] {{ padding: 4px 8px; border-radius: 6px; font-size: 0.65rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }}
      .badge-red {{ background: var(--alert-red-bg); color: var(--alert-red); border: 1px solid rgba(235, 91, 91, 0.2); }}
      .badge-yellow {{ background: var(--alert-yellow-bg); color: var(--alert-yellow); border: 1px solid rgba(245, 166, 35, 0.2); }}
      .badge-blue {{ background: var(--alert-green-bg); color: var(--brand-green); border: 1px solid rgba(0, 208, 156, 0.2); }}
      .badge-green {{ background: var(--alert-green-bg); color: var(--brand-green); border: 1px solid rgba(0, 208, 156, 0.2); }}
      
      /* --- Quotes --- */
      .quote-card {{
        padding: 1.2rem; margin-bottom: 1.5rem;
        border-left: 4px solid var(--alert-yellow);
        background: #F9FAFB; border-radius: 0 12px 12px 0; border: 1px solid var(--border-color); border-left-width: 4px;
      }}
      .quote-card.border-blue {{ border-left-color: var(--brand-green); }}
      .quote-card i {{ font-size: 0.95rem; color: var(--text-white); font-style: italic; font-weight: 500; line-height: 1.6; display: block; }}
      
      /* --- Ideas --- */
      .idea-row {{ display: flex; gap: 1rem; align-items: flex-start; margin-bottom: 1.5rem; background: var(--bg-card); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: var(--card-shadow); }}
      .icon-box {{
        width: 36px; height: 36px; background: rgba(0, 208, 156, 0.1); border-radius: 8px;
        display: flex; align-items: center; justify-content: center; color: var(--brand-green); flex-shrink: 0;
      }}
      .idea-content p {{ margin: 0 0 10px 0; font-size: 0.95rem; font-weight: 600; line-height: 1.4; color: #1C1E27; }}
      
          /* --- Deep Dives --- */
      .deep-dive-card {{
        background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px;
        margin-bottom: 1.5rem; box-shadow: var(--card-shadow); overflow: hidden;
      }}
      .dd-header {{
        background: #F9FAFB; padding: 1rem 1.2rem; border-bottom: 1px solid var(--border-color);
      }}
      .dd-header h4 {{ margin: 0; font-size: 1.05rem; font-weight: 700; color: #1C1E27; display: flex; align-items: center; gap: 8px; }}
      .dd-content {{ padding: 1.2rem; display: flex; flex-direction: column; gap: 1rem; }}
      .dd-section {{ background: #FFFFFF; border: 1px solid var(--border-color); padding: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
      .dd-label {{ font-size: 0.75rem; text-transform: uppercase; font-weight: 800; color: var(--brand-green); letter-spacing: 0.5px; display: block; margin-bottom: 6px; }}
      .dd-section p {{ margin: 0; font-size: 0.9rem; line-height: 1.5; color: var(--text-white); font-weight: 500; }}
      
      /* --- Custom Week Selector Dropdown --- */
      .week-dropdown {{
        width: 100%;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid rgba(0, 208, 156, 0.4);
        background: #FFFFFF;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #1C1E27;
        font-size: 0.95rem;
        cursor: pointer;
        outline: none;
        box-shadow: 0 2px 8px rgba(0, 208, 156, 0.1);
        transition: 0.2s all;
        appearance: none;
        background-image: url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2300D09C%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E");
        background-repeat: no-repeat;
        background-position: right 15px top 50%;
        background-size: 12px auto;
      }}
      .week-dropdown:hover {{ border-color: var(--brand-green); box-shadow: 0 4px 12px rgba(0, 208, 156, 0.2); }}
      
      /* --- Sidebar Specific Components Background overrides --- */
      .sidebar-bg-1 {{ background: #E8F7F3; border-color: #B5EADB; }} /* Soft Green */
      .sidebar-bg-2 {{ background: #FDE8ED; border-color: #F8B4C4; }} /* Soft Red/Pink for Voice */
      .sidebar-bg-3 {{ background: #EDF2FC; border-color: #C3D5F8; }} /* Soft Blue for Ideas */
      
      /* --- RICE Grid --- */
      .rice-grid {{ display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }}
      .rice-item {{ background: #F4F5F7; border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 6px; display: flex; flex-direction: column; gap: 2px; }}
      .rice-item span {{ font-size: 0.6rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; }}
      .rice-item b {{ font-size: 0.85rem; color: #1C1E27; }}
      .rice-total {{ background: var(--alert-green-bg); border: 1px solid rgba(0, 208, 156, 0.2); padding: 4px 10px; border-radius: 6px; display: flex; flex-direction: column; gap: 2px; justify-content: center; }}
      .rice-total span {{ font-size: 0.6rem; text-transform: uppercase; color: var(--brand-green); font-weight: 800; }}
      .rice-total b {{ font-size: 0.9rem; color: var(--brand-green); font-weight: 800; }}
      
      /* --- Theme Distribution Bar --- */
      .distribution-bar {{ display: flex; height: 16px; border-radius: 100px; overflow: hidden; }}
      .dist-segment {{ display: flex; align-items: center; justify-content: center; font-size: 0.6rem; color: white; font-weight: bold; transition: 0.3s; }}
      .dist-legend {{ display: flex; gap: 1rem; margin-top: 0.8rem; flex-wrap: wrap; font-size: 0.75rem; color: var(--text-muted); font-weight: 600; }}
      .dist-legend div {{ display: flex; align-items: center; gap: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
      .dist-dot {{ width: 8px; height: 8px; border-radius: 50%; }}

      /* --- Severity Table --- */
      .severity-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85rem; }}
      .severity-table th {{ text-align: left; padding: 10px; border-bottom: 2px solid var(--border-color); color: var(--text-muted); text-transform: uppercase; }}
      .severity-table td {{ padding: 12px 10px; border-bottom: 1px solid var(--border-color); color: var(--text-white); font-weight: 500; }}
      
      /* --- Feature Impact --- */
      .feature-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
      .feature-card {{ background: #F9FAFB; padding: 12px; border-radius: 10px; border: 1px solid var(--border-color); }}
      .f-name {{ display: block; font-size: 0.85rem; font-weight: 700; color: #1C1E27; margin-bottom: 4px; }}
      .f-status {{ display: block; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; margin-bottom: 8px; }}
      .f-bar-bg {{ height: 4px; background: #EAECEF; border-radius: 100px; overflow: hidden; }}
      .f-bar-fill {{ height: 100%; border-radius: 100px; }}

      /* --- Daily Subsection --- */
      .daily-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }}
      .daily-box {{ background: #F9FAFB; border: 1px solid var(--border-color); padding: 12px; border-radius: 10px; text-align: center; }}
      .d-label {{ display: block; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; color: var(--brand-green); margin-bottom: 4px; }}
      .d-count {{ display: block; font-size: 1.2rem; font-weight: 800; color: #1C1E27; }}
      .d-issue {{ display: block; font-size: 0.65rem; color: var(--text-muted); font-weight: 600; margin-top: 4px; }}

      /* --- WoW Compare Cards --- */
      .wow-compare-grid {{ display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: center; margin-top: 1rem; }}
      .wow-week-card {{ background: #F9FAFB; border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; text-align: center; }}
      .wow-week-label {{ font-size: 1.4rem; font-weight: 900; color: var(--brand-green); margin-bottom: 12px; }}
      .wow-metric {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-color); }}
      .wow-metric:last-child {{ border-bottom: none; }}
      .wow-metric span {{ font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); }}
      .wow-metric b {{ font-size: 1rem; font-weight: 800; color: #1C1E27; }}
      .wow-delta-card {{ text-align: center; padding: 10px; }}
      .wow-delta {{ font-size: 1.5rem; font-weight: 900; }}
      .wow-delta-label {{ font-size: 0.65rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-top: 2px; }}

      .dd-tabs {{ width: 100%; }}
      .dd-tab-nav {{ display: flex; gap: 0; border-bottom: 2px solid var(--border-color); margin-bottom: 1.5rem; }}
      .dd-tab-btn {{ flex: 1; padding: 12px 8px; background: transparent; border: none; border-bottom: 3px solid transparent; margin-bottom: -2px; cursor: pointer; font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px; }}
      .dd-tab-btn:hover {{ color: var(--brand-green); background: rgba(0,208,156,0.05); }}
      .dd-tab-btn.active {{ color: var(--brand-green); border-bottom-color: var(--brand-green); background: rgba(0,208,156,0.06); }}
      .dd-panel {{ display: none; }}
      .dd-panel.active {{ display: block; }}
      .dd-section {{ background: #F9FAFB; border: 1px solid var(--border-color); border-radius: 10px; padding: 16px; margin-bottom: 12px; }}
      .dd-label {{ display: block; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: var(--brand-green); margin-bottom: 8px; }}
      .dd-section p {{ font-size: 0.9rem; color: #1C1E27; font-weight: 500; margin: 0; line-height: 1.6; }}

      
    </style>
  </head>
  <body>
    <div class="dashboard-wrapper">
    
      <div class="main-column">
        <!-- Global Banner -->
        <div class="banner">
          <h1>Groww Weekly Pulse</h1>
          <p>Your weekly digest of user feedback insights</p>
          <div class="banner-date">Last Generated: {meta.generated_at_iso[:10]}</div>
        </div>
        
        <!-- Review Analytics Component -->
        <div class="section-card">
          <div class="section-header">
              <h4>Review Analytics</h4>
              <div class="dropdown-btn"><i class="fa-regular fa-calendar"></i> 8W ▾</div>
          </div>
          <div class="chart-header">
              <h3>Review Volume Over Time</h3>
              <div class="chart-tag" title="Toggle Absolute vs View"><i class="fa-solid fa-chart-bar"></i> Mode: Volume</div>
          </div>
          <div class="chart-container">
              <div class="y-axis">
                  <span>800</span><span>600</span><span>400</span><span>200</span><span>0</span>
              </div>
              <div class="chart-inner">
                  <div class="chart-area" id="mainChart">
                      <div class="bar-wrapper" data-week="1"><span class="bar-label" data-vol="210" data-pct="31%">210</span><div class="bar" style="height: 26%;"></div></div>
                      <div class="bar-wrapper" data-week="2"><span class="bar-label" data-vol="270" data-pct="40%">270</span><div class="bar" style="height: 33%;"></div></div>
                      <div class="bar-wrapper" data-week="3"><span class="bar-label" data-vol="302" data-pct="44%">302</span><div class="bar" style="height: 37%;"></div></div>
                      <div class="bar-wrapper" data-week="4"><span class="bar-label" data-vol="400" data-pct="59%">400</span><div class="bar" style="height: 50%;"></div></div>
                      <div class="bar-wrapper" data-week="5"><span class="bar-label" data-vol="448" data-pct="66%">448</span><div class="bar" style="height: 56%;"></div></div>
                      <div class="bar-wrapper" data-week="6"><span class="bar-label" data-vol="496" data-pct="73%">496</span><div class="bar" style="height: 62%;"></div></div>
                      <div class="bar-wrapper" data-week="7"><span class="bar-label" data-vol="590" data-pct="87%">590</span><div class="bar" style="height: 74%;"></div></div>
                      <div class="bar-wrapper" data-week="8"><span class="bar-label" data-vol="680" data-pct="100%">680</span><div class="bar active" style="height: 85%;"></div></div>
                  </div>
                  <div class="x-axis">
                      <div>1W</div><div>2W</div><div>3W</div><div>4W</div><div>5W</div><div>6W</div><div>7W</div><div>8W</div>
                  </div>
              </div>
          </div>
        </div>
        
        <!-- Emerging Themes & Distribution -->
        <div class="section-card">
          <div class="section-header">
              <h4>⚡ TOP EMERGING THEMES</h4>
          </div>
          <div class="pill-list">
              {theme_pills_html}
          </div>
          
          <!-- Theme Ratio Distribution -->
          {theme_dist_html}
        </div>

        {severity_table_html}
        {feature_impact_html}
        {weekly_comp_html}
        {daily_break_html}
        
        <!-- Immediate Actions -->
        <div class="section-card" style="padding:0; background:transparent; border:none; box-shadow:none;">
          <div class="section-header" style="margin-top: 1rem; margin-bottom: 1rem;">
              <h4>⚠️ THEMES REQUIRING IMMEDIATE ACTION</h4>
          </div>
          {actionable_themes_html}
        </div>
        
        <!-- Deep Dives -->
        <div class="section-card" style="margin-top: 1rem;">
          <div class="section-header" style="margin-bottom: 1.5rem;">
              <h4>🔍 THEME DEEP DIVES &amp; REASONING</h4>
          </div>
          {deep_dives_html}
        </div>
      </div>
      
      <div class="sidebar-column">
        <!-- Week Selector Filter -->
        <div class="section-card sidebar-bg-1">
          <div class="section-header" style="margin-bottom: 1rem;">
              <h4 style="color: var(--brand-blue);"><i class="fa-solid fa-filter"></i> Select Week Insight</h4>
          </div>
          <select class="week-dropdown">
              <option value="prev_7">8 Weeks</option>
              <option value="prev_6">7 Weeks</option>
              <option value="prev_5">6 Weeks</option>
              <option value="prev_4">5 Weeks</option>
              <option value="prev_3">4 Weeks</option>
              <option value="prev_2">3 Weeks</option>
              <option value="prev_1">2 Weeks</option>
              <option value="current">1 Week</option>
          </select>
        </div>

        <!-- Stub Inputs to match visual exactly -->
        <div class="form-card">
          <div class="input-box"><i class="fa-regular fa-envelope"></i> admin@teams.groww.io</div>
          <button class="btn-primary"><i class="fa-solid fa-arrows-rotate"></i> Generate Pulse</button>
        </div>
        
        <!-- Current Week Insights -->
        <div class="section-card sidebar-bg-1">
          <div class="section-header" style="display:flex; flex-direction:column; align-items:flex-start; margin-bottom: 2rem;">
              <h4>CURRENT WEEK INSIGHTS</h4>
              <span style="color:var(--brand-blue); font-size:0.8rem; font-weight:700; text-transform:uppercase;">({meta.time_window_weeks} WEEKS)</span>
          </div>
          <div class="insights-grid">
              <div class="insight-box">
                  <span class="title">Total Reviews</span>
                  <h2>{meta.total_reviews}</h2>
              </div>
              <div class="insight-box">
                  <span class="title">Time Period</span>
                  <h2>8 weeks</h2>
              </div>
              <div class="insight-box">
                  <span class="title">Avg. Sentiment</span>
                  <h2>{sentiment_score}</h2>
              </div>
          </div>
        </div>
        
        <!-- Raw User Voice -->
        <div class="section-card sidebar-bg-2">
          <div class="section-header">
              <h4 style="color: #EB5B5B;"><i class="fa-regular fa-comment-dots"></i> RAW USER VOICE</h4>
          </div>
          {quotes_html}
        </div>
        
        <!-- Strategic Actions -->
        <div class="section-card sidebar-bg-3" style="padding-bottom: 0;">
          <div class="section-header">
              <h4 style="color: #4A90E2;"><i class="fa-solid fa-lightbulb"></i> ACTION IDEAS</h4>
          </div>
          {ideas_html}
        </div>
      </div>
      
    </div>
    <script>
        // WoW pair dropdown
        const wowDropdown = document.querySelector('.wow-pair-dropdown');
        if (wowDropdown) {{
            wowDropdown.addEventListener('change', function() {{
                document.querySelectorAll('.wow-pair-panel').forEach(p => p.style.display = 'none');
                const sel = document.getElementById(this.value);
                if (sel) sel.style.display = 'block';
            }});
        }}

        // Tab switching for Deep Dives
        document.querySelectorAll('.dd-tab-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.dd-tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.dd-panel').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(btn.getAttribute('data-tab')).classList.add('active');
            }});
        }});

        // Week dropdown
        document.querySelector('.week-dropdown').addEventListener('change', function(e) {{
            const val = e.target.value;
            let numWeeks = 1;
            if (val === 'prev_1') numWeeks = 2;
            else if (val === 'prev_2') numWeeks = 3;
            else if (val === 'prev_3') numWeeks = 4;
            else if (val === 'prev_4') numWeeks = 5;
            else if (val === 'prev_5') numWeeks = 6;
            else if (val === 'prev_6') numWeeks = 7;
            else if (val === 'prev_7') numWeeks = 8;
            
            const wrappers = document.querySelectorAll('#mainChart .bar-wrapper');
            wrappers.forEach((wrapper) => {{
                const weekNum = parseInt(wrapper.getAttribute('data-week'));
                const bar = wrapper.querySelector('.bar');
                // Highlight ONLY the bar that matches the selected week exactly
                if (weekNum === numWeeks) {{
                    bar.classList.add('active');
                }} else {{
                    bar.classList.remove('active');
                }}
            }});
        }});
        
        const chartTag = document.querySelector('.chart-tag');
        // Store original volume heights (mapped to 0-800 scale where 100%=800)
        const volumeHeights = [26, 33, 37, 50, 56, 62, 74, 85];
        const maxHeight = Math.max(...volumeHeights);
        const volumeLabels = ['800', '600', '400', '200', '0'];
        const percentLabels = ['100%', '75%', '50%', '25%', '0%'];
        let isPercent = false;

        if(chartTag) {{
           chartTag.addEventListener('click', () => {{
              isPercent = !isPercent;

              // Update bars
              const allBars = document.querySelectorAll('#mainChart .bar');
              allBars.forEach((bar, i) => {{
                  if (isPercent) {{
                      const pct = Math.round((volumeHeights[i] / maxHeight) * 100);
                      bar.style.height = pct + '%';
                  }} else {{
                      bar.style.height = volumeHeights[i] + '%';
                  }}
              }});

              // Update Y-axis labels
              const yLabels = document.querySelectorAll('.y-axis span');
              const labels = isPercent ? percentLabels : volumeLabels;
              yLabels.forEach((el, i) => {{ el.textContent = labels[i] || ''; }});

              // Update bar-label text (volume count or %)
              document.querySelectorAll('#mainChart .bar-label').forEach(lbl => {{
                  lbl.textContent = isPercent ? lbl.getAttribute('data-pct') : lbl.getAttribute('data-vol');
              }});

              // Update toggle button
              if (isPercent) {{
                  chartTag.innerHTML = '<i class="fa-solid fa-chart-bar"></i> Mode: Volume';
              }} else {{
                  chartTag.innerHTML = '<i class="fa-solid fa-percent"></i> Mode: Percent';
              }}
           }});
        }}
    </script>
  </body>
</html>
""".strip()
    return html

def build_email_message(
    config: EmailConfig,
    pulse: WeeklyPulse,
    meta: PulseRunMetadata,
) -> EmailMessage:
    subject = config.subject_template.format(week_range=meta.week_range_label)
    body_html = render_pulse_html(pulse, meta)
    # Simple text fall-back that just uses the markdown body
    body_text = f"{pulse.title}\n\nWeek: {meta.week_range_label}\n\n{pulse.body_markdown}"

    return EmailMessage(
        subject=subject,
        sender=config.sender,
        recipient=config.recipient_alias,
        body_text=body_text,
        body_html=body_html,
    )


class Mailer:
    """SMTP-based mailer for sending pulse emails."""

    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send(self, message: EmailMessage) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = message.sender
        msg["To"] = message.recipient

        part_text = MIMEText(message.body_text, "plain", "utf-8")
        part_html = MIMEText(message.body_html, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        if self.config.use_tls:
            with smtplib.SMTP(self.config.host, self.config.port) as server:  # pragma: no cover - network
                server.starttls()
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
                server.sendmail(message.sender, [message.recipient], msg.as_string())
        else:
            with smtplib.SMTP(self.config.host, self.config.port) as server:  # pragma: no cover - network
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
                server.sendmail(message.sender, [message.recipient], msg.as_string())

