import json
import os
import re
import sqlite3
from pathlib import Path
from datetime import date, datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'student_support.db'


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_year_sem(value):
    if value is None:
        return 0, 0

    text = str(value).strip()
    year_match = re.search(r'\b([ivxlcdm]+|\d+)\s*(?:st|nd|rd|th)?\s+year\b', text, re.IGNORECASE)
    if year_match is None:
        year_match = re.search(r'\byear\s+(\d+)\b', text, re.IGNORECASE)
    semester_match = re.search(r'\bsem(?:ester)?\s*[:#-]?\s*(\d+)\b', text, re.IGNORECASE)

    def parse_year(token):
        if token.isdigit():
            return int(token)
        values = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
        return values.get(token.upper(), 0)

    year = parse_year(year_match.group(1)) if year_match else 0
    if semester_match:
        semester = int(semester_match.group(1))
    else:
        numbers = re.findall(r'\d+', text)
        semester = int(numbers[1]) if len(numbers) > 1 else 0
    return (
        year if 1 <= year <= 20 else 0,
        semester if 1 <= semester <= 20 else 0,
    )


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                year INTEGER NOT NULL,
                semester INTEGER NOT NULL,
                attendance_percentage REAL NOT NULL,
                average_marks REAL NOT NULL,
                active_backlogs INTEGER NOT NULL,
                financial_support TEXT NOT NULL,
                estimated_risk TEXT NOT NULL,
                last_counseling_date TEXT,
                risk_score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counseling_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                concerns TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                assigned_faculty TEXT NOT NULL,
                appointment_date TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                follow_up_date TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                counselor_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                session_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Scheduled',
                follow_up TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                metrics TEXT NOT NULL,
                trained_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        student_columns = {
            row['name'] for row in conn.execute('PRAGMA table_info(students)').fetchall()
        }
        additional_columns = {
            'data_source': "TEXT NOT NULL DEFAULT 'demo'",
            'data_fields': "TEXT NOT NULL DEFAULT '{}'",
            'financial_difficulty': 'TEXT',
            'scholarship_status': 'TEXT',
            'previous_semester_gpa': 'REAL',
            'assignment_completion': 'REAL',
            'dropout_status': 'TEXT',
        }
        for column, definition in additional_columns.items():
            if column not in student_columns:
                conn.execute(f'ALTER TABLE students ADD COLUMN {column} {definition}')


def seed_demo_data():
    """Initialize database schema only. No demo data is seeded."""
    with get_connection() as conn:
        # Ensure tables exist but don't add any demo records
        pass


def list_students(search=None, department=None, year=None, semester=None, risk=None):
    query = 'SELECT * FROM students WHERE 1=1'
    params = []
    if search:
        query += ' AND (student_id LIKE ? OR name LIKE ? )'
        params.extend([f'%{search}%', f'%{search}%'])
    if department and department != 'All':
        query += ' AND department = ?'
        params.append(department)
    if year and year != 'All':
        query += ' AND year = ?'
        params.append(int(year))
    if semester and semester != 'All':
        query += ' AND semester = ?'
        params.append(int(semester))
    if risk and risk != 'All':
        query += ' AND estimated_risk = ?'
        params.append(risk)
    query += ' ORDER BY name ASC'
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_student_record(row) for row in rows]


def _student_record(row):
    record = dict(row)
    try:
        record['data_fields'] = json.loads(record.get('data_fields') or '{}')
    except (TypeError, json.JSONDecodeError):
        record['data_fields'] = {}
    if record.get('year', 0) <= 0 or record.get('semester', 0) <= 0:
        combined_year_sem = record['data_fields'].get('year_sem')
        if combined_year_sem is not None:
            year, semester = _parse_year_sem(combined_year_sem)
            if record.get('year', 0) <= 0:
                record['year'] = year
            if record.get('semester', 0) <= 0:
                record['semester'] = semester
    if not record.get('last_counseling_date'):
        for key in (
            'last_counseling_date', 'last_counseling', 'last_counselling_date',
            'last_counselling', 'last_counselling_data', 'counseling_date',
            'counselling_date', 'counselling_data',
        ):
            value = record['data_fields'].get(key)
            if value is not None and str(value).strip():
                record['last_counseling_date'] = str(value).strip()
                break
    return record


def get_student(student_id):
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
        return _student_record(row) if row else None


def replace_student_dataset(records):
    with get_connection() as conn:
        conn.execute('DELETE FROM counseling_cases')
        conn.execute('DELETE FROM appointments')
        conn.execute('DELETE FROM students')
        conn.executemany(
            """
            INSERT INTO students (
                student_id, name, department, year, semester, attendance_percentage,
                average_marks, active_backlogs, financial_support, estimated_risk,
                last_counseling_date, risk_score, data_source, data_fields,
                financial_difficulty, scholarship_status, previous_semester_gpa,
                assignment_completion, dropout_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record['student_id'],
                    record['name'],
                    record['department'],
                    record['year'],
                    record['semester'],
                    record['attendance_percentage'],
                    record['average_marks'],
                    record['active_backlogs'],
                    record['financial_support'],
                    record['estimated_risk'],
                    record.get('last_counseling_date'),
                    record['risk_score'],
                    json.dumps(record['data_fields'], ensure_ascii=False),
                    record.get('financial_difficulty'),
                    record.get('scholarship_status'),
                    record.get('previous_semester_gpa'),
                    record.get('assignment_completion'),
                    record.get('dropout_status'),
                )
                for record in records
            ],
        )


def update_student_assessments(assessments):
    with get_connection() as conn:
        conn.executemany(
            """
            UPDATE students
            SET estimated_risk = ?, risk_score = ?, data_fields = ?, updated_at = CURRENT_TIMESTAMP
            WHERE student_id = ?
            """,
            [
                (
                    assessment['risk_category'],
                    assessment['score'],
                    json.dumps(assessment['data_fields'], ensure_ascii=False),
                    assessment['student_id'],
                )
                for assessment in assessments
            ],
        )


def upsert_student(payload):
    with get_connection() as conn:
        record = payload.copy()
        data = (
            record['student_id'],
            record['name'],
            record['department'],
            int(record['year']),
            int(record['semester']),
            float(record['attendance_percentage']),
            float(record['average_marks']),
            int(record['active_backlogs']),
            record['financial_support'],
            record['estimated_risk'],
            record.get('last_counseling_date') or '',
            float(record.get('risk_score') or 0.0),
        )
        existing = conn.execute('SELECT 1 FROM students WHERE student_id = ?', (record['student_id'],)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE students SET name=?, department=?, year=?, semester=?, attendance_percentage=?, average_marks=?,
                active_backlogs=?, financial_support=?, estimated_risk=?, last_counseling_date=?, risk_score=?, updated_at=CURRENT_TIMESTAMP
                WHERE student_id=?
                """,
                (*data[1:12], data[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO students (student_id, name, department, year, semester, attendance_percentage,
                average_marks, active_backlogs, financial_support, estimated_risk, last_counseling_date, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )
        return get_student(record['student_id'])


def delete_student(student_id):
    with get_connection() as conn:
        conn.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
        return True


def get_dashboard_payload():
    with get_connection() as conn:
        students = [dict(row) for row in conn.execute('SELECT * FROM students ORDER BY name').fetchall()]
        total_students = len(students)
        requiring_attention = sum(1 for s in students if s['estimated_risk'] in ('Medium', 'High'))
        high_risk = sum(1 for s in students if s['estimated_risk'] == 'High')
        pending_cases = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE lower(status) != 'completed'"
        ).fetchone()[0]
        uploaded_count = sum(1 for student in students if student['data_source'] == 'uploaded')

        distribution = {'Low': 0, 'Medium': 0, 'High': 0}
        for student in students:
            distribution[student['estimated_risk']] += 1

        risk_distribution = [
            {'name': 'Low Risk', 'value': distribution.get('Low', 0)},
            {'name': 'Medium Risk', 'value': distribution.get('Medium', 0)},
            {'name': 'High Risk', 'value': distribution.get('High', 0)},
        ]

        attendance_data = [
            {
                'name': student['name'],
                'student_id': student['student_id'],
                'attendance': student['attendance_percentage'],
                'marks': student['average_marks'],
            }
            for student in students
            if student['attendance_percentage'] is not None
            and student['attendance_percentage'] >= 0
            and student['average_marks'] is not None
            and student['average_marks'] >= 0
        ][:12]

        session_rows = conn.execute(
            """
            SELECT substr(appointment_date, 1, 7) AS month, COUNT(*) AS sessions
            FROM appointments
            WHERE appointment_date IS NOT NULL AND appointment_date != ''
            GROUP BY substr(appointment_date, 1, 7)
            ORDER BY month
            """
        ).fetchall()
        counseling_trend = [
            {'month': row['month'], 'sessions': row['sessions']}
            for row in session_rows
        ][-6:]

        dept_risk = {}
        for student in students:
            dept_risk.setdefault(student['department'], {'Low': 0, 'Medium': 0, 'High': 0})
            dept_risk[student['department']][student['estimated_risk']] += 1

        department_data = [
            {'department': dept, 'low': values['Low'], 'medium': values['Medium'], 'high': values['High']}
            for dept, values in dept_risk.items()
        ]

        semester_scores = {}
        for student in students:
            semester = student['semester']
            marks = student['average_marks']
            if semester and semester > 0 and marks is not None and marks >= 0:
                semester_scores.setdefault(semester, []).append(marks)
        semester_performance = [
            {'semester': f'Sem {semester}', 'score': round(sum(scores) / len(scores), 1)}
            for semester, scores in sorted(semester_scores.items())
        ]

        flagged = [
            {'student_id': s['student_id'], 'name': s['name'], 'department': s['department'], 'risk': s['estimated_risk'], 'score': s['risk_score']}
            for s in students if s['estimated_risk'] in ('Medium', 'High')
        ][:5]

        follow_ups = [
            {
                'student_id': row['student_id'],
                'name': row['name'],
                'next_step': f"Follow-up due {row['follow_up_date']}",
            }
            for row in conn.execute(
                """
                SELECT c.student_id, s.name, c.follow_up_date
                FROM counseling_cases c
                JOIN students s ON s.student_id = c.student_id
                WHERE c.follow_up_date IS NOT NULL AND c.follow_up_date != ''
                ORDER BY c.follow_up_date
                """
            ).fetchall()
        ]
        follow_up_ids = {item['student_id'] for item in follow_ups}
        if len(follow_ups) < 4:
            candidates = conn.execute(
                """
                SELECT student_id, name, estimated_risk, risk_score, data_fields
                FROM students
                WHERE estimated_risk IN ('High', 'Medium')
                ORDER BY CASE estimated_risk WHEN 'High' THEN 0 ELSE 1 END, risk_score DESC
                """
            ).fetchall()
            for student in candidates:
                if student['student_id'] in follow_up_ids:
                    continue
                try:
                    fields = json.loads(student['data_fields'] or '{}')
                except (TypeError, json.JSONDecodeError):
                    fields = {}
                observed_factors = fields.get('_risk_factors') or []
                next_step = observed_factors[0] if observed_factors else 'Review available student indicators and support recommendations'
                follow_ups.append({
                    'student_id': student['student_id'],
                    'name': student['name'],
                    'next_step': f'{next_step}; follow-up not yet scheduled',
                })
                if len(follow_ups) == 4:
                    break

        appointments = [
            {
                'student': row['student_name'],
                'date': row['appointment_date'],
                'time': row['appointment_time'],
                'counselor': row['counselor_name'],
                'student_id': row['student_id'],
            }
            for row in conn.execute(
                """
                SELECT student_id, student_name, appointment_date, appointment_time, counselor_name
                FROM appointments
                WHERE lower(status) != 'completed'
                ORDER BY appointment_date, appointment_time
                LIMIT 4
                """
            ).fetchall()
        ]

        return {
            'summary': [
                {'label': 'Total Students', 'value': total_students, 'detail': f'{uploaded_count} from current uploaded dataset' if uploaded_count else 'Current student records'},
                {'label': 'Students Requiring Attention', 'value': requiring_attention, 'detail': 'Based on recorded student indicators'},
                {'label': 'High-Risk Students', 'value': high_risk, 'detail': 'Advisory estimates for human review'},
                {'label': 'Counseling Sessions Pending', 'value': pending_cases, 'detail': 'From saved appointments'},
            ],
            'risk_distribution': risk_distribution,
            'attendance_data': attendance_data,
            'counseling_trend': counseling_trend,
            'department_data': department_data,
            'semester_performance': semester_performance,
            'flagged_students': flagged,
            'follow_ups': follow_ups,
            'upcoming_appointments': appointments,
            'dataset': {
                'active': uploaded_count > 0,
                'student_count': uploaded_count,
                'data_source': 'uploaded' if uploaded_count else 'demo',
            },
        }


def get_case_data(student_id):
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM counseling_cases WHERE student_id = ?', (student_id,)).fetchone()
        if row:
            return dict(row)
        student = get_student(student_id)
        if student:
            fields = student.get('data_fields', {})
            concerns = []
            recommendations = []
            if student['attendance_percentage'] is not None and student['attendance_percentage'] >= 0 and student['attendance_percentage'] < 75:
                concerns.append(f"Attendance is {student['attendance_percentage']:g}%")
                recommendations.append('Offer a supportive attendance discussion and explore barriers')
            if student['average_marks'] is not None and student['average_marks'] >= 0 and student['average_marks'] < 60:
                concerns.append(f"Average marks are {student['average_marks']:g}")
                recommendations.append('Offer faculty mentoring or remedial academic support')
            if student['active_backlogs'] is not None and student['active_backlogs'] > 0:
                concerns.append(f"{student['active_backlogs']} active backlog(s)")
                recommendations.append('Create a personalized backlog recovery plan')
            if student.get('financial_difficulty') in ('1', 'yes', 'true'):
                concerns.append('Financial assistance indicator is marked as needing support')
                recommendations.append('Refer the student to the appropriate financial-aid office')
            for factor in fields.get('_risk_factors', []):
                if factor not in concerns:
                    concerns.append(factor)
                    recommendations.append(
                        'Discuss the reported indicator with the student and identify appropriate support'
                    )
            for column, value in fields.items():
                if column.startswith('_') or value is None or not str(value).strip():
                    continue
                if column in {
                    'student_id', 'name', 'department', 'year', 'semester',
                    'attendance_percentage', 'average_marks', 'active_backlogs',
                    'financial_difficulty', 'scholarship_status',
                    'previous_semester_gpa', 'assignment_completion',
                    'dropout_status', 'risk_status',
                }:
                    continue
                if column.lower() in {'risk', 'risk status', 'student status', 'academic status', 'retention status'}:
                    concerns.append(f"{column.replace('_', ' ').title()} is {value}")
            if not concerns:
                concerns.append('No elevated concerns were found in the available uploaded indicators')
                recommendations.append('Continue routine supportive check-ins')
            missing_fields = fields.get('_missing_fields', [])
            return {
                'student_id': student_id,
                'concerns': '; '.join(concerns),
                'recommendations': '; '.join(recommendations),
                'assigned_faculty': '',
                'appointment_date': '',
                'status': 'Pending',
                'follow_up_date': '',
                'notes': '',
                'missing_fields': missing_fields,
                'source': 'observed student data',
            }
        return None


def get_appointments():
    with get_connection() as conn:
        rows = conn.execute('SELECT * FROM appointments ORDER BY appointment_date ASC, appointment_time ASC').fetchall()
        return [dict(row) for row in rows]


def create_appointment(payload):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO appointments (student_id, student_name, counselor_name, appointment_date, appointment_time, session_type, status, follow_up)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload['student_id'],
                payload['student_name'],
                payload['counselor_name'],
                payload['appointment_date'],
                payload['appointment_time'],
                payload['session_type'],
                payload.get('status', 'Scheduled'),
                payload.get('follow_up', ''),
            ),
        )
        row = conn.execute('SELECT * FROM appointments ORDER BY id DESC LIMIT 1').fetchone()
        return dict(row)


def update_appointment_status(appointment_id, status):
    with get_connection() as conn:
        cursor = conn.execute(
            'UPDATE appointments SET status = ? WHERE id = ?',
            (status, appointment_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            'SELECT * FROM appointments WHERE id = ?',
            (appointment_id,),
        ).fetchone()
        return dict(row)


def get_model_history():
    with get_connection() as conn:
        rows = conn.execute('SELECT * FROM model_history ORDER BY id DESC LIMIT 5').fetchall()
        return [dict(row) for row in rows]


def save_model_history(model_name, version, dataset_name, metrics):
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO model_history (model_name, version, dataset_name, metrics) VALUES (?, ?, ?, ?)',
            (model_name, version, dataset_name, json.dumps(metrics)),
        )
        return True


def log_audit(action, details=''):
    with get_connection() as conn:
        conn.execute('INSERT INTO audit_logs (action, details) VALUES (?, ?)', (action, details))
        return True
