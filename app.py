"""
CityCare Hospital Management System
Basic stack: Python + Flask + SQLite + HTML/CSS (Jinja templates)
"""
import os
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On Vercel the filesystem is read-only except /tmp, so the DB lives there.
# NOTE: data in /tmp is temporary and is lost when Vercel restarts the app.
IS_VERCEL = bool(os.environ.get("VERCEL"))
DATABASE = "/tmp/hospital.db" if IS_VERCEL else os.path.join(BASE_DIR, "hospital.db")

app = Flask(__name__)
# Set SECRET_KEY as an environment variable on Vercel.
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_db():
    """Create tables and insert sample data the first time the app runs."""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    with open(os.path.join(BASE_DIR, "schema.sql")) as f:
        db.executescript(f.read())

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        today = date.today()
        tomorrow = today + timedelta(days=1)

        for name in ["General Medicine", "Cardiology", "Orthopedics",
                     "Pediatrics", "Dermatology"]:
            db.execute("INSERT INTO departments (name) VALUES (?)", (name,))

        doctors = [
            ("Dr. Ananya Rao", 1, "General Physician", "9876500001", "ananya@citycare.com", 300),
            ("Dr. Rohit Mehta", 2, "Cardiologist", "9876500002", "rohit@citycare.com", 700),
            ("Dr. Sneha Iyer", 3, "Orthopedic Surgeon", "9876500003", "sneha@citycare.com", 600),
            ("Dr. Arjun Das", 4, "Pediatrician", "9876500004", "arjun@citycare.com", 400),
        ]
        db.executemany("INSERT INTO doctors (name, department_id, specialization, phone, email, fee) "
                       "VALUES (?,?,?,?,?,?)", doctors)

        users = [
            ("admin", "admin123", "admin", "Hospital Admin", None),
            ("reception", "reception123", "receptionist", "Front Desk", None),
            ("doctor", "doctor123", "doctor", "Dr. Ananya Rao", 1),
        ]
        for u, p, role, full, did in users:
            db.execute("INSERT INTO users (username, password_hash, role, full_name, doctor_id) "
                       "VALUES (?,?,?,?,?)", (u, generate_password_hash(p), role, full, did))

        patients = [
            ("Ravi Kumar", 45, "Male", "9123400001", "B+", "12 Lake Road, Bhubaneswar"),
            ("Priya Sharma", 29, "Female", "9123400002", "O+", "45 Patia, Bhubaneswar"),
            ("Aman Singh", 8, "Male", "9123400003", "A+", "7 Nayapalli, Bhubaneswar"),
            ("Lakshmi Devi", 62, "Female", "9123400004", "AB+", "Old Town, Bhubaneswar"),
        ]
        db.executemany("INSERT INTO patients (name, age, gender, phone, blood_group, address) "
                       "VALUES (?,?,?,?,?,?)", patients)

        appts = [
            (1, 1, str(today), "10:00", "Fever and cold", "Scheduled"),
            (2, 2, str(today), "11:30", "Chest discomfort", "Scheduled"),
            (3, 4, str(tomorrow), "09:30", "Routine checkup", "Scheduled"),
        ]
        db.executemany("INSERT INTO appointments (patient_id, doctor_id, appt_date, appt_time, reason, status) "
                       "VALUES (?,?,?,?,?,?)", appts)
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Login / role helpers
# --------------------------------------------------------------------------
def login_required(*roles):
    """Protect a route. Pass roles to restrict it, e.g. @login_required('admin')."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if roles and session.get("role") not in roles:
                flash("You do not have permission to open that page.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.template_filter("pid")
def patient_code(value):
    return f"P{int(value):04d}"


@app.template_filter("money")
def money(value):
    return f"₹{float(value):,.2f}"


@app.context_processor
def inject_today():
    return {"today": str(date.today())}


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["full_name"]
            session["doctor_id"] = user["doctor_id"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@app.route("/dashboard")
@login_required()
def dashboard():
    today = str(date.today())
    doctor_id = session.get("doctor_id") if session["role"] == "doctor" else None

    stats = {
        "patients": query("SELECT COUNT(*) c FROM patients", one=True)["c"],
        "doctors": query("SELECT COUNT(*) c FROM doctors", one=True)["c"],
        "today_appts": query(
            "SELECT COUNT(*) c FROM appointments WHERE appt_date = ? AND status = 'Scheduled'"
            + (" AND doctor_id = ?" if doctor_id else ""),
            (today, doctor_id) if doctor_id else (today,), one=True)["c"],
        "unpaid": query("SELECT COUNT(*) c FROM bills WHERE status = 'Unpaid'", one=True)["c"],
        "revenue": query("SELECT COALESCE(SUM(total), 0) s FROM bills WHERE status = 'Paid'",
                         one=True)["s"],
    }

    sql = ("SELECT a.*, p.name AS patient_name, d.name AS doctor_name FROM appointments a "
           "JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id "
           "WHERE a.appt_date = ? AND a.status = 'Scheduled'")
    args = [today]
    if doctor_id:
        sql += " AND a.doctor_id = ?"
        args.append(doctor_id)
    todays = query(sql + " ORDER BY a.appt_time", args)
    return render_template("dashboard.html", stats=stats, todays=todays)


# --------------------------------------------------------------------------
# Patients
# --------------------------------------------------------------------------
def read_patient_form():
    f = request.form
    data = {
        "name": f.get("name", "").strip(),
        "age": f.get("age", "").strip(),
        "gender": f.get("gender", ""),
        "phone": f.get("phone", "").strip(),
        "blood_group": f.get("blood_group", ""),
        "address": f.get("address", "").strip(),
    }
    error = None
    if not data["name"]:
        error = "Patient name is required."
    elif not data["age"].isdigit() or not (0 <= int(data["age"]) <= 120):
        error = "Age must be a number between 0 and 120."
    elif data["gender"] not in ("Male", "Female", "Other"):
        error = "Please select a gender."
    elif not (data["phone"].isdigit() and len(data["phone"]) == 10):
        error = "Phone number must be exactly 10 digits."
    return data, error


@app.route("/patients")
@login_required()
def patients():
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        rows = query("SELECT * FROM patients WHERE name LIKE ? OR phone LIKE ? ORDER BY id DESC",
                     (like, like))
    else:
        rows = query("SELECT * FROM patients ORDER BY id DESC")
    return render_template("patients.html", patients=rows, q=q)


@app.route("/patients/add", methods=["GET", "POST"])
@login_required("admin", "receptionist")
def patient_add():
    if request.method == "POST":
        data, error = read_patient_form()
        if error:
            flash(error, "error")
            return render_template("patient_form.html", patient=data, mode="Register")
        pid = execute("INSERT INTO patients (name, age, gender, phone, blood_group, address) "
                      "VALUES (?,?,?,?,?,?)",
                      (data["name"], int(data["age"]), data["gender"], data["phone"],
                       data["blood_group"], data["address"]))
        flash("Patient registered successfully.", "success")
        return redirect(url_for("patient_view", patient_id=pid))
    return render_template("patient_form.html", patient={}, mode="Register")


@app.route("/patients/<int:patient_id>")
@login_required()
def patient_view(patient_id):
    patient = query("SELECT * FROM patients WHERE id = ?", (patient_id,), one=True)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))
    appts = query("SELECT a.*, d.name AS doctor_name FROM appointments a "
                  "JOIN doctors d ON d.id = a.doctor_id WHERE a.patient_id = ? "
                  "ORDER BY a.appt_date DESC, a.appt_time DESC", (patient_id,))
    records = query("SELECT r.*, d.name AS doctor_name FROM records r "
                    "JOIN doctors d ON d.id = r.doctor_id WHERE r.patient_id = ? "
                    "ORDER BY r.visit_date DESC, r.id DESC", (patient_id,))
    bills = query("SELECT * FROM bills WHERE patient_id = ? ORDER BY id DESC", (patient_id,))
    return render_template("patient_view.html", patient=patient, appts=appts,
                           records=records, bills=bills)


@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@login_required("admin", "receptionist")
def patient_edit(patient_id):
    patient = query("SELECT * FROM patients WHERE id = ?", (patient_id,), one=True)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))
    if request.method == "POST":
        data, error = read_patient_form()
        if error:
            flash(error, "error")
            data["id"] = patient_id
            return render_template("patient_form.html", patient=data, mode="Edit")
        execute("UPDATE patients SET name=?, age=?, gender=?, phone=?, blood_group=?, address=? "
                "WHERE id=?", (data["name"], int(data["age"]), data["gender"], data["phone"],
                               data["blood_group"], data["address"], patient_id))
        flash("Patient details updated.", "success")
        return redirect(url_for("patient_view", patient_id=patient_id))
    return render_template("patient_form.html", patient=patient, mode="Edit")


@app.route("/patients/<int:patient_id>/delete", methods=["POST"])
@login_required("admin")
def patient_delete(patient_id):
    execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    flash("Patient and all related records were deleted.", "success")
    return redirect(url_for("patients"))


@app.route("/patients/<int:patient_id>/records/add", methods=["POST"])
@login_required("doctor")
def record_add(patient_id):
    diagnosis = request.form.get("diagnosis", "").strip()
    if not diagnosis:
        flash("Diagnosis is required.", "error")
    else:
        execute("INSERT INTO records (patient_id, doctor_id, diagnosis, prescription, notes, visit_date) "
                "VALUES (?,?,?,?,?,?)",
                (patient_id, session["doctor_id"], diagnosis,
                 request.form.get("prescription", "").strip(),
                 request.form.get("notes", "").strip(), str(date.today())))
        flash("Medical record saved.", "success")
    return redirect(url_for("patient_view", patient_id=patient_id))


# --------------------------------------------------------------------------
# Departments and Doctors
# --------------------------------------------------------------------------
@app.route("/departments", methods=["GET", "POST"])
@login_required("admin")
def departments():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Department name is required.", "error")
        else:
            try:
                execute("INSERT INTO departments (name) VALUES (?)", (name,))
                flash("Department added.", "success")
            except sqlite3.IntegrityError:
                flash("That department already exists.", "error")
        return redirect(url_for("departments"))
    rows = query("SELECT d.*, (SELECT COUNT(*) FROM doctors WHERE department_id = d.id) AS doctor_count "
                 "FROM departments d ORDER BY d.name")
    return render_template("departments.html", departments=rows)


@app.route("/departments/<int:dept_id>/delete", methods=["POST"])
@login_required("admin")
def department_delete(dept_id):
    try:
        execute("DELETE FROM departments WHERE id = ?", (dept_id,))
        flash("Department deleted.", "success")
    except sqlite3.IntegrityError:
        flash("Cannot delete a department that still has doctors.", "error")
    return redirect(url_for("departments"))


@app.route("/doctors")
@login_required()
def doctors():
    rows = query("SELECT d.*, dep.name AS department FROM doctors d "
                 "JOIN departments dep ON dep.id = d.department_id ORDER BY d.name")
    return render_template("doctors.html", doctors=rows)


@app.route("/doctors/add", methods=["GET", "POST"])
@login_required("admin")
def doctor_add():
    depts = query("SELECT * FROM departments ORDER BY name")
    if request.method == "POST":
        f = request.form
        name = f.get("name", "").strip()
        username = f.get("username", "").strip()
        password = f.get("password", "")
        try:
            fee = float(f.get("fee", "0") or 0)
        except ValueError:
            fee = -1
        error = None
        if not name:
            error = "Doctor name is required."
        elif not f.get("department_id"):
            error = "Please choose a department."
        elif fee < 0:
            error = "Consultation fee must be a valid positive number."
        elif username and len(password) < 6:
            error = "Login password must be at least 6 characters."
        if error:
            flash(error, "error")
            return render_template("doctor_form.html", depts=depts, d=f)
        did = None
        try:
            did = execute("INSERT INTO doctors (name, department_id, specialization, phone, email, fee) "
                          "VALUES (?,?,?,?,?,?)",
                          (name, int(f["department_id"]), f.get("specialization", "").strip(),
                           f.get("phone", "").strip(), f.get("email", "").strip(), fee))
            if username:
                execute("INSERT INTO users (username, password_hash, role, full_name, doctor_id) "
                        "VALUES (?,?,?,?,?)",
                        (username, generate_password_hash(password), "doctor", name, did))
            flash("Doctor added successfully.", "success")
            return redirect(url_for("doctors"))
        except sqlite3.IntegrityError:
            flash("That login username is already taken.", "error")
            if did:
                execute("DELETE FROM doctors WHERE id = ?", (did,))
            return render_template("doctor_form.html", depts=depts, d=f)
    return render_template("doctor_form.html", depts=depts, d={})


@app.route("/doctors/<int:doctor_id>/delete", methods=["POST"])
@login_required("admin")
def doctor_delete(doctor_id):
    try:
        execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
        flash("Doctor removed.", "success")
    except sqlite3.IntegrityError:
        flash("Cannot remove a doctor who has appointments or records.", "error")
    return redirect(url_for("doctors"))


# --------------------------------------------------------------------------
# Appointments
# --------------------------------------------------------------------------
@app.route("/appointments")
@login_required()
def appointments():
    day = request.args.get("date", "").strip()
    status = request.args.get("status", "").strip()
    sql = ("SELECT a.*, p.name AS patient_name, d.name AS doctor_name FROM appointments a "
           "JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE 1=1")
    args = []
    if session["role"] == "doctor":
        sql += " AND a.doctor_id = ?"
        args.append(session["doctor_id"])
    if day:
        sql += " AND a.appt_date = ?"
        args.append(day)
    if status:
        sql += " AND a.status = ?"
        args.append(status)
    rows = query(sql + " ORDER BY a.appt_date DESC, a.appt_time", args)
    return render_template("appointments.html", appointments=rows, day=day, status=status)


@app.route("/appointments/add", methods=["GET", "POST"])
@login_required("admin", "receptionist")
def appointment_add():
    patients_list = query("SELECT id, name, phone FROM patients ORDER BY name")
    doctors_list = query("SELECT d.id, d.name, dep.name AS department FROM doctors d "
                         "JOIN departments dep ON dep.id = d.department_id ORDER BY d.name")
    form = request.form if request.method == "POST" else {
        "patient_id": request.args.get("patient_id", "")}

    if request.method == "POST":
        patient_id = form.get("patient_id")
        doctor_id = form.get("doctor_id")
        appt_date = form.get("appt_date", "")
        appt_time = form.get("appt_time", "")
        error = None
        if not (patient_id and doctor_id and appt_date and appt_time):
            error = "Patient, doctor, date and time are all required."
        elif appt_date < str(date.today()):
            error = "Appointments cannot be booked in the past."
        elif query("SELECT id FROM appointments WHERE doctor_id=? AND appt_date=? AND appt_time=? "
                   "AND status='Scheduled'", (doctor_id, appt_date, appt_time), one=True):
            error = "That doctor already has an appointment at this time. Please pick another slot."
        if error:
            flash(error, "error")
        else:
            execute("INSERT INTO appointments (patient_id, doctor_id, appt_date, appt_time, reason) "
                    "VALUES (?,?,?,?,?)",
                    (patient_id, doctor_id, appt_date, appt_time, form.get("reason", "").strip()))
            flash("Appointment booked successfully.", "success")
            return redirect(url_for("appointments", date=appt_date))
    return render_template("appointment_form.html", patients=patients_list,
                           doctors=doctors_list, f=form)


@app.route("/appointments/<int:appt_id>/status", methods=["POST"])
@login_required()
def appointment_status(appt_id):
    new_status = request.form.get("status")
    appt = query("SELECT * FROM appointments WHERE id = ?", (appt_id,), one=True)
    if not appt or new_status not in ("Completed", "Cancelled"):
        flash("Invalid request.", "error")
    elif session["role"] == "doctor" and appt["doctor_id"] != session["doctor_id"]:
        flash("You can only update your own appointments.", "error")
    else:
        execute("UPDATE appointments SET status = ? WHERE id = ?", (new_status, appt_id))
        flash(f"Appointment marked as {new_status}.", "success")
    return redirect(request.referrer or url_for("appointments"))


# --------------------------------------------------------------------------
# Billing
# --------------------------------------------------------------------------
@app.route("/billing")
@login_required("admin", "receptionist")
def billing():
    status = request.args.get("status", "").strip()
    sql = ("SELECT b.*, p.name AS patient_name FROM bills b "
           "JOIN patients p ON p.id = b.patient_id")
    args = []
    if status:
        sql += " WHERE b.status = ?"
        args.append(status)
    rows = query(sql + " ORDER BY b.id DESC", args)
    return render_template("billing.html", bills=rows, status=status)


@app.route("/billing/add", methods=["GET", "POST"])
@login_required("admin", "receptionist")
def bill_add():
    patients_list = query("SELECT id, name, phone FROM patients ORDER BY name")
    form = {}
    if request.method == "POST":
        form = request.form
        try:
            consult = float(form.get("consultation_fee") or 0)
            medicine = float(form.get("medicine_charges") or 0)
            other = float(form.get("other_charges") or 0)
        except ValueError:
            consult = medicine = other = -1
        if not form.get("patient_id"):
            flash("Please select a patient.", "error")
        elif min(consult, medicine, other) < 0:
            flash("Charges must be valid, non-negative numbers.", "error")
        else:
            appt_id = form.get("appointment_id") or None
            bill_id = execute("INSERT INTO bills (patient_id, appointment_id, consultation_fee, "
                              "medicine_charges, other_charges, total, bill_date) VALUES (?,?,?,?,?,?,?)",
                              (form["patient_id"], appt_id, consult, medicine, other,
                               consult + medicine + other, str(date.today())))
            flash("Bill generated.", "success")
            return redirect(url_for("bill_view", bill_id=bill_id))
    else:
        appt_id = request.args.get("appointment_id")
        if appt_id:
            a = query("SELECT a.patient_id, a.id, d.fee FROM appointments a "
                      "JOIN doctors d ON d.id = a.doctor_id WHERE a.id = ?", (appt_id,), one=True)
            if a:
                form = {"patient_id": a["patient_id"], "appointment_id": a["id"],
                        "consultation_fee": a["fee"]}
    return render_template("bill_form.html", patients=patients_list, f=form)


@app.route("/billing/<int:bill_id>")
@login_required("admin", "receptionist")
def bill_view(bill_id):
    bill = query("SELECT b.*, p.name AS patient_name, p.phone, p.age, p.gender FROM bills b "
                 "JOIN patients p ON p.id = b.patient_id WHERE b.id = ?", (bill_id,), one=True)
    if not bill:
        flash("Bill not found.", "error")
        return redirect(url_for("billing"))
    return render_template("bill_view.html", bill=bill)


@app.route("/billing/<int:bill_id>/pay", methods=["POST"])
@login_required("admin", "receptionist")
def bill_pay(bill_id):
    method = request.form.get("payment_method")
    if method not in ("Cash", "Card", "UPI"):
        flash("Please choose a payment method.", "error")
    else:
        execute("UPDATE bills SET status='Paid', payment_method=? WHERE id=? AND status='Unpaid'",
                (method, bill_id))
        flash("Payment recorded.", "success")
    return redirect(url_for("bill_view", bill_id=bill_id))


# On Vercel, `if __name__ == "__main__"` never runs, so create the DB at import time.
if IS_VERCEL and not os.path.exists(DATABASE):
    init_db()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)