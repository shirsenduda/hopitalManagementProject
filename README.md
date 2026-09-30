# CityCare Hospital Management System

A simple web-based Hospital Management System built with basic technologies:
**Python (Flask) + SQLite + HTML/CSS (Jinja templates)**. No heavy frameworks.

## Features
- Login with 3 roles: Admin, Receptionist, Doctor (role-based access)
- Dashboard with live counts (patients, doctors, today's appointments, unpaid bills, revenue)
- Patient registration, search (name/phone), edit, delete, full patient history page
- Doctor and department management (admin)
- Appointment booking with double-booking and past-date checks; complete/cancel; filters
- Medical records and prescriptions (doctors)
- Billing: auto-total, prefill from a completed appointment, mark paid (Cash/Card/UPI), printable invoice

## Run it
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000  (database and sample data are created automatically on first run)

## Demo logins
| Role         | Username  | Password     |
|--------------|-----------|--------------|
| Admin        | admin     | admin123     |
| Receptionist | reception | reception123 |
| Doctor       | doctor    | doctor123    |

## Run the tests
```bash
python test_app.py
```
(Tests use a temporary database, so your real data is not touched.)

## Project structure
```
app.py            all routes and logic
schema.sql        database tables
templates/        HTML pages (Jinja)
static/style.css  styling
test_app.py       feature tests
```

## Database tables
departments, doctors, users, patients, appointments, records, bills
