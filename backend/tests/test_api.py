import io
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import app
import ml_pipeline
import database as database_module


def authenticated_client():
    client = app.test_client()
    with client.session_transaction() as login_session:
        login_session['user'] = {
            'email': 'admin@college.edu',
            'name': 'Dr. Meera Singh',
            'role': 'Management',
        }
    return client


def test_health_endpoint():
    client = app.test_client()
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'


def test_login_endpoint():
    client = app.test_client()
    response = client.post('/api/login', json={'email': 'admin@college.edu', 'password': 'Admin@123'})
    assert response.status_code == 410
    assert 'email one-time-code' in response.json['message']


def test_student_data_requires_a_login_session():
    response = app.test_client().get('/api/students')
    assert response.status_code == 401


def test_email_otp_login_for_faculty_and_management(monkeypatch):
    sent_codes = {}
    monkeypatch.setattr(app_module, '_send_login_otp', lambda email, code: sent_codes.update({email: code}))
    app_module.LOGIN_OTP_CODES.clear()
    client = app.test_client()

    for email, role, expected_name in [
        ('faculty@college.edu', 'Faculty', 'Prof. Aditi Nair'),
        ('admin@college.edu', 'Management', 'Dr. Meera Singh'),
    ]:
        response = client.post('/api/auth/request-otp', json={'email': email})
        assert response.status_code == 200
        assert email in sent_codes
        cooldown = client.post('/api/auth/request-otp', json={'email': email})
        assert cooldown.status_code == 429

        response = client.post('/api/auth/verify-otp', json={
            'email': email,
            'code': sent_codes[email],
        })
        assert response.status_code == 200
        assert response.json['user'] == {'email': email, 'name': expected_name, 'role': role}
        assert client.get('/api/auth/session').json['user'] == response.json['user']


def test_email_otp_login_for_configured_staff_emails(monkeypatch):
    sent_codes = {}
    monkeypatch.setenv('FACULTY_EMAILS', 'faculty.member@gmail.com')
    monkeypatch.setenv('MANAGEMENT_EMAILS', 'manager.member@gmail.com')
    monkeypatch.setattr(app_module, '_send_login_otp', lambda email, code: sent_codes.update({email: code}))
    app_module.LOGIN_OTP_CODES.clear()
    client = app.test_client()

    response = client.post('/api/auth/request-otp', json={'email': 'faculty.member@gmail.com'})
    assert response.status_code == 200
    assert 'faculty.member@gmail.com' in sent_codes
    response = client.post('/api/auth/verify-otp', json={
        'email': 'faculty.member@gmail.com',
        'code': sent_codes['faculty.member@gmail.com'],
    })
    assert response.status_code == 200
    assert response.json['user'] == {
        'email': 'faculty.member@gmail.com',
        'name': 'Faculty Member',
        'role': 'Faculty',
    }

    unregistered_email = client.post('/api/auth/request-otp', json={'email': 'unknown@gmail.com'})
    assert unregistered_email.status_code == 404
    assert len(sent_codes) == 1


def test_register_email_then_sign_in_as_faculty(tmp_path, monkeypatch):
    sent_codes = {}
    monkeypatch.setattr(database_module, 'DB_PATH', tmp_path / 'registration.db')
    database_module.init_db()
    database_module.seed_demo_data()
    monkeypatch.setenv('FACULTY_EMAILS', '')
    monkeypatch.setenv('MANAGEMENT_EMAILS', '')
    monkeypatch.setattr(app_module, '_send_login_otp', lambda email, code: sent_codes.update({email: code}))
    app_module.LOGIN_OTP_CODES.clear()
    client = app.test_client()

    response = client.post('/api/auth/request-otp', json={
        'email': 'new.faculty@gmail.com',
        'name': 'New Faculty',
        'purpose': 'register',
    })
    assert response.status_code == 200
    response = client.post('/api/auth/verify-otp', json={
        'email': 'new.faculty@gmail.com',
        'code': sent_codes['new.faculty@gmail.com'],
        'purpose': 'register',
    })
    assert response.status_code == 200
    assert response.json['user'] == {
        'email': 'new.faculty@gmail.com',
        'name': 'New Faculty',
        'role': 'Faculty',
    }

    with database_module.get_connection() as conn:
        user = conn.execute(
            'SELECT email, name, role FROM users WHERE email = ?',
            ('new.faculty@gmail.com',),
        ).fetchone()
    assert tuple(user) == ('new.faculty@gmail.com', 'New Faculty', 'Faculty')

    client.post('/api/auth/logout')
    response = client.post('/api/auth/request-otp', json={'email': 'new.faculty@gmail.com'})
    assert response.status_code == 200
    response = client.post('/api/auth/verify-otp', json={
        'email': 'new.faculty@gmail.com',
        'code': sent_codes['new.faculty@gmail.com'],
    })
    assert response.status_code == 200
    assert response.json['user']['role'] == 'Faculty'


def test_email_otp_login_limits_attempts(monkeypatch):
    sent_codes = {}
    monkeypatch.setattr(app_module, '_send_login_otp', lambda email, code: sent_codes.update({email: code}))
    app_module.LOGIN_OTP_CODES.clear()
    client = app.test_client()

    client.post('/api/auth/request-otp', json={'email': 'faculty@college.edu'})
    wrong_code = '000000' if sent_codes['faculty@college.edu'] != '000000' else '000001'
    for _ in range(app_module.OTP_MAX_ATTEMPTS):
        response = client.post('/api/auth/verify-otp', json={
            'email': 'faculty@college.edu',
            'code': wrong_code,
        })
        assert response.status_code == 401

    response = client.post('/api/auth/verify-otp', json={
        'email': 'faculty@college.edu',
        'code': sent_codes['faculty@college.edu'],
    })
    assert response.status_code == 429
    assert 'too many incorrect attempts' in response.json['message'].lower()


def test_email_otp_reports_brevo_delivery_failure(monkeypatch):
    app_module.LOGIN_OTP_CODES.clear()

    def fail_to_send(email, code):
        raise app_module.urllib.error.URLError('Brevo request failed')

    monkeypatch.setattr(app_module, '_send_login_otp', fail_to_send)

    response = app.test_client().post(
        '/api/auth/request-otp',
        json={'email': 'faculty@college.edu'},
    )

    assert response.status_code == 503
    assert 'brevo email delivery failed' in response.json['message'].lower()
    assert 'faculty@college.edu' not in app_module.LOGIN_OTP_CODES
    assert 'faculty@college.edu' not in app_module.LOGIN_OTP_PENDING


def test_email_otp_reports_brevo_unauthorized_api_key(monkeypatch):
    app_module.LOGIN_OTP_CODES.clear()

    def reject_credentials(email, code):
        raise app_module.urllib.error.HTTPError(
            'https://api.brevo.com/v3/smtp/email',
            401,
            'Unauthorized',
            hdrs=None,
            fp=io.BytesIO(),
        )

    monkeypatch.setattr(app_module, '_send_login_otp', reject_credentials)

    response = app.test_client().post(
        '/api/auth/request-otp',
        json={'email': 'faculty@college.edu'},
    )

    assert response.status_code == 503
    assert 'brevo rejected the api key' in response.json['message'].lower()
    assert 'faculty@college.edu' not in app_module.LOGIN_OTP_CODES
    assert 'faculty@college.edu' not in app_module.LOGIN_OTP_PENDING


def test_brevo_otp_uses_https_api(monkeypatch):
    calls = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        calls['url'] = request.full_url
        calls['method'] = request.method
        calls['api_key'] = request.get_header('Api-key')
        calls['content_type'] = request.get_header('Content-type')
        calls['timeout'] = timeout
        calls['body'] = app_module.json.loads(request.data)
        return FakeResponse()

    monkeypatch.setenv('BREVO_API_KEY', 'test-api-key')
    monkeypatch.setenv('BREVO_FROM_EMAIL', 'verified@example.com')
    monkeypatch.setenv('BREVO_SENDER_NAME', 'Test Sender')
    monkeypatch.setattr(app_module.urllib.request, 'urlopen', fake_urlopen)

    app_module._send_login_otp('faculty@example.com', '123456')

    assert calls['url'] == 'https://api.brevo.com/v3/smtp/email'
    assert calls['method'] == 'POST'
    assert calls['api_key'] == 'test-api-key'
    assert calls['content_type'] == 'application/json'
    assert calls['timeout'] == app_module.BREVO_TIMEOUT_SECONDS
    assert calls['body']['sender'] == {
        'email': 'verified@example.com',
        'name': 'Test Sender',
    }
    assert calls['body']['to'] == [{'email': 'faculty@example.com'}]
    assert calls['body']['subject'] == 'Your DropoutGuard verification code'
    assert '123456' in calls['body']['textContent']


def test_brevo_otp_requires_api_key(monkeypatch):
    monkeypatch.delenv('BREVO_API_KEY', raising=False)
    monkeypatch.setenv('BREVO_FROM_EMAIL', 'verified@example.com')

    try:
        app_module._send_login_otp('faculty@example.com', '123456')
    except RuntimeError as exc:
        assert 'BREVO_API_KEY' in str(exc)
    else:
        raise AssertionError('Expected missing Brevo API key to prevent email delivery.')


def test_students_endpoint():
    client = authenticated_client()
    response = client.get('/api/students')
    assert response.status_code == 200
    assert len(response.json['students']) > 0


def test_appointment_status_can_be_updated_and_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, 'DB_PATH', tmp_path / 'appointments.db')
    database_module.init_db()
    appointment = database_module.create_appointment({
        'student_id': 'STU-7001',
        'student_name': 'Report Student',
        'counselor_name': 'Test Counselor',
        'appointment_date': '2026-10-20',
        'appointment_time': '10:00',
        'session_type': 'Academic counseling',
        'status': 'Scheduled',
    })
    client = authenticated_client()

    response = client.patch(
        f"/api/appointments/{appointment['id']}",
        json={'status': 'Completed'},
    )
    assert response.status_code == 200
    assert response.json['appointment']['status'] == 'Completed'

    invalid_response = client.patch(
        f"/api/appointments/{appointment['id']}",
        json={'status': 'Invalid'},
    )
    assert invalid_response.status_code == 400

    missing_response = client.patch('/api/appointments/99999', json={'status': 'Pending'})
    assert missing_response.status_code == 404


def test_report_csv_download_contains_generated_summaries_not_student_dump(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, 'DB_PATH', tmp_path / 'reports.db')
    database_module.init_db()
    client = authenticated_client()

    response = client.get('/api/reports/export.csv')

    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'attachment' in response.headers['Content-Disposition']
    assert 'student_support_report.csv' in response.headers['Content-Disposition']
    report = response.data.decode('utf-8-sig')
    assert 'section,item,value,details' in report
    assert 'Total Students' in report
    assert 'Risk distribution' in report
    assert 'STU-1001' not in report


def test_csv_upload_normalizes_headers_and_validates(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: None)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    client = authenticated_client()
    csv_data = b'\xef\xbb\xbfStudent ID,Attendance %,Average Marks,Backlogs,Financial Difficulty,Scholarship,Previous Semester GPA,Assignment Completion,Dropout Status\nSTU-1001,91,88,1,0,scholarship,8.6,92,0\nSTU-1002,72,69,2,1,none,6.9,76,1\n'
    response = client.post('/api/upload-csv', data={'file': (io.BytesIO(csv_data), 'demo.csv')}, content_type='multipart/form-data')
    assert response.status_code == 200
    assert response.json['valid'] is True
    assert response.json['training_ready'] is True
    assert 'attendance_percentage' in response.json['columns']


def test_feature_dataset_can_upload_without_historical_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: None)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    client = authenticated_client()
    csv_data = b'Student ID,Attendance %,Average Marks\nSTU-2001,82,77\n'
    response = client.post('/api/upload-csv', data={'file': (io.BytesIO(csv_data), 'students.csv')}, content_type='multipart/form-data')
    assert response.status_code == 200
    assert response.json['valid'] is True
    assert response.json['training_ready'] is False
    assert response.json['missing_training_columns'] == ['risk_status or outcome']
    assert 'analyzed' in response.json['message'].lower()


def test_csv_upload_analyzes_custom_columns_without_student_id(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    imported = []
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: imported.extend(records))
    client = authenticated_client()
    csv_data = (
        b'Maths Marks,Engagement Score,Advisor Note\n'
        b'42,35,Needs support\n'
        b'91,95,On track\n'
    )

    response = client.post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'custom.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert response.json['training_ready'] is False
    assert response.json['rows'] == 2
    assert imported[0]['student_id'] == 'CSV-0001'
    assert imported[0]['estimated_risk'] == 'High'
    assert imported[0]['data_fields']['maths_marks'] == 42
    assert imported[0]['data_fields']['engagement_score'] == 35
    assert imported[1]['estimated_risk'] == 'Low'


def test_csv_upload_maps_year_sem_and_last_counselling_data(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    monkeypatch.setattr(database_module, 'DB_PATH', tmp_path / 'directory.db')
    database_module.init_db()
    csv_data = (
        b'Student ID,Year,Sem,Last Counselling Data\n'
        b'STU-4001,3,5,2026-09-12\n'
    )

    response = authenticated_client().post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'counselling.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    students_response = authenticated_client().get('/api/students')
    imported_student = next(
        student for student in students_response.json['students']
        if student['student_id'] == 'STU-4001'
    )
    assert imported_student['year'] == 3
    assert imported_student['semester'] == 5
    assert imported_student['last_counseling_date'] == '2026-09-12'


def test_csv_upload_parses_combined_year_sem_header(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    imported = []
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: imported.extend(records))
    csv_data = b'Student ID,Year Sem\nSTU-4002,Year 2 / Sem 4\n'

    response = authenticated_client().post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'year-sem.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert imported[0]['year'] == 2
    assert imported[0]['semester'] == 4


def test_csv_upload_parses_roman_numeral_year_sem(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    imported = []
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: imported.extend(records))
    csv_data = b'Student ID,Year Sem\nSTU-4003,III Year / Sem 5\n'

    response = authenticated_client().post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'roman-year-sem.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert imported[0]['year'] == 3
    assert imported[0]['semester'] == 5


def test_legacy_uploaded_directory_fields_are_read_from_raw_dataset():
    student = database_module._student_record({
        'year': 0,
        'semester': 0,
        'last_counseling_date': None,
        'data_fields': '{"year_sem": "III Year / Sem 5", "last_counseling": "2026-09-12"}',
    })

    assert student['year'] == 3
    assert student['semester'] == 5
    assert student['last_counseling_date'] == '2026-09-12'


def test_csv_upload_keeps_categorical_values_in_known_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    imported = []
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: imported.extend(records))
    csv_data = b'Student Name,Attendance,Comments\nStudent A,Low,Needs support\nStudent B,High,On track\n'

    response = authenticated_client().post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'categorical.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert imported[0]['estimated_risk'] == 'Medium'
    assert imported[1]['estimated_risk'] == 'Low'
    assert imported[0]['data_fields']['attendance_percentage'] == 'Low'


def test_csv_upload_analyzes_percentage_strings(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    imported = []
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: imported.extend(records))
    csv_data = b'Attendance %,Maths Marks\n55%,42\n95%,88\n'

    response = authenticated_client().post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'percentages.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert imported[0]['attendance_percentage'] == 55
    assert imported[0]['estimated_risk'] == 'High'


def test_model_assessment_ignores_internal_array_metadata(monkeypatch):
    student = {
        'student_id': 'CUSTOM-1',
        'attendance_percentage': -1,
        'average_marks': -1,
        'active_backlogs': -1,
        'financial_difficulty': None,
        'scholarship_status': None,
        'previous_semester_gpa': None,
        'assignment_completion': None,
        'data_fields': {
            'maths_marks': 42,
            '_risk_factors': ['Maths marks is 42'],
            '_missing_fields': [],
        },
    }
    saved_assessments = []
    monkeypatch.setattr(app_module, 'list_students', lambda: [student])
    monkeypatch.setattr(
        app_module,
        'update_student_assessments',
        lambda assessments: saved_assessments.extend(assessments),
    )

    app_module._refresh_assessments_with_model({'feature_columns': []})

    assert saved_assessments[0]['student_id'] == 'CUSTOM-1'
    assert saved_assessments[0]['risk_category'] in {'High', 'Medium', 'Low'}
    assert isinstance(saved_assessments[0]['data_fields']['_risk_factors'], list)


def test_csv_upload_uses_supplied_risk_status_as_training_label(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: None)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    client = authenticated_client()
    csv_data = (
        b'Attendance Rate,Risk Level\n'
        b'45,High\n'
        b'55,High\n'
        b'92,Low\n'
        b'88,Low\n'
    )

    response = client.post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'status.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert response.json['training_ready'] is True
    assert response.json['columns'] == ['student_id', 'attendance_percentage', 'risk_status']


def test_upload_requires_confirmation_to_replace_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    client = authenticated_client()
    (tmp_path / 'uploaded_students.csv').write_text('existing dataset')
    csv_data = b'Student ID,Attendance\nSTU-3001,80\n'
    response = client.post('/api/upload-csv', data={'file': (io.BytesIO(csv_data), 'students.csv')}, content_type='multipart/form-data')
    assert response.status_code == 409
    assert response.json['replace_required'] is True


def test_upload_replacement_succeeds_after_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(app_module, 'replace_student_dataset', lambda records: None)
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    client = authenticated_client()
    (tmp_path / 'uploaded_students.csv').write_text('existing dataset')
    csv_data = b'Student ID,Attendance\nSTU-3001,80\n'
    response = client.post(
        '/api/upload-csv',
        data={
            'file': (io.BytesIO(csv_data), 'students.csv'),
            'replace_existing': 'true',
        },
        content_type='multipart/form-data',
    )
    assert response.status_code == 200
    assert response.json['valid'] is True


def test_upload_imports_dataset_for_directory_dashboard_risk_and_recommendations(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'UPLOAD_DIR', tmp_path / 'uploads')
    (tmp_path / 'uploads').mkdir()
    monkeypatch.setattr(app_module, 'load_model', lambda: None)
    monkeypatch.setattr(database_module, 'DB_PATH', tmp_path / 'student-support.db')
    database_module.init_db()
    client = authenticated_client()

    csv_data = (
        b'Student ID,Student Name,Department,Year,Semester,Attendance %,Average Marks,Backlogs,'
        b'Financial Difficulty,Scholarship Status,Previous Semester GPA,Assignment Completion\n'
        b'R-001,Amira Das,Engineering,2,4,58,52,2,Yes,No,5.4,62\n'
        b'R-002,Dev Shah,Science,1,2,92,86,0,No,Yes,8.6,94\n'
    )
    response = client.post(
        '/api/upload-csv',
        data={'file': (io.BytesIO(csv_data), 'college.csv')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    assert response.json['students_imported'] == 2

    students = client.get('/api/students').json['students']
    assert [student['student_id'] for student in students] == ['R-001', 'R-002']
    assert students[0]['name'] == 'Amira Das'
    assert students[0]['financial_difficulty'] == '1'
    assert students[0]['estimated_risk'] == 'High'

    dashboard = client.get('/api/dashboard').json
    assert dashboard['summary'][0]['value'] == 2
    assert dashboard['dataset'] == {'active': True, 'student_count': 2, 'data_source': 'uploaded'}
    assert sum(item['value'] for item in dashboard['risk_distribution']) == 2
    assert {item['department'] for item in dashboard['department_data']} == {'Engineering', 'Science'}
    assert dashboard['semester_performance'] == [
        {'semester': 'Sem 2', 'score': 86.0},
        {'semester': 'Sem 4', 'score': 52.0},
    ]
    assert dashboard['follow_ups']
    assert any('follow-up not yet scheduled' in item['next_step'] for item in dashboard['follow_ups'])
    report = client.get('/api/reports').json
    assert report['dataset'] == dashboard['dataset']
    assert report['overall_summary'][0]['value'] == 2

    risk = client.get('/api/risk/R-001').json
    assert risk['risk_category'] == 'High'
    assert risk['source'] == 'transparent rule-based estimate'
    assert any('58%' in factor for factor in risk['risk_factors'])
    recommendation = client.get('/api/recommendations/R-001').json
    assert 'Attendance is 58%' in recommendation['concerns']
    assert 'backlog recovery plan' in recommendation['recommendations']


def test_csv_template_download():
    response = authenticated_client().get('/api/csv-template')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert response.data.splitlines()[0] == b'student_id,indicator_1,risk_status'
    assert b'attendance_percentage' not in response.data


def test_model_training_accepts_yes_no_financial_values(tmp_path, monkeypatch):
    dataset_path = tmp_path / 'historical.csv'
    rows = []
    for index in range(40):
        rows.append({
            'student_id': f'STU-{index:04d}',
            'attendance_percentage': 60 + index,
            'average_marks': 50 + (index % 45),
            'active_backlogs': index % 4,
            'financial_difficulty': 'Yes' if index % 3 == 0 else 'No',
            'scholarship_status': 'Yes' if index % 2 == 0 else 'No',
            'previous_semester_gpa': 5 + (index % 5),
            'assignment_completion': 55 + (index % 45),
            'dropout_status': '1' if index % 2 else '0',
        })
    import pandas as pd
    pd.DataFrame(rows).to_csv(dataset_path, index=False)
    monkeypatch.setattr(ml_pipeline, 'MODEL_PATH', tmp_path / 'model.joblib')

    result = ml_pipeline.train_model_from_file(dataset_path)

    assert result['model_name'] == 'RandomForestClassifier'
    assert 0 <= result['metrics']['f1_score'] <= 1
    assert result['metrics']['target_distribution'] == {'0': 20, '1': 20}


def test_model_training_uses_custom_features_and_risk_level_target(tmp_path, monkeypatch):
    dataset_path = tmp_path / 'custom.csv'
    rows = [
        {
            'student_id': f'CSV-{index:04d}',
            'maths_marks': f'{35 + (index % 60)}%',
            'engagement': 'Low' if index % 2 else 'High',
            'risk_status': 'High' if index % 2 else 'Low',
        }
        for index in range(40)
    ]
    import pandas as pd
    pd.DataFrame(rows).to_csv(dataset_path, index=False)
    monkeypatch.setattr(ml_pipeline, 'MODEL_PATH', tmp_path / 'custom-model.joblib')

    result = ml_pipeline.train_model_from_file(dataset_path)
    bundle = ml_pipeline.load_model()

    assert result['model_name'] == 'RandomForestClassifier'
    assert bundle['feature_columns'] == ['maths_marks', 'engagement']
    assert result['metrics']['target_distribution'] == {'0': 20, '1': 20}
