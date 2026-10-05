from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Pipeline stages, in order. Stored as plain strings on Lead.stage so the
# dashboard/kanban can render them in a fixed sequence.
STAGES = [
    "new",                  # just captured (landing page or manual/historical)
    "contacted",            # office has reached out
    "consultation_booked",  # free consultation date confirmed
    "consultation_done",    # consultation happened
    "assessment_booked",    # free assessment scheduled
    "assessment_done",      # assessment completed
    "trial_booked",         # free trial lesson scheduled
    "trial_done",           # trial lesson completed
    "enrolled",             # won - now a paying student
    "lost",                 # not proceeding
]

STAGE_LABELS = {
    "new": "New Lead",
    "contacted": "Contacted",
    "consultation_booked": "Consultation Booked",
    "consultation_done": "Consultation Done",
    "assessment_booked": "Assessment Booked",
    "assessment_done": "Assessment Done",
    "trial_booked": "Trial Booked",
    "trial_done": "Trial Done",
    "enrolled": "Enrolled",
    "lost": "Lost",
}

LEAD_SOURCES = ["landing_page", "historical_import", "manual", "sms_campaign_reply", "other"]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")  # 'admin' | 'staff'
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    # Flask-Login uses is_active; keep our own 'active' column separate from it
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.active


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)

    parent_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=True, index=True)

    child_name = db.Column(db.String(150), nullable=True)
    year_group = db.Column(db.String(60), nullable=True)
    subject_needed = db.Column(db.String(120), nullable=True)

    source = db.Column(db.String(30), nullable=False, default="manual")
    stage = db.Column(db.String(30), nullable=False, default="new", index=True)

    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])

    notes = db.Column(db.Text, nullable=True)

    consultation_date = db.Column(db.DateTime, nullable=True)
    assessment_date = db.Column(db.DateTime, nullable=True)
    trial_date = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    communications = db.relationship(
        "Communication", backref="lead", cascade="all, delete-orphan",
        order_by="Communication.created_at.desc()",
    )
    stage_history = db.relationship(
        "StageHistory", backref="lead", cascade="all, delete-orphan",
        order_by="StageHistory.changed_at.desc()",
    )

    @property
    def stage_label(self) -> str:
        return STAGE_LABELS.get(self.stage, self.stage)


class StageHistory(db.Model):
    __tablename__ = "stage_history"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    from_stage = db.Column(db.String(30), nullable=True)
    to_stage = db.Column(db.String(30), nullable=False)
    note = db.Column(db.Text, nullable=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


class Communication(db.Model):
    __tablename__ = "communications"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)

    channel = db.Column(db.String(20), nullable=False)  # 'sms' | 'call' | 'email' | 'whatsapp'
    direction = db.Column(db.String(10), nullable=False, default="outbound")  # 'outbound' | 'inbound'
    body = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=True)  # 'sent' | 'delivered' | 'failed' | 'logged'

    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=True)

    sent_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    sent_by = db.relationship("User", foreign_keys=[sent_by_id])

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    channel = db.Column(db.String(20), nullable=False, default="sms")
    message_template = db.Column(db.Text, nullable=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recipients = db.relationship(
        "CampaignRecipient", backref="campaign", cascade="all, delete-orphan"
    )

    @property
    def sent_count(self) -> int:
        return sum(1 for r in self.recipients if r.status in ("sent", "delivered"))

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.recipients if r.status == "failed")


class CampaignRecipient(db.Model):
    __tablename__ = "campaign_recipients"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    lead = db.relationship("Lead")

    status = db.Column(db.String(20), nullable=False, default="pending")  # pending|sent|delivered|failed
    error = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
