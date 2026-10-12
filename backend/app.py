import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_file, session
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from database import (
    create_appointment,
    get_connection,
    get_appointments,
    get_case_data,
    get_dashboard_payload,
    get_model_history,
    get_student,
    init_db,
    list_students,
    log_audit,
    save_model_history,
    seed_demo_data,
    upsert_student,
    delete_student,
    replace_student_dataset,
    update_student_assessments,
    _parse_year_sem,
    update_appointment_status,
)
from ml_pipeline import (
    TARGET_COLUMN_ALIASES,
    get_training_readiness,
    load_model,
    predict_student_risk,
    train_model_from_file,
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
UPLOAD_DIR = BASE_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
CORS(app)
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

init_db()
seed_demo_data()

HEADER_ALIASES = {
    'student_id': {'student_id', 'studentid', 'id', 'roll_no', 'roll_number', 'registration_number'},
    'attendance_percentage': {'attendance_percentage', 'attendance', 'attendance_percent', 'attendance_pct', 'attendance_rate'},
    'average_marks': {'average_marks', 'avg_marks', 'marks', 'internal_marks', 'average_score'},
    'active_backlogs': {'active_backlogs', 'backlogs', 'backlog_count', 'number_of_backlogs'},
    'financial_difficulty': {'financial_difficulty', 'financial_need', 'financial_support_needed'},
    'scholarship_status': {'scholarship_status', 'scholarship', 'scholarship_type'},
    'previous_semester_gpa': {
        'previous_semester_gpa', 'previous_gpa', 'previous_semester_cgpa',
        'cgpa', 'gpa', 'grade_point_average', 'cumulative_gpa', 'semester_gpa',
    },
    'assignment_completion': {'assignment_completion', 'assignment_completion_percentage', 'assignments_completed'},
    'dropout_status': {'dropout_status', 'dropout', 'discontinued', 'discontinued_status', 'historical_outcome'},
    'name': {'name', 'student_name', 'full_name'},
    'department': {'department', 'dept', 'program', 'course'},
    'year': {'year', 'academic_year', 'study_year', 'year_of_study'},
    'semester': {'semester', 'sem', 'term', 'current_semester', 'semester_number'},
    'year_sem': {'year_sem', 'year_semester', 'year_and_semester'},
    'financial_support': {'financial_support', 'financial_aid'},
    'last_counseling_date': {
        'last_counseling_date', 'counseling_date', 'last_counseling',
        'last_counselling_date', 'last_counselling', 'last_counselling_data',
        'counselling_date', 'counselling_data',
    },
    'risk_status': {
        'risk_status', 'risk', 'risk_category', 'risk_label', 'risk_level',
        'at_risk', 'status', 'outcome_status', 'student_outcome',
        'student_status', 'academic_status', 'retention_status',
    },
    'dropout_status': {'dropout', 'dropout_status', 'dropout_risk', 'historical_outcome', 'outcome'},
}

LOWER_VALUE_CONCERNING = {
    'attendance', 'attend', 'mark', 'marks', 'grade', 'grades', 'gpa',
    'score', 'performance', 'completion', 'complete', 'engagement',
    'participation', 'progress', 'credit',
}
HIGHER_VALUE_CONCERNING = {
    'backlog', 'backlogs', 'arrear', 'arrears', 'fail', 'fails', 'failure',
    'failures', 'absence', 'absences', 'absent', 'debt', 'overdue',
    'incident', 'incidents', 'warning', 'warnings', 'concern', 'missed', 'late',
}
STATUS_COLUMNS = TARGET_COLUMN_ALIASES | {'risk_status'}
HIGH_CONCERN_VALUES = {
    'high', 'critical', 'at risk', 'atrisk', 'dropout', 'dropped out',
    'failing', 'failed', 'poor', 'struggling', 'needs support',
}
MEDIUM_CONCERN_VALUES = {'medium', 'moderate', 'warning', 'declining', 'fair'}
LOW_CONCERN_VALUES = {
    'low', 'safe', 'on track', 'stable', 'good', 'excellent', 'retained',
    'active', 'enrolled', 'good standing',
}

OTP_TTL_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
BREVO_TIMEOUT_SECONDS = 10
LOGIN_OTP_CODES = {}
LOGIN_OTP_PENDING = set()
LOGIN_OTP_LOCK = threading.Lock()


def _send_login_otp(email, code):
    api_key = (os.getenv('BREVO_API_KEY') or '').strip()
    sender = (os.getenv('BREVO_FROM_EMAIL') or '').strip()
    if not api_key or not sender:
        raise RuntimeError(
            'Email OTP is not configured. Set BREVO_API_KEY and BREVO_FROM_EMAIL.'
        )

    request_body = json.dumps({
        'sender': {
            'email': sender,
            'name': os.getenv('BREVO_SENDER_NAME', 'DropoutGuard'),
        },
        'to': [{'email': email}],
        'subject': 'Your DropoutGuard verification code',
        'textContent': (
            f'Your verification code is {code}. It expires in 5 minutes. '
            'If you did not request this code, you can ignore this email.'
        ),
    }).encode('utf-8')
    brevo_request = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=request_body,
        headers={
            'accept': 'application/json',
            'api-key': api_key,
            'content-type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(brevo_request, timeout=BREVO_TIMEOUT_SECONDS):
        pass


def _requested_login_role(user_role):
    if user_role == 'Faculty':
        return 'Faculty'
    if user_role in {'Management', 'Administrator', 'Admin'}:
        return 'Management'
    return None


def _configured_login_user(email):
    with get_connection() as conn:
        row = conn.execute(
            'SELECT email, name, role FROM users WHERE lower(email) = ?',
            (email,),
        ).fetchone()

    if row:
        role = _requested_login_role(row['role'])
        return {'name': row['name'], 'role': role} if role else None

    faculty_emails = {
        value.strip().lower()
        for value in os.getenv('FACULTY_EMAILS', '').split(',')
        if value.strip()
    }
    management_emails = {
        value.strip().lower()
        for value in os.getenv('MANAGEMENT_EMAILS', '').split(',')
        if value.strip()
    }
    if email in faculty_emails and email not in management_emails:
        role = 'Faculty'
    elif email in management_emails and email not in faculty_emails:
        role = 'Management'
    else:
        return None

    display_name = re.sub(r'[^A-Za-z0-9]+', ' ', email.split('@', 1)[0]).strip().title()
    return {'name': display_name or email, 'role': role}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user'):
            return jsonify({'success': False, 'message': 'Sign in to access this resource.'}), 401
        return view(*args, **kwargs)
    return wrapped


def _optional_number(value, column, minimum=None, maximum=None):
    if pd.isna(value) or str(value).strip() == '':
        return None
    try:
        number = float(str(value).strip().replace(',', '').removesuffix('%'))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Column '{column}' must contain numeric values.") from exc
    if column in {'active_backlogs', 'year', 'semester'} and not number.is_integer():
        raise ValueError(f"Column '{column}' must contain whole numbers.")
    if minimum is not None and number < minimum or maximum is not None and number > maximum:
        raise ValueError(f"Values in '{column}' must be between {minimum} and {maximum}.")
    return int(number) if number.is_integer() else number


def _binary_indicator(value, column):
    if pd.isna(value) or str(value).strip() == '':
        return None
    normalized = str(value).strip().lower()
    mapping = {'1': '1', 'yes': '1', 'true': '1', '0': '0', 'no': '0', 'false': '0'}
    if normalized not in mapping:
        raise ValueError(f"Column '{column}' must contain Yes/No or 1/0 values.")
    return mapping[normalized]


def _assess_uploaded_row(row):
    factors = []
    score = 0.1
    recognized = False

    def add_factor(column, message, weight):
        nonlocal score, recognized
        recognized = True
        if message not in factors:
            factors.append(message)
            score += weight

    for column, value in row.items():
        if column in {'_risk_factors', '_missing_fields', '_assessment_source'} or not pd.api.types.is_scalar(value):
            continue
        if value is None or pd.isna(value) or not str(value).strip():
            continue

        key = str(column).lower()
        normalized = re.sub(r'[_\W]+', ' ', key).strip()
        words = set(normalized.split())
        text = str(value).strip().lower()
        if key in STATUS_COLUMNS:
            if text in HIGH_CONCERN_VALUES or text in {'1', 'yes', 'true'}:
                add_factor(column, f'{column.replace("_", " ")} is marked {value}', 0.65)
                continue
            if text in MEDIUM_CONCERN_VALUES:
                add_factor(column, f'{column.replace("_", " ")} is marked {value}', 0.3)
                continue
            if text in LOW_CONCERN_VALUES or text in {'0', 'no', 'false'}:
                recognized = True
                continue

        is_financial = 'financial' in words
        is_lower_indicator = any(word in words for word in LOWER_VALUE_CONCERNING)
        is_higher_indicator = any(word in words for word in HIGHER_VALUE_CONCERNING)
        if is_financial:
            if text in {
                'yes', 'true', '1', 'high', 'difficulty', 'hardship', 'need',
                'needs support', 'struggling',
            }:
                add_factor(column, 'Financial difficulty is indicated in the dataset', 0.15)
            elif text in {'no', 'false', '0', 'none', 'low'}:
                recognized = True
            continue

        if (
            text in HIGH_CONCERN_VALUES | MEDIUM_CONCERN_VALUES
            and not (is_lower_indicator and text in {'high', 'good', 'excellent'})
        ):
            add_factor(column, f'{column.replace("_", " ")} is marked {value}', 0.2)
            continue
        if is_lower_indicator and text in {'low', 'poor', 'below average', 'inadequate', 'declining'}:
            add_factor(column, f'{column.replace("_", " ")} is marked {value}', 0.25)
            continue
        if is_lower_indicator and text in {'high', 'good', 'excellent', 'above average', 'on track', 'pass'}:
            recognized = True
            continue

        try:
            number = float(text.replace(',', '').removesuffix('%'))
        except (TypeError, ValueError):
            if is_higher_indicator and text not in {'no', 'none', 'false', 'good', 'normal'}:
                add_factor(column, f'{column.replace("_", " ")} is marked {value}', 0.15)
            continue

        if is_lower_indicator:
            recognized = True
            if 'attendance' in words or 'attend' in words:
                if number < 75:
                    add_factor(column, f'{column.replace("_", " ")} is {number:g}%', 0.35 if number < 60 else 0.25)
            elif ('gpa' in words or 'grade' in words) and 0 <= number <= 10:
                if number < 6:
                    add_factor(column, f'{column.replace("_", " ")} is {number:g}', 0.25)
                elif number < 7:
                    add_factor(column, f'{column.replace("_", " ")} is {number:g}', 0.1)
            elif 0 <= number <= 100:
                if number < 60:
                    add_factor(
                        column,
                        f'{column.replace("_", " ")} is {number:g}',
                        0.35 if number < 40 else 0.2,
                    )
                elif number < 70:
                    add_factor(column, f'{column.replace("_", " ")} is {number:g}', 0.1)
            elif number < 0:
                add_factor(column, f'{column.replace("_", " ")} is {number:g}', 0.1)
        elif is_higher_indicator:
            recognized = True
            if number > 0:
                add_factor(
                    column,
                    f'{column.replace("_", " ")} is {number:g}',
                    0.25 if number >= 2 else 0.15,
                )

    if not recognized:
        return 'Medium', 0.5, ['No recognized risk indicators were found in the provided columns.'], 'insufficient recognized indicators'

    score = round(min(score, 0.95), 2)
    risk = 'High' if score >= 0.65 else 'Medium' if score >= 0.35 else 'Low'
    if not factors:
        factors.append('No elevated values were found in the recognized indicators.')
    return risk, score, factors, 'transparent rule-based estimate'


def _build_student_import_record(row, model_bundle):
    def number(field, minimum=None, maximum=None, fallback=-1):
        try:
            value = _optional_number(row.get(field), field, minimum, maximum)
        except ValueError:
            return fallback
        return fallback if value is None else value

    attendance = number('attendance_percentage', 0, 100)
    marks = number('average_marks', 0, 100)
    backlogs = number('active_backlogs', 0, 100)
    combined_year = 0
    combined_semester = 0
    combined_year_sem = row.get('year_sem')
    if combined_year_sem is not None and not pd.isna(combined_year_sem):
        combined_year, combined_semester = _parse_year_sem(combined_year_sem)
    year = number('year', 1, 20, fallback=combined_year)
    semester = number('semester', 1, 20, fallback=combined_semester)
    try:
        gpa = _optional_number(row.get('previous_semester_gpa'), 'previous_semester_gpa', 0, 10)
    except ValueError:
        gpa = None
    try:
        assignment = _optional_number(row.get('assignment_completion'), 'assignment_completion', 0, 100)
    except ValueError:
        assignment = None
    try:
        financial = _binary_indicator(row.get('financial_difficulty'), 'financial_difficulty')
    except ValueError:
        financial = None
    try:
        dropout = _binary_indicator(row.get('dropout_status'), 'dropout_status')
    except ValueError:
        dropout = None

    if 'scholarship_status' not in row or pd.isna(row.get('scholarship_status')):
        scholarship = None
    else:
        scholarship = str(row.get('scholarship_status')).strip()
        if scholarship.lower() in ('yes', 'true', '1'):
            scholarship = 'Scholarship'
        elif scholarship.lower() in ('no', 'false', '0'):
            scholarship = 'No Support'

    source_support = row.get('financial_support')
    if source_support is not None and not pd.isna(source_support) and str(source_support).strip():
        financial_support = str(source_support).strip()
    elif financial == '1':
        financial_support = 'Need-based Aid'
    elif scholarship is not None:
        financial_support = 'Scholarship' if scholarship != 'No Support' else 'No Support'
    else:
        financial_support = 'Not provided'

    last_counseling_date = row.get('last_counseling_date')
    if last_counseling_date is not None and not pd.isna(last_counseling_date):
        last_counseling_date = str(last_counseling_date).strip() or None
    else:
        last_counseling_date = None

    risk, score, factors, source = _assess_uploaded_row(row)
    model_features = set(model_bundle.get('feature_columns', [])) if model_bundle else set()
    if model_bundle and model_features and model_features.issubset(row):
        prediction = predict_student_risk(row, model_bundle)
        risk, score, source = prediction['risk_category'], prediction['score'], prediction['source']

    raw_fields = {}
    for key, value in row.items():
        if pd.isna(value):
            raw_fields[key] = None
        elif hasattr(value, 'item'):
            raw_fields[key] = value.item()
        else:
            raw_fields[key] = value
    raw_fields['_missing_fields'] = []
    raw_fields['_risk_factors'] = factors
    raw_fields['_assessment_source'] = source

    name = row.get('name')
    if name is None or pd.isna(name) or not str(name).strip():
        name = str(row['student_id'])
    department = row.get('department')
    if department is None or pd.isna(department) or not str(department).strip():
        department = 'Not provided'

    return {
        'student_id': str(row['student_id']).strip(),
        'name': str(name).strip(),
        'department': str(department).strip(),
        'year': year,
        'semester': semester,
        'last_counseling_date': last_counseling_date,
        'attendance_percentage': attendance,
        'average_marks': marks,
        'active_backlogs': backlogs,
        'financial_support': financial_support,
        'estimated_risk': risk,
        'risk_score': score,
        'financial_difficulty': financial,
        'scholarship_status': scholarship,
        'previous_semester_gpa': gpa,
        'assignment_completion': assignment,
        'dropout_status': dropout,
        'data_fields': raw_fields,
    }


def _risk_input_from_student(student):
    fields = student.get('data_fields', {})
    fixed_features = {
        'attendance_percentage': None if student['attendance_percentage'] < 0 else student['attendance_percentage'],
        'average_marks': None if student['average_marks'] < 0 else student['average_marks'],
        'active_backlogs': None if student['active_backlogs'] < 0 else student['active_backlogs'],
        'financial_difficulty': int(student['financial_difficulty']) if student.get('financial_difficulty') in ('0', '1') else None,
        'scholarship_status': student.get('scholarship_status'),
        'previous_semester_gpa': student.get('previous_semester_gpa'),
        'assignment_completion': student.get('assignment_completion'),
    }
    return {**fields, **fixed_features}, fields


def _refresh_assessments_with_model(model_bundle):
    assessments = []
    for student in list_students():
        features, fields = _risk_input_from_student(student)
        rule_risk, rule_score, factors, _ = _assess_uploaded_row(features)
        model_features = set(model_bundle.get('feature_columns', []))
        if model_features and model_features.issubset(features):
            prediction = predict_student_risk(features, model_bundle)
        else:
            prediction = {
                'risk_category': rule_risk,
                'score': rule_score,
                'source': 'transparent rule-based estimate',
            }
        fields['_assessment_source'] = prediction['source']
        fields['_risk_factors'] = factors
        assessments.append({
            'student_id': student['student_id'],
            'risk_category': prediction['risk_category'],
            'score': prediction['score'],
            'data_fields': fields,
        })
    update_student_assessments(assessments)


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'student-support-api', 'timestamp': datetime.now(timezone.utc).isoformat()})


@app.route('/api/auth/session', methods=['GET'])
def current_login_session():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'user': None}), 401
    return jsonify({'success': True, 'user': user})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/request-otp', methods=['POST'])
def request_login_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    purpose = data.get('purpose', 'login')
    name = (data.get('name') or '').strip()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return jsonify({'success': False, 'message': 'Enter a valid email address.'}), 400
    if purpose not in {'login', 'register'}:
        return jsonify({'success': False, 'message': 'Choose sign in or registration.'}), 400

    login_user = _configured_login_user(email)
    if purpose == 'login' and not login_user:
        return jsonify({
            'success': True,
            'message': 'No account exists for this email. Register your email first.',
        }), 404
    if purpose == 'register' and login_user:
        return jsonify({
            'success': False,
            'message': 'An account already exists for this email. Sign in instead.',
        }), 409
    if purpose == 'register' and not name:
        return jsonify({'success': False, 'message': 'Enter your name to register.'}), 400

    now = time.monotonic()
    with LOGIN_OTP_LOCK:
        previous = LOGIN_OTP_CODES.get(email)
        if email in LOGIN_OTP_PENDING or (
            previous and now - previous['sent_at'] < OTP_RESEND_SECONDS
        ):
            return jsonify({
                'success': False,
                'message': 'Please wait before requesting another code.',
                'retry_after': max(
                    1,
                    int(OTP_RESEND_SECONDS - (now - previous['sent_at']))
                    if previous else OTP_RESEND_SECONDS,
                ),
            }), 429
        LOGIN_OTP_PENDING.add(email)

    code = f'{secrets.randbelow(1_000_000):06d}'
    try:
        _send_login_otp(email, code)
    except RuntimeError as exc:
        with LOGIN_OTP_LOCK:
            LOGIN_OTP_PENDING.discard(email)
        app.logger.error('Could not send sign-in code: %s', exc)
        return jsonify({
            'success': False,
            'message': 'Brevo email is not configured. Set BREVO_API_KEY and BREVO_FROM_EMAIL in backend/.env, then restart the backend.',
        }), 503
    except urllib.error.HTTPError as exc:
        with LOGIN_OTP_LOCK:
            LOGIN_OTP_PENDING.discard(email)
        if exc.code in {401, 403}:
            app.logger.error('Brevo rejected the API credentials with HTTP %s.', exc.code)
            message = 'Brevo rejected the API key. Check that BREVO_API_KEY is an active Brevo API key, not an SMTP key.'
        else:
            app.logger.error('Brevo rejected the email request with HTTP %s.', exc.code)
            message = f'Brevo rejected the email request (HTTP {exc.code}). Check the verified sender and Brevo email settings.'
        return jsonify({'success': False, 'message': message}), 503
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        with LOGIN_OTP_LOCK:
            LOGIN_OTP_PENDING.discard(email)
        app.logger.exception('Brevo email delivery failed.')
        return jsonify({
            'success': False,
            'message': 'Brevo email delivery failed. Check the API key and verify that BREVO_FROM_EMAIL is an approved sender in Brevo.',
        }), 503

    with LOGIN_OTP_LOCK:
        LOGIN_OTP_PENDING.discard(email)
        sent_at = time.monotonic()
        LOGIN_OTP_CODES[email] = {
            'digest': hmac.new(
                app.config['SECRET_KEY'].encode(),
                f'{email}:{code}'.encode(),
                hashlib.sha256,
            ).hexdigest(),
            'expires_at': sent_at + OTP_TTL_SECONDS,
            'sent_at': sent_at,
            'attempts': 0,
            'role': login_user['role'] if login_user else 'Faculty',
            'name': login_user['name'] if login_user else name,
            'purpose': purpose,
        }

    return jsonify({
        'success': True,
        'message': (
            'A verification code was sent to your email address.'
            if purpose == 'register'
            else 'A sign-in code was sent to your email address.'
        ),
    })


@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_login_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    purpose = data.get('purpose', 'login')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or not re.fullmatch(r'\d{6}', code):
        return jsonify({'success': False, 'message': 'Enter a valid email address and six-digit code.'}), 400
    if purpose not in {'login', 'register'}:
        return jsonify({'success': False, 'message': 'Choose sign in or registration.'}), 400

    now = time.monotonic()
    with LOGIN_OTP_LOCK:
        challenge = LOGIN_OTP_CODES.get(email)
        if not challenge or challenge['expires_at'] <= now or challenge['purpose'] != purpose:
            LOGIN_OTP_CODES.pop(email, None)
            return jsonify({'success': False, 'message': 'This code is invalid or expired. Request a new code.'}), 401
        if challenge['attempts'] >= OTP_MAX_ATTEMPTS:
            LOGIN_OTP_CODES.pop(email, None)
            return jsonify({'success': False, 'message': 'Too many incorrect attempts. Request a new code.'}), 429

        submitted_digest = hmac.new(
            app.config['SECRET_KEY'].encode(),
            f'{email}:{code}'.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(challenge['digest'], submitted_digest):
            challenge['attempts'] += 1
            return jsonify({'success': False, 'message': 'That code is incorrect. Check it and try again.'}), 401

        LOGIN_OTP_CODES.pop(email, None)

    if purpose == 'register':
        try:
            with get_connection() as conn:
                existing = conn.execute(
                    'SELECT email, name, role FROM users WHERE lower(email) = ?',
                    (email,),
                ).fetchone()
                if existing:
                    return jsonify({
                        'success': False,
                        'message': 'An account already exists for this email. Sign in instead.',
                    }), 409
                conn.execute(
                    'INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, ?, ?)',
                    (
                        email,
                        challenge['name'],
                        'Faculty',
                        generate_password_hash(secrets.token_urlsafe(48)),
                    ),
                )
        except sqlite3.IntegrityError:
            return jsonify({
                'success': False,
                'message': 'An account already exists for this email. Sign in instead.',
            }), 409

    user = {
        'email': email,
        'name': challenge['name'],
        'role': challenge['role'],
    }
    session.clear()
    session.permanent = True
    session['user'] = user
    return jsonify({
        'success': True,
        'user': user,
    })


@app.route('/api/login', methods=['POST'])
def login():
    return jsonify({
        'success': False,
        'message': 'Password sign-in is disabled. Use email one-time-code sign-in.',
    }), 410


@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    return jsonify(get_dashboard_payload())


@app.route('/api/students', methods=['GET', 'POST'])
@login_required
def students():
    if request.method == 'GET':
        search = request.args.get('search', '')
        department = request.args.get('department', 'All')
        year = request.args.get('year', 'All')
        semester = request.args.get('semester', 'All')
        risk = request.args.get('risk', 'All')
        students_list = list_students(search=search, department=department, year=year, semester=semester, risk=risk)
        return jsonify({'students': students_list})

    payload = request.get_json(silent=True) or {}
    if not payload:
        return jsonify({'success': False, 'message': 'Student payload is required'}), 400
    student = upsert_student(payload)
    log_audit('student_saved', f"student_id={payload.get('student_id')}")
    return jsonify({'success': True, 'student': student})


@app.route('/api/students/<student_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def student_detail(student_id):
    if request.method == 'GET':
        row = get_student(student_id)
        if not row:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        record = dict(row)
        record['recommendations'] = get_case_data(student_id)
        return jsonify({'student': record})

    if request.method == 'PUT':
        payload = request.get_json(silent=True) or {}
        payload['student_id'] = student_id
        updated = upsert_student(payload)
        return jsonify({'success': True, 'student': updated})

    delete_student(student_id)
    log_audit('student_deleted', f'student_id={student_id}')
    return jsonify({'success': True, 'message': 'Student deleted'})


@app.route('/api/recommendations/<student_id>', methods=['GET'])
@login_required
def recommendations(student_id):
    case = get_case_data(student_id)
    if case is None:
        return jsonify({'success': False, 'message': 'No recommendation found'}), 404
    return jsonify(case)


@app.route('/api/appointments', methods=['GET', 'POST'])
@login_required
def appointments():
    if request.method == 'GET':
        return jsonify({'appointments': get_appointments()})

    payload = request.get_json(silent=True) or {}
    if not payload:
        return jsonify({'success': False, 'message': 'Appointment details are required'}), 400
    created = create_appointment(payload)
    log_audit('appointment_created', f"student_id={payload.get('student_id')}")
    return jsonify({'success': True, 'appointment': created})


@app.route('/api/appointments/<int:appointment_id>', methods=['PATCH'])
@login_required
def update_appointment(appointment_id):
    payload = request.get_json(silent=True) or {}
    status = payload.get('status')
    if status not in {'Scheduled', 'Pending', 'Completed'}:
        return jsonify({
            'success': False,
            'message': 'Status must be Scheduled, Pending, or Completed.',
        }), 400

    updated = update_appointment_status(appointment_id, status)
    if updated is None:
        return jsonify({'success': False, 'message': 'Appointment not found.'}), 404

    log_audit('appointment_status_updated', f"appointment_id={appointment_id}; status={status}")
    return jsonify({'success': True, 'appointment': updated})


@app.route('/api/upload-csv', methods=['POST'])
@login_required
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'CSV file is required'}), 400

    csv_file = request.files['file']
    if not csv_file or csv_file.filename == '':
        return jsonify({'success': False, 'message': 'CSV file is required'}), 400

    if not csv_file.filename.lower().endswith('.csv'):
        return jsonify({'success': False, 'message': 'Only CSV files are allowed'}), 400

    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig', sep=None, engine='python')
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        return jsonify({'success': False, 'message': f'Could not read this CSV. Check its encoding and delimiter: {exc}'}), 400

    if df.empty:
        return jsonify({'success': False, 'message': 'The uploaded file is empty'}), 400

    original_columns = [str(column) for column in df.columns]
    if any(not column.lstrip('\ufeff').strip() for column in original_columns):
        return jsonify({
            'success': False,
            'message': 'Every CSV column needs a non-empty header.',
        }), 400

    normalized_columns = []
    for column in original_columns:
        normalized = re.sub(r'[^a-z0-9]+', '_', column.lstrip('\ufeff').strip().lower()).strip('_')
        alias = next((canonical for canonical, aliases in HEADER_ALIASES.items() if normalized in aliases), normalized)
        normalized_columns.append(alias)

    if len(normalized_columns) != len(set(normalized_columns)):
        return jsonify({
            'success': False,
            'message': 'Two or more CSV headers map to the same field. Rename the duplicate columns and try again.',
        }), 400

    df.columns = normalized_columns

    if df.dropna(how='all').empty:
        return jsonify({
            'success': False,
            'message': 'Add at least one data value to the CSV before uploading it.',
            'received_columns': original_columns,
        }), 400

    if 'student_id' not in df.columns:
        df.insert(0, 'student_id', [f'CSV-{index:04d}' for index in range(1, len(df) + 1)])
    else:
        df['student_id'] = df['student_id'].astype('string').str.strip()
        missing_ids = df['student_id'].isna() | (df['student_id'] == '')
        df.loc[missing_ids, 'student_id'] = [
            f'CSV-{index:04d}' for index in df.index[missing_ids]
        ]

    if df.duplicated(subset=['student_id']).any():
        duplicates = df.loc[df.duplicated(subset=['student_id'], keep=False), 'student_id'].tolist()
        return jsonify({'success': False, 'message': 'Duplicate student IDs found', 'duplicates': duplicates}), 400

    rows = df.to_dict(orient='records')
    try:
        model_bundle = load_model()
        imported_students = [
            _build_student_import_record(row, model_bundle)
            for row in rows
        ]
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

    target_column, feature_columns, missing_training_columns = get_training_readiness(df.columns)
    feature_columns = [column for column in feature_columns if df[column].notna().any()]
    if target_column and not feature_columns and 'student data columns' not in missing_training_columns:
        missing_training_columns.append('student data columns')
    training_ready = bool(feature_columns) and not missing_training_columns
    active_dataset_path = UPLOAD_DIR / 'active_dataset.csv'
    legacy_dataset_path = UPLOAD_DIR / 'uploaded_students.csv'
    existing_upload = active_dataset_path.exists() or legacy_dataset_path.exists()
    replace_existing = request.form.get('replace_existing', '').lower() == 'true'
    if existing_upload and not replace_existing:
        return jsonify({
            'success': False,
            'replace_required': True,
            'message': 'A validated dataset already exists. Confirm replacement to upload this file.',
        }), 409

    temporary_path = UPLOAD_DIR / 'active_dataset.csv.tmp'
    try:
        df.to_csv(temporary_path, index=False)
        replace_student_dataset(imported_students)
        os.replace(temporary_path, active_dataset_path)
    except (OSError, ValueError) as exc:
        if temporary_path.exists():
            temporary_path.unlink()
        return jsonify({'success': False, 'message': f'Could not save the uploaded dataset: {exc}'}), 500
    log_audit('dataset_imported', f'rows={len(imported_students)}')

    missing_summary = {column: int(df[column].isna().sum()) for column in df.columns}

    preview_frame = df.head(5).astype(object)
    preview_frame = preview_frame.where(pd.notna(preview_frame), None)
    preview = preview_frame.to_dict(orient='records')
    return jsonify({
        'success': True,
        'valid': True,
        'message': 'Dataset validated successfully',
        'rows': len(df),
        'students_imported': len(imported_students),
        'data_source': 'uploaded dataset',
        'columns': list(df.columns),
        'original_columns': original_columns,
        'preview': preview,
        'missing_summary': missing_summary,
        'training_ready': training_ready,
        'missing_training_columns': missing_training_columns,
        'message': (
            'Dataset analyzed and ready for model training.'
            if training_ready
            else 'Dataset analyzed. Add a risk_status, dropout_status, or outcome column to enable model training.'
        ),
    })


@app.route('/api/csv-template', methods=['GET'])
@login_required
def csv_template():
    return send_file(
        BASE_DIR / 'csv_template.csv',
        mimetype='text/csv',
        as_attachment=True,
        download_name='student_dataset_template.csv',
    )


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({'success': False, 'message': 'CSV exceeds the 16 MB upload limit.'}), 413


@app.route('/api/train-model', methods=['POST'])
@login_required
def train_model():
    try:
        active_dataset_path = UPLOAD_DIR / 'active_dataset.csv'
        legacy_dataset_path = UPLOAD_DIR / 'uploaded_students.csv'
        dataset_path = active_dataset_path if active_dataset_path.exists() else legacy_dataset_path
        if not dataset_path.exists():
            return jsonify({'success': False, 'message': 'Upload a dataset before training the model'}), 400
        metrics = train_model_from_file(str(dataset_path))
        model_bundle = load_model()
        if model_bundle is not None:
            _refresh_assessments_with_model(model_bundle)
        save_model_history('RandomForestClassifier', 'v1.0.0', dataset_path.name, metrics)
        log_audit('model_trained', json.dumps(metrics))
        return jsonify({'success': True, 'message': 'Model trained successfully', 'metrics': metrics})
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400


@app.route('/api/model', methods=['GET'])
@login_required
def model_info():
    history = get_model_history()
    if not history:
        return jsonify({'exists': False, 'message': 'No trained model yet. Please upload and train a dataset.'})
    for model_version in history:
        model_version['metrics'] = json.loads(model_version['metrics'])
    return jsonify({'exists': True, 'history': history, 'latest': history[0]})


@app.route('/api/risk/<student_id>', methods=['GET'])
@login_required
def risk(student_id):
    student = get_student(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    fields = student.get('data_fields', {})
    risk_factors = fields.get('_risk_factors', [])
    if not risk_factors:
        if 0 <= student['attendance_percentage'] < 75:
            risk_factors.append(f"Attendance is {student['attendance_percentage']:g}%")
        if 0 <= student['average_marks'] < 60:
            risk_factors.append(f"Average marks are {student['average_marks']:g}")
        if student['active_backlogs'] >= 2:
            risk_factors.append(f"{student['active_backlogs']} active backlogs")
        if student.get('financial_difficulty') in ('1', 'yes', 'true'):
            risk_factors.append('Financial difficulty is indicated in the dataset')
    result = {
        'student_id': student_id,
        'risk_category': student['estimated_risk'],
        'score': student['risk_score'],
        'source': fields.get('_assessment_source', 'staff-recorded advisory estimate'),
        'risk_factors': risk_factors,
        'missing_fields': fields.get('_missing_fields', []),
    }
    return jsonify(result)


@app.route('/api/reports', methods=['GET'])
@login_required
def reports():
    board = get_dashboard_payload()
    return jsonify({
        'overall_summary': board['summary'],
        'risk_distribution': board['risk_distribution'],
        'students_requiring_followup': board['follow_ups'],
        'upcoming_sessions': board['upcoming_appointments'],
        'dataset': board['dataset'],
        'generated_at': datetime.now(timezone.utc).isoformat(),
    })


@app.route('/api/reports/export.csv', methods=['GET'])
@login_required
def export_report_csv():
    board = get_dashboard_payload()
    generated_at = datetime.now(timezone.utc).isoformat()
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['section', 'item', 'value', 'details'])
    writer.writerow(['Report', 'Generated at', generated_at, ''])
    writer.writerow([
        'Dataset',
        'Source',
        board['dataset']['data_source'],
        f"{board['dataset']['student_count']} uploaded student records",
    ])

    for metric in board['summary']:
        writer.writerow(['Summary', metric['label'], metric['value'], metric['detail']])
    for risk_level in board['risk_distribution']:
        writer.writerow(['Risk distribution', risk_level['name'], risk_level['value'], 'Students'])
    for follow_up in board['follow_ups']:
        writer.writerow([
            'Follow-up',
            follow_up['student_id'],
            follow_up['name'],
            follow_up['next_step'],
        ])
    for appointment in get_appointments():
        writer.writerow([
            'Appointment',
            appointment['student_name'],
            appointment['status'],
            f"{appointment['appointment_date']} {appointment['appointment_time']} · {appointment['session_type']} · {appointment['counselor_name']}",
        ])

    report_file = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    return send_file(
        report_file,
        mimetype='text/csv',
        as_attachment=True,
        download_name='student_support_report.csv',
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
