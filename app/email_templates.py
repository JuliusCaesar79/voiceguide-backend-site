# app/email_templates.py
from __future__ import annotations
from typing import Iterable


def _money(v) -> str:
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


# =========================================================
# RECEIPT — SINGLE LICENSE
# =========================================================
def render_receipt_html_single(
    *,
    order_id: int,
    total_amount,
    license_code: str,
    max_guests: int,
) -> str:
    total = _money(total_amount)

    return f"""\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VoiceGuideApp — Receipt</title>
</head>
<body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;color:#111;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:#ffffff;border-radius:14px;padding:22px;border:1px solid #eceef3;">
      
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div style="font-size:18px;font-weight:700;">VoiceGuideApp</div>
        <div style="font-size:12px;color:#666;">Purchase receipt</div>
      </div>

      <hr style="border:none;border-top:1px solid #eceef3;margin:16px 0;">

      <h1 style="font-size:18px;margin:0 0 8px 0;">Purchase completed ✅</h1>

      <p style="margin:0 0 16px 0;color:#444;font-size:14px;">
        Thank you for your purchase on VoiceGuideApp.
        Below you will find your order details and license code.
      </p>

      <div style="background:#f9fafc;border:1px solid #eceef3;border-radius:12px;padding:14px;">
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px;">
          <span style="color:#666;">Order</span>
          <strong>#{order_id}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px;">
          <span style="color:#666;">Total</span>
          <strong>{total} €</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px;">
          <span style="color:#666;">License</span>
          <strong>{license_code}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:14px;">
          <span style="color:#666;">Max guests</span>
          <strong>{max_guests}</strong>
        </div>
      </div>

      <h2 style="font-size:15px;margin:18px 0 8px 0;">Quick instructions</h2>
      <ol style="margin:0 0 14px 18px;font-size:14px;line-height:1.5;">
        <li>Open the VoiceGuideApp</li>
        <li>Enter your license code</li>
        <li>Start the tour and share the PIN with your guests</li>
      </ol>

      <p style="margin:0;color:#666;font-size:12px;">
        Need help? Reply to this email or contact
        <strong>support@voiceguideapp.com</strong>
      </p>
    </div>

    <p style="margin:14px 0 0 0;text-align:center;color:#888;font-size:11px;">
      © 2025 VoiceGuideApp — Automated email
    </p>
  </div>
</body>
</html>
"""
    

# =========================================================
# RECEIPT — PACKAGE (TO / SCHOOL)
# =========================================================
def render_receipt_html_package(
    *,
    order_id: int,
    total_amount,
    package_type: str,
    bundle_size: int,
    licenses_lines: Iterable[str],
) -> str:
    total = _money(total_amount)
    lic_html = "".join(
        f"<li style='margin-bottom:6px;'><strong>{x}</strong></li>"
        for x in licenses_lines
    )

    return f"""\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VoiceGuideApp — Receipt</title>
</head>
<body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;color:#111;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:#ffffff;border-radius:14px;padding:22px;border:1px solid #eceef3;">
      
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div style="font-size:18px;font-weight:700;">VoiceGuideApp</div>
        <div style="font-size:12px;color:#666;">Purchase receipt</div>
      </div>

      <hr style="border:none;border-top:1px solid #eceef3;margin:16px 0;">

      <h1 style="font-size:18px;margin:0 0 8px 0;">Purchase completed ✅</h1>

      <p style="margin:0 0 16px 0;color:#444;font-size:14px;">
        Thank you for your purchase on VoiceGuideApp.
        Below you will find your order details and license codes.
      </p>

      <div style="background:#f9fafc;border:1px solid #eceef3;border-radius:12px;padding:14px;">
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px;">
          <span style="color:#666;">Order</span>
          <strong>#{order_id}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px;">
          <span style="color:#666;">Total</span>
          <strong>{total} €</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px;">
          <span style="color:#666;">Package</span>
          <strong>{package_type}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:14px;">
          <span style="color:#666;">Quantity</span>
          <strong>{bundle_size}</strong>
        </div>
      </div>

      <h2 style="font-size:15px;margin:18px 0 8px 0;">License codes</h2>
      <ul style="margin:0 0 14px 18px;font-size:14px;line-height:1.4;">
        {lic_html}
      </ul>

      <h2 style="font-size:15px;margin:18px 0 8px 0;">Quick instructions</h2>
      <ol style="margin:0 0 14px 18px;font-size:14px;line-height:1.5;">
        <li>Open the VoiceGuideApp</li>
        <li>Enter one of the license codes</li>
        <li>Start the tour and share the PIN with your guests</li>
      </ol>

      <p style="margin:0;color:#666;font-size:12px;">
        Need help? Reply to this email or contact
        <strong>support@voiceguideapp.com</strong>
      </p>
    </div>

    <p style="margin:14px 0 0 0;text-align:center;color:#888;font-size:11px;">
      © 2025 VoiceGuideApp — Automated email
    </p>
  </div>
</body>
</html>
"""
