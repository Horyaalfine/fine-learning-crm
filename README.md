# Fine Learning CRM

Internal CRM for the Fine Learning online tuition business. Tracks the pipeline
from first contact through to enrolment:

```
New -> Contacted -> Consultation Booked -> Consultation Done ->
Assessment Booked -> Assessment Done -> Trial Booked -> Trial Done ->
Enrolled (or Lost at any point)
```

Leads come in two ways:

1. **Landing page bookings** - the "Book My Free Consultation" form on
   `book.finelearning.co.uk` POSTs to `/api/leads` on this app.
2. **Historical parents/students** - imported in bulk via CSV
   (Leads -> Import CSV), then contacted via an SMS campaign that links back
   to the landing page.

## Stack

Flask + SQLAlchemy + PostgreSQL + Flask-Login, server-rendered templates
(no JS framework), deployed on Railway - consistent with the rest of the
Fine Tutors / Fine Learning app suite.

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY=dev
export DATABASE_URL=sqlite:///local.db   # or a real Postgres URL
flask --app app run --debug
```

Create your first admin user:

```bash
flask --app app create-admin "Your Name" you@finelearning.co.uk a-strong-password
```

## Environment variables (set these in Railway)

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | yes | random string, used for session signing |
| `DATABASE_URL` | yes | Railway Postgres connection string (set automatically if you attach a Postgres plugin) |
| `LANDING_PAGE_URL` | yes | `https://book.finelearning.co.uk` - used in SMS message templates |
| `LEAD_API_KEY` | recommended | shared secret the landing page form sends in `X-Api-Key`; leave unset to allow unauthenticated POSTs (not recommended once live) |
| `ALLOWED_LEAD_ORIGINS` | yes | comma-separated list, e.g. `https://book.finelearning.co.uk`, used for CORS on `/api/leads` |
| `TWILIO_ACCOUNT_SID` | for SMS sending | |
| `TWILIO_AUTH_TOKEN` | for SMS sending | |
| `TWILIO_FROM_NUMBER` | for SMS sending | or use `TWILIO_MESSAGING_SERVICE_SID` instead |

Without Twilio variables set, the app still runs - campaign creation works,
but clicking "Send now" shows an error explaining Twilio isn't configured
yet, rather than crashing.

## Wiring up the landing page form

Once this app is deployed and `LEAD_API_KEY` is set, add this to the landing
page's booking form (replace the form's current submit handling) so a
booking creates a lead here automatically:

```html
<script>
document.querySelector('#consultation-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = {
    parent_name: form.parent_name.value,
    phone: form.phone.value,
    email: form.email.value,
    year_group: form.year_group.value,
    subject_needed: form.subject_needed.value,
  };
  try {
    const res = await fetch('https://<your-crm-domain>/api/leads', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': '<LEAD_API_KEY value>',
      },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      form.closest('.form-card').innerHTML = '<h3>Thanks! We\\'ll call you back within 30 minutes during opening hours.</h3>';
    } else {
      alert('Something went wrong - please call or WhatsApp us instead.');
    }
  } catch (err) {
    alert('Something went wrong - please call or WhatsApp us instead.');
  }
});
</script>
```

(The `LEAD_API_KEY` ends up visible in the landing page's HTML source either
way, since it's a public page - its only job is to stop randos who find the
URL from spamming the endpoint, not to be a real secret.)

## CSV import format

```
parent_name,phone,email,child_name,year_group,subject_needed,notes
```

Only `parent_name` is required. See `sample_leads.csv` for an example.
