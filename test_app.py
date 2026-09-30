import sys, re
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A
from datetime import date, timedelta
import tempfile, os
A.DATABASE = os.path.join(tempfile.mkdtemp(), 'test.db')  # tests use a throwaway database
A.init_db()
c = A.app.test_client()
results = []
def check(name, cond):
    results.append((name, cond)); print(("PASS" if cond else "FAIL"), "-", name)

def login(u, p):
    c.get("/logout")
    return c.post("/login", data={"username": u, "password": p}, follow_redirects=True)

# auth
check("protected page redirects to login", c.get("/patients").status_code == 302)
check("wrong password rejected", b"Invalid username" in login("admin", "bad").data)
check("admin login works", b"Welcome, Hospital Admin" in login("admin", "admin123").data)
check("dashboard shows stats", b"Total Patients" in c.get("/dashboard").data)

# receptionist: patients
login("reception", "reception123")
r = c.post("/patients/add", data={"name": "Test Patient", "age": "30", "gender": "Male", "phone": "9999999999", "blood_group": "O+", "address": "x"}, follow_redirects=True)
check("register patient", b"Patient registered" in r.data)
r = c.post("/patients/add", data={"name": "Bad", "age": "30", "gender": "Male", "phone": "123"}, follow_redirects=True)
check("phone validation", b"exactly 10 digits" in r.data)
r = c.post("/patients/add", data={"name": "Bad", "age": "abc", "gender": "Male", "phone": "9999999999"}, follow_redirects=True)
check("age validation", b"Age must be" in r.data)
check("search by name", b"Ravi Kumar" in c.get("/patients?q=Ravi").data and b"Priya" not in c.get("/patients?q=Ravi").data)
check("search by phone", b"Priya Sharma" in c.get("/patients?q=9123400002").data)
check("edit patient", b"updated" in c.post("/patients/5/edit", data={"name": "Test Patient 2", "age": "31", "gender": "Male", "phone": "9999999999"}, follow_redirects=True).data)
check("receptionist cannot delete patient", b"permission" in c.post("/patients/5/delete", follow_redirects=True).data)
check("receptionist cannot open departments", b"permission" in c.get("/departments", follow_redirects=True).data)

# appointments
tomorrow = str(date.today() + timedelta(days=2))
r = c.post("/appointments/add", data={"patient_id": "5", "doctor_id": "1", "appt_date": tomorrow, "appt_time": "10:00", "reason": "Checkup"}, follow_redirects=True)
check("book appointment", b"booked successfully" in r.data)
r = c.post("/appointments/add", data={"patient_id": "1", "doctor_id": "1", "appt_date": tomorrow, "appt_time": "10:00"}, follow_redirects=True)
check("double booking blocked", b"already has an appointment" in r.data)
r = c.post("/appointments/add", data={"patient_id": "1", "doctor_id": "1", "appt_date": "2020-01-01", "appt_time": "10:00"}, follow_redirects=True)
check("past date blocked", b"cannot be booked in the past" in r.data)
check("appointment filter", b"Checkup" in c.get(f"/appointments?date={tomorrow}").data)

# doctor role
login("doctor", "doctor123")
check("doctor sees only own appts", b"Chest discomfort" not in c.get("/appointments").data and b"Fever and cold" in c.get("/appointments").data)
check("doctor cannot book", b"permission" in c.get("/appointments/add", follow_redirects=True).data)
check("doctor cannot open billing", b"permission" in c.get("/billing", follow_redirects=True).data)
r = c.post("/patients/1/records/add", data={"diagnosis": "Viral fever", "prescription": "Paracetamol 500mg", "notes": "Rest"}, follow_redirects=True)
check("doctor adds medical record", b"Viral fever" in r.data and b"Paracetamol" in r.data)
check("record needs diagnosis", b"Diagnosis is required" in c.post("/patients/1/records/add", data={"diagnosis": ""}, follow_redirects=True).data)
check("doctor cannot update other doctor's appt", b"only update your own" in c.post("/appointments/2/status", data={"status": "Completed"}, follow_redirects=True).data)
check("doctor completes own appt", b"marked as Completed" in c.post("/appointments/1/status", data={"status": "Completed"}, follow_redirects=True).data)

# billing
login("reception", "reception123")
r = c.get("/billing/add?appointment_id=1")
check("bill prefilled from appointment", b'value="300.0"' in r.data)
r = c.post("/billing/add", data={"patient_id": "1", "appointment_id": "1", "consultation_fee": "300", "medicine_charges": "150.50", "other_charges": "49.50"}, follow_redirects=True)
check("bill total calculated (500)", b"500.00" in r.data)
check("negative charge rejected", b"non-negative" in c.post("/billing/add", data={"patient_id": "1", "consultation_fee": "-5"}, follow_redirects=True).data)
check("pay bill", b"Payment recorded" in c.post("/billing/1/pay", data={"payment_method": "UPI"}, follow_redirects=True).data)
check("bill shows paid", b"Paid via" in c.get("/billing/1").data)
check("unpaid filter works", b"No bills found" in c.get("/billing?status=Unpaid").data)

# admin
login("admin", "admin123")
r = c.post("/doctors/add", data={"name": "Dr. New", "department_id": "5", "specialization": "Skin", "fee": "500", "username": "drnew", "password": "secret123"}, follow_redirects=True)
check("admin adds doctor with login", b"Dr. New" in r.data)
check("new doctor can log in", b"Welcome, Dr. New" in login("drnew", "secret123").data)
login("admin", "admin123")
check("duplicate username rejected", b"already taken" in c.post("/doctors/add", data={"name": "Dr. Dup", "department_id": "5", "fee": "1", "username": "drnew", "password": "secret123"}, follow_redirects=True).data)
check("add department", b"Department added" in c.post("/departments", data={"name": "Neurology"}, follow_redirects=True).data)
check("duplicate department blocked", b"already exists" in c.post("/departments", data={"name": "Neurology"}, follow_redirects=True).data)
check("cannot delete dept with doctors", b"still has doctors" in c.post("/departments/1/delete", follow_redirects=True).data)
check("cannot delete doctor with history", b"Cannot remove" in c.post("/doctors/1/delete", follow_redirects=True).data)
check("admin deletes patient (cascade)", b"deleted" in c.post("/patients/1/delete", follow_redirects=True).data)
check("cascade removed bill", A.app.test_request_context() is not None and c.get("/billing/1", follow_redirects=True).data.count(b"Bill not found") == 1)

for path in ["/dashboard","/patients","/doctors","/appointments","/billing","/departments","/patients/2","/patients/add","/doctors/add","/appointments/add","/billing/add"]:
    check(f"page loads: {path}", c.get(path).status_code == 200)

print(f"\n{sum(1 for _,o in results if o)}/{len(results)} passed")
sys.exit(0 if all(o for _,o in results) else 1)
