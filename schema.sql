-- Hospital Management System : database schema (SQLite)

CREATE TABLE IF NOT EXISTS departments (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS doctors (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    department_id  INTEGER NOT NULL,
    specialization TEXT,
    phone          TEXT,
    email          TEXT,
    fee            REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'receptionist', 'doctor')),
    full_name     TEXT NOT NULL,
    doctor_id     INTEGER,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    age         INTEGER NOT NULL,
    gender      TEXT NOT NULL,
    phone       TEXT NOT NULL,
    blood_group TEXT,
    address     TEXT,
    created_at  TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS appointments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id  INTEGER NOT NULL,
    appt_date  TEXT NOT NULL,
    appt_time  TEXT NOT NULL,
    reason     TEXT,
    status     TEXT NOT NULL DEFAULT 'Scheduled'
               CHECK (status IN ('Scheduled', 'Completed', 'Cancelled')),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL,
    doctor_id    INTEGER NOT NULL,
    diagnosis    TEXT NOT NULL,
    prescription TEXT,
    notes        TEXT,
    visit_date   TEXT NOT NULL DEFAULT (date('now')),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS bills (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER NOT NULL,
    appointment_id   INTEGER,
    consultation_fee REAL NOT NULL DEFAULT 0,
    medicine_charges REAL NOT NULL DEFAULT 0,
    other_charges    REAL NOT NULL DEFAULT 0,
    total            REAL NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Unpaid' CHECK (status IN ('Unpaid', 'Paid')),
    payment_method   TEXT,
    bill_date        TEXT NOT NULL DEFAULT (date('now')),
    FOREIGN KEY (patient_id)     REFERENCES patients(id)     ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
);
