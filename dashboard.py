from flask import Blueprint, render_template
from flask_login import login_required

from models import STAGES, STAGE_LABELS, Lead

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    counts = {s: Lead.query.filter_by(stage=s).count() for s in STAGES}
    total = sum(counts.values())
    enrolled = counts.get("enrolled", 0)
    conversion_rate = round((enrolled / total) * 100, 1) if total else 0.0

    recent_leads = Lead.query.order_by(Lead.created_at.desc()).limit(8).all()

    return render_template(
        "dashboard.html",
        counts=counts,
        stage_labels=STAGE_LABELS,
        stages=STAGES,
        total=total,
        enrolled=enrolled,
        conversion_rate=conversion_rate,
        recent_leads=recent_leads,
    )
