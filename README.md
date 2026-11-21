# ChoreMarket — Django Freelance Service Booking System

A Django MVP based on the supplied **Freelance Service Booking System — Project Proposal (Django)** and ChoreMarket Figma style guide.

## Included
- Client, Service Provider and Admin roles with a custom user model
- Registration, login, role-aware dashboards and Django admin
- Provider profile with ID/selfie upload and admin approval gate
- Categories, service listings and up to three Basic/Standard/Premium packages
- Service search and category / maximum-price filters
- Booking requests, time-overlap checks, status transitions and notifications
- Mock payment ledger (no real money), hold/refund/release states and 10% example platform fee
- Booking-scoped chat, proof uploads, reviews, safety reports and disputes
- Responsive interface using the supplied palette and typography guide

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations marketplace
python manage.py migrate
python manage.py seed_categories
python manage.py createsuperuser
python manage.py runserver
```
Open http://127.0.0.1:8000/ . Create a normal account through **Sign up**. To make an admin account, use `createsuperuser`; then set its `role` to `ADMIN` in Django admin if needed. Add categories in `/admin/` before creating services.

## Suggested demo setup
1. Default categories are created with `python manage.py seed_categories` (you can also manage them in `/admin/`).
2. Register a provider, open Provider verification, submit the profile and documents.
3. In Django admin, approve the provider profile.
4. Provider adds a service and its package(s).
5. Register a client, browse and book a package. The mock ledger holds the package fee and optional errand budget.
6. Provider accepts, starts the job, uploads a photo (and grocery receipt when applicable), then marks complete.

## Design tokens
- Primary `#2146AD`; secondary `#3B82F6`; accent `#F05A0A`; foreground `#1E3A8A`; destructive `#DC2626`; background `#EFF6FF`; border `#DBEAFE`.
- Poppins for headings and Open Sans for interface/body text.
- Compact 8px spacing rhythm, 12px surfaces and restrained shadows.

## Important implementation notes
- This is a **mock-payment demo**, not a payment gateway. Do not enter real payment credentials.
- Configure a production `SECRET_KEY`, `DEBUG=False`, HTTPS, secure cookie settings, private storage for identity documents and a real email provider before deployment.
- SQLite is configured for quick local setup. For concurrent production booking traffic, use PostgreSQL and add a database exclusion constraint over provider + time range for active statuses. The current transaction-wrapped conflict check is suitable for demonstrating the flow but is not a substitute for that production constraint under all concurrent workloads.
- The proposal's 10% platform fee, cancellation cutoff/fee and reliability-score threshold were open decisions. The demo uses 10% as a clearly adjustable starting assumption; detailed cancellation fee policy and reliability scoring still need stakeholder decisions.
- Provider identity files are stored under a private-named media path in this starter; production must move these to access-controlled private storage and serve them only to authorized admins.
- The proposal calls for 24-hour auto-expiry and 48-hour auto-confirm. Add a scheduled worker (Celery/cron) before production; they are not silently simulated by page loads.
- Search currently supports keyword, category and maximum package price. Rating and geographic-radius filtering need location coordinates and rating aggregation to be configured for the deployment.

## Project structure

```text
config/                 Django project settings and URL routing
marketplace/            Custom user, marketplace, booking, payment and safety models/views
 templates/             Server-rendered pages
 static/css/style.css   ChoreMarket design system
```
