"""Send screenshot emails via SMTP."""

import os
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, timezone

from .config import get_email_config, list_urls
from .balances import fetch_all_balances


def _build_balance_html(wallets: list[dict], timestamp: str) -> str:
    """Build an inline-styled HTML balance report for email."""
    html = """
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e1e4e8;padding:24px;">
      <div style="text-align:center;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #30363d;">
        <h1 style="font-size:1.3rem;margin:0 0 6px 0;color:#e1e4e8;">Portfolio Balance Report</h1>
        <div style="color:#8b949e;font-size:0.85rem;">""" + timestamp + """</div>
      </div>
    """

    for w in wallets:
        type_style = "background:#2a1f4e;color:#bc8cff;" if w.get("type") == "solana" else "background:#1c3a5f;color:#58a6ff;"
        type_name = "Solana" if w.get("type") == "solana" else "EVM"
        total = w.get("total_usd", 0)

        html += f"""
      <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;padding-bottom:12px;border-bottom:1px solid #21262d;">
          <div>
            <span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.7rem;font-weight:600;text-transform:uppercase;{type_style}">{type_name}</span>
            <div style="font-weight:600;font-size:1rem;margin-top:4px;">{w.get('label', '')}</div>
            <div style="font-family:monospace;font-size:0.75rem;color:#8b949e;margin-top:4px;">{w.get('address', '')}</div>
          </div>
          <div style="font-size:1.5rem;font-weight:700;color:#3fb950;">${total:.2f}</div>
        </div>
        """

        if w.get("error"):
            html += f'<div style="color:#f85149;padding:8px 0;">Error: {w["error"]}</div>'
        elif w.get("type") == "solana":
            # Holdings section header
            holdings_usd = w.get("sol_usd", 0) + sum(t.get("usd", 0) for t in w.get("tokens", []))
            html += f"""
        <div style="display:flex;justify-content:space-between;padding:8px 0;margin-top:4px;">
          <div style="font-weight:600;font-size:0.9rem;">Holdings</div>
          <div style="font-weight:600;font-size:0.9rem;">${holdings_usd:.2f}</div>
        </div>
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #30363d;color:#8b949e;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;">
          <div style="flex:2;">Asset</div>
          <div style="flex:1.5;text-align:right;">Balance</div>
          <div style="flex:1;text-align:right;">Price</div>
          <div style="flex:1;text-align:right;">Value</div>
        </div>"""

            # SOL row (always shown)
            if w.get("sol_balance") is not None:
                html += f"""
        <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #21262d;align-items:center;">
          <div style="flex:2;"><div style="font-weight:600;font-size:0.9rem;">SOL</div><div style="color:#8b949e;font-size:0.75rem;">Solana</div></div>
          <div style="flex:1.5;text-align:right;color:#c9d1d9;font-size:0.9rem;">{w['sol_balance']:.4f}</div>
          <div style="flex:1;text-align:right;color:#8b949e;font-size:0.85rem;">${w.get('sol_price', 0):.2f}</div>
          <div style="flex:1;text-align:right;font-weight:600;font-size:0.9rem;">${w.get('sol_usd', 0):.2f}</div>
        </div>"""

            # Holdings token rows (>= $1)
            for t in w.get("tokens", []):
                price_str = f"${t['price']:.4f}" if t.get("price") else "--"
                html += f"""
        <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #21262d;align-items:center;">
          <div style="flex:2;"><div style="font-weight:600;font-size:0.9rem;">{t['symbol']}</div><div style="color:#8b949e;font-size:0.75rem;">{t.get('name', '')}</div></div>
          <div style="flex:1.5;text-align:right;color:#c9d1d9;font-size:0.9rem;">{t['amount']:.4f}</div>
          <div style="flex:1;text-align:right;color:#8b949e;font-size:0.85rem;">{price_str}</div>
          <div style="flex:1;text-align:right;font-weight:600;font-size:0.9rem;">${t.get('usd', 0):.2f}</div>
        </div>"""

            # Other section (< $1)
            other = w.get("other_tokens", [])
            if other:
                other_usd = sum(t.get("usd", 0) for t in other)
                html += f"""
        <div style="display:flex;justify-content:space-between;padding:8px 0;margin-top:16px;border-top:1px solid #30363d;">
          <div style="font-weight:600;font-size:0.9rem;">Other</div>
          <div style="font-weight:600;font-size:0.9rem;">${other_usd:.2f}</div>
        </div>
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #30363d;color:#8b949e;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;">
          <div style="flex:2;">Asset</div>
          <div style="flex:1.5;text-align:right;">Balance</div>
          <div style="flex:1;text-align:right;">Price</div>
          <div style="flex:1;text-align:right;">Value</div>
        </div>"""
                for t in other:
                    price_str = f"${t['price']:.4f}" if t.get("price") else "--"
                    html += f"""
        <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #21262d;align-items:center;">
          <div style="flex:2;"><div style="font-weight:600;font-size:0.9rem;">{t['symbol']}</div><div style="color:#8b949e;font-size:0.75rem;">{t.get('name', '')}</div></div>
          <div style="flex:1.5;text-align:right;color:#c9d1d9;font-size:0.9rem;">{t['amount']:.4f}</div>
          <div style="flex:1;text-align:right;color:#8b949e;font-size:0.85rem;">{price_str}</div>
          <div style="flex:1;text-align:right;font-weight:600;font-size:0.9rem;">${t.get('usd', 0):.2f}</div>
        </div>"""

        elif w.get("type") == "evm":
            html += """
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #30363d;color:#8b949e;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;">
          <div style="flex:2;">Chain</div>
          <div style="flex:1;text-align:right;">Value</div>
        </div>"""
            for c in w.get("chains", []):
                html += f"""
        <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #21262d;">
          <div style="flex:2;font-weight:500;">{c['name']}</div>
          <div style="flex:1;text-align:right;font-weight:600;">${c.get('usd', 0):.2f}</div>
        </div>"""

        html += "</div>"

    html += "</div>"
    return html


def send_screenshots_email(
    screenshot_results: list[dict],
    config_path: str | None = None,
    include_balances: bool = True,
) -> None:
    """Email screenshots as attachments with balance report in body."""
    email_cfg = get_email_config(config_path)

    recipient = email_cfg.get("recipient", "")
    smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = email_cfg.get("smtp_port", 587)
    smtp_user = email_cfg.get("smtp_user", "")
    smtp_password = email_cfg.get("smtp_password", "")

    if not recipient:
        raise ValueError("No recipient email configured. Set it in the Settings page.")
    if not smtp_user or not smtp_password:
        raise ValueError("SMTP credentials not configured. Set them in the Settings page.")

    now = datetime.now(timezone.utc)
    month_str = now.strftime("%B %Y")
    timestamp = now.strftime("%B %d, %Y at %H:%M UTC")

    successful = [r for r in screenshot_results if r.get("path")]
    failed = [r for r in screenshot_results if r.get("error")]

    # Build plain text summary
    text_lines = [
        f"Monthly portfolio report - {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Total URLs: {len(screenshot_results)}",
        f"Screenshots captured: {len(successful)}",
    ]
    if failed:
        text_lines.append(f"Failed: {len(failed)}")
        for f_item in failed:
            text_lines.append(f"  - {f_item['label']}: {f_item['error']}")
    text_lines.append("")
    text_lines.append("See attached screenshots and the HTML version for balance details.")

    # Build HTML body
    html_body = f"""<html><body style="background:#0f1117;margin:0;padding:0;">
    <div style="max-width:700px;margin:0 auto;padding:20px;">
      <h2 style="color:#e1e4e8;font-family:-apple-system,sans-serif;text-align:center;">Portfolio Snapshots - {month_str}</h2>
      <p style="color:#8b949e;font-family:-apple-system,sans-serif;text-align:center;font-size:0.85rem;">
        {len(successful)} screenshot(s) captured{f', {len(failed)} failed' if failed else ''}
      </p>
    """

    # Include balance report
    if include_balances:
        try:
            urls = list_urls(config_path)
            wallets = fetch_all_balances(urls)
            html_body += _build_balance_html(wallets, timestamp)
        except Exception as e:
            html_body += f'<p style="color:#f85149;font-family:sans-serif;">Could not load balances: {e}</p>'

    html_body += """
      <hr style="border:none;border-top:1px solid #30363d;margin:24px 0;">
      <p style="color:#8b949e;font-family:-apple-system,sans-serif;font-size:0.8rem;text-align:center;">
        Screenshots are attached as PNG files.
      </p>
    </div></body></html>"""

    # Build MIME message
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Portfolio Report - {month_str}"
    msg["From"] = smtp_user
    msg["To"] = recipient

    # HTML + text alternative
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("\n".join(text_lines), "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    # Attach screenshots
    for result in successful:
        filepath = result["path"]
        if filepath and os.path.exists(filepath):
            filename = result.get("filename") or os.path.basename(filepath)
            with open(filepath, "rb") as f:
                img_data = f.read()
            img = MIMEImage(img_data, _subtype="png")
            img.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(img)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)

    print(f"Email sent to {recipient} with {len(successful)} screenshot(s) + balance report.")
