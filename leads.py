import csv
import io
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import STAGES, STAGE_LABELS, Communication, Lead, StageHistory, db

leads_bp = Blueprint("leads", __name__)


@leads_bp.route("/leads")
@login_required
def board():
    """Kanban-style pipeline board, grouped by stage. All stages are always
    shown as columns; `stage` in the query string just highlights one."""
    active_stage = request.args.get("stage")
    leads = Lead.query.order_by(Lead.updated_at.desc()).all()

    columns = {s: [] for s in STAGES}
    for lead in leads:
        columns.setdefault(lead.stage, []).append(lead)

    return render_template(
        "leads_board.html",
        columns=columns,
        stages=STAGES,
        stage_labels=STAGE_LABELS,
        active_stage=active_stage,
    )


@leads_bp.route("/leads/new", methods=["GET", "POST"])
@login_required
def new_lead():
    if request.method == "POST":
        lead = Lead(
            parent_name=(request.form.get("parent_name") or "").strip(),
            phone=(request.form.get("phone") or "").strip() or None,
            email=(request.form.get("email") or "").strip() or None,
            child_name=(request.form.get("child_name") or "").strip() or None,
            year_group=(request.form.get("year_group") or "").strip() or None,
            subject_needed=(request.form.get("subject_needed") or "").strip() or None,
            source="manual",
            notes=(request.form.get("notes") or "").strip() or None,
        )
        if not lead.parent_name:
            flash("Parent name is required.", "error")
            return render_template("lead_form.html")

        db.session.add(lead)
        db.session.commit()
        flash(f"Lead for {lead.parent_name} created.", "success")
        return redirect(url_for("leads.detail", lead_id=lead.id))

    return render_template("lead_form.html")


@leads_bp.route("/leads/<int:lead_id>")
@login_required
def detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return render_template(
        "lead_detail.html", lead=lead, stages=STAGES, stage_labels=STAGE_LABELS
    )


@leads_bp.route("/leads/<int:lead_id>/stage", methods=["POST"])
@login_required
def change_stage(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    new_stage = request.form.get("stage")
    note = (request.form.get("note") or "").strip() or None

    if new_stage not in STAGES:
        flash("Unknown stage.", "error")
        return redirect(url_for("leads.detail", lead_id=lead.id))

    old_stage = lead.stage
    lead.stage = new_stage
    lead.updated_at = datetime.utcnow()

    # Convenience: stamp the relevant date field when moving into a booked stage
    now = datetime.utcnow()
    if new_stage == "consultation_booked" and not lead.consultation_date:
        lead.consultation_date = now
    elif new_stage == "assessment_booked" and not lead.assessment_date:
        lead.assessment_date = now
    elif new_stage == "trial_booked" and not lead.trial_date:
        lead.trial_date = now

    db.session.add(
        StageHistory(
            lead=lead,
            from_stage=old_stage,
            to_stage=new_stage,
            note=note,
            changed_by=current_user,
        )
    )
    db.session.commit()
    flash(f"Moved {lead.parent_name} to {STAGE_LABELS.get(new_stage, new_stage)}.", "success")
    return redirect(url_for("leads.detail", lead_id=lead.id))


@leads_bp.route("/leads/<int:lead_id>/note", methods=["POST"])
@login_required
def add_note(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    body = (request.form.get("body") or "").strip()
    channel = request.form.get("channel") or "call"

    if body:
        db.session.add(
            Communication(
                lead=lead,
                channel=channel,
                direction="outbound",
                body=body,
                status="logged",
                sent_by=current_user,
            )
        )
        lead.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Note logged.", "success")

    return redirect(url_for("leads.detail", lead_id=lead.id))


@leads_bp.route("/leads/import", methods=["GET", "POST"])
@login_required
def import_leads():
    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or not file.filename:
            flash("Choose a CSV file first.", "error")
            return render_template("lead_import.html")

        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)

        required = {"parent_name"}
        if not reader.fieldnames or not required.issubset(
            {f.strip().lower() for f in reader.fieldnames}
        ):
            flash(
                "CSV must include at least a 'parent_name' column "
                "(phone, email, child_name, year_group, subject_needed, notes are optional).",
                "error",
            )
            return render_template("lead_import.html")

        # normalize header lookup regardless of casing/whitespace
        field_map = {f.strip().lower(): f for f in reader.fieldnames}

        def get(row, key):
            col = field_map.get(key)
            return (row.get(col) or "").strip() if col else ""

        created = 0
        skipped = 0
        for row in reader:
            parent_name = get(row, "parent_name")
            if not parent_name:
                skipped += 1
                continue
            lead = Lead(
                parent_name=parent_name,
                phone=get(row, "phone") or None,
                email=get(row, "email") or None,
                child_name=get(row, "child_name") or None,
                year_group=get(row, "year_group") or None,
                subject_needed=get(row, "subject_needed") or None,
                notes=get(row, "notes") or None,
                source="historical_import",
                stage="new",
            )
            db.session.add(lead)
            created += 1

        db.session.commit()
        flash(f"Imported {created} leads ({skipped} rows skipped - no parent name).", "success")
        return redirect(url_for("leads.board"))

    return render_template("lead_import.html")
