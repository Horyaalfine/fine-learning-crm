from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Campaign, CampaignRecipient, Communication, Lead, db
from sms import SmsNotConfigured, send_sms

campaigns_bp = Blueprint("campaigns", __name__)

DEFAULT_TEMPLATE = (
    "Hi {parent_name}, it's Fine Learning – we'd love to welcome {child_name_or_your_child} "
    "back for Maths, English or Science tuition. Book a free consultation here: {landing_page_url}"
)


def render_message(template: str, lead: Lead) -> str:
    child = lead.child_name or "your child"
    return (
        template.replace("{parent_name}", lead.parent_name or "there")
        .replace("{child_name}", lead.child_name or "")
        .replace("{child_name_or_your_child}", child)
        .replace("{landing_page_url}", current_app.config["LANDING_PAGE_URL"])
    )


@campaigns_bp.route("/campaigns")
@login_required
def list_campaigns():
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    return render_template("campaigns_list.html", campaigns=campaigns)


@campaigns_bp.route("/campaigns/new", methods=["GET", "POST"])
@login_required
def new_campaign():
    # Simple segment options for v1: all leads, or leads at a specific stage,
    # or leads with no stage progress yet (fresh historical imports).
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        message_template = (request.form.get("message_template") or "").strip()
        segment = request.form.get("segment") or "all"
        lead_ids = request.form.getlist("lead_ids")

        if not name or not message_template:
            flash("Campaign name and message are required.", "error")
            return render_template(
                "campaign_form.html", default_template=DEFAULT_TEMPLATE, leads=Lead.query.order_by(Lead.parent_name).all()
            )

        if lead_ids:
            leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
        elif segment == "new":
            leads = Lead.query.filter_by(stage="new").all()
        elif segment == "historical":
            leads = Lead.query.filter_by(source="historical_import").all()
        else:
            leads = Lead.query.all()

        leads = [l for l in leads if l.phone]

        if not leads:
            flash("No leads with a phone number matched that selection.", "error")
            return render_template(
                "campaign_form.html", default_template=DEFAULT_TEMPLATE, leads=Lead.query.order_by(Lead.parent_name).all()
            )

        campaign = Campaign(
            name=name,
            channel="sms",
            message_template=message_template,
            created_by=current_user,
        )
        db.session.add(campaign)
        db.session.flush()

        for lead in leads:
            db.session.add(CampaignRecipient(campaign=campaign, lead=lead, status="pending"))

        db.session.commit()
        flash(f"Campaign '{name}' created with {len(leads)} recipients. Review and send below.", "success")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    return render_template(
        "campaign_form.html",
        default_template=DEFAULT_TEMPLATE,
        leads=Lead.query.order_by(Lead.parent_name).all(),
    )


@campaigns_bp.route("/campaigns/<int:campaign_id>")
@login_required
def detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    return render_template("campaign_detail.html", campaign=campaign)


@campaigns_bp.route("/campaigns/<int:campaign_id>/send", methods=["POST"])
@login_required
def send_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)

    sent = 0
    failed = 0
    for recipient in campaign.recipients:
        if recipient.status in ("sent", "delivered"):
            continue  # don't double-send if this is re-triggered

        lead = recipient.lead
        body = render_message(campaign.message_template, lead)

        try:
            send_sms(lead.phone, body)
            recipient.status = "sent"
            recipient.sent_at = datetime.utcnow()
            sent += 1
            db.session.add(
                Communication(
                    lead=lead,
                    channel="sms",
                    direction="outbound",
                    body=body,
                    status="sent",
                    campaign_id=campaign.id,
                    sent_by=current_user,
                )
            )
        except SmsNotConfigured as exc:
            db.session.commit()
            flash(str(exc), "error")
            return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
        except Exception as exc:  # Twilio errors, bad numbers, etc.
            recipient.status = "failed"
            recipient.error = str(exc)
            failed += 1

    db.session.commit()
    flash(f"Sent {sent} messages, {failed} failed.", "success" if failed == 0 else "error")
    return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
