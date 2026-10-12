import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  Download,
  Filter,
  GraduationCap,
  LayoutDashboard,
  LockKeyhole,
  Mail,
  MessageSquareText,
  Plus,
  Search,
  ShieldCheck,
  Upload,
  UserCircle2,
  Users,
} from 'lucide-react'
import './App.css'

const navItems = [
  'Overview',
  'Student Directory',
  'Risk Analysis',
  'Counseling Center',
  'Appointments',
  'Dataset & Model',
  'Reports',
]

const COLORS = ['#0f172a', '#0f766e', '#d97706']
const API_BASE = '/api'

function LoginPage({ onAuthenticated, notice }) {
  const [purpose, setPurpose] = useState('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [step, setStep] = useState('email')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const requestCode = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const response = await fetch(`${API_BASE}/auth/request-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name, purpose }),
        credentials: 'include',
      })
      const result = await response.json()
      if (!response.ok) {
        setError(result.message || 'Unable to send a sign-in code.')
        return
      }
      setStep('code')
      setMessage(result.message || `A verification code was sent to ${email}.`)
    } catch {
      setError('Could not reach the sign-in service. Check your connection and try again.')
    } finally {
      setBusy(false)
    }
  }

  const verifyCode = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code, purpose }),
        credentials: 'include',
      })
      const result = await response.json()
      if (!response.ok) {
        setError(result.message || 'Unable to verify the code.')
        return
      }
      onAuthenticated(result.user)
    } catch {
      setError('Could not reach the sign-in service. Check your connection and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-showcase">
        <div className="login-brand">
          <div className="brand-mark"><GraduationCap size={20} /></div>
          <span>DropoutGuard</span>
        </div>
        <div className="showcase-copy">
          <span className="showcase-eyebrow"><ShieldCheck size={15} /> A more supportive campus</span>
          <h1>Every student deserves a chance to thrive.</h1>
          <p>One secure place for faculty and management to turn early signals into meaningful support.</p>
        </div>
        <div className="showcase-note">
          <div className="showcase-note-icon"><LockKeyhole size={18} /></div>
          <div><strong>Private by design</strong><span>Secure, role-based access for your institution.</span></div>
        </div>
        <div className="showcase-decoration showcase-decoration-one" />
        <div className="showcase-decoration showcase-decoration-two" />
      </section>

      <section className="login-form-side">
        <div className="login-card">
          <div className="login-card-heading">
            <span className="login-kicker">STAFF ACCESS</span>
            <h2>{step === 'email' ? (purpose === 'login' ? 'Welcome back' : 'Create your account') : 'Check your inbox'}</h2>
            <p>{step === 'email'
              ? (purpose === 'login' ? 'Sign in to your student success workspace.' : 'Verify your email to register for staff access.')
              : `Enter the 6-digit code sent to ${email}.`}</p>
          </div>
          {notice && <p className="login-feedback error" role="alert">{notice}</p>}

          {step === 'email' ? (
            <form onSubmit={requestCode}>
              <div className="login-mode-switch" role="tablist" aria-label="Account access">
                <button
                  type="button"
                  role="tab"
                  aria-selected={purpose === 'login'}
                  className={purpose === 'login' ? 'active' : ''}
                  onClick={() => { setPurpose('login'); setError('') }}
                >
                  Sign in
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={purpose === 'register'}
                  className={purpose === 'register' ? 'active' : ''}
                  onClick={() => { setPurpose('register'); setError('') }}
                >
                  Register
                </button>
              </div>
              {purpose === 'register' && (
                <>
                  <label className="login-label" htmlFor="register-name">Your name</label>
                  <div className="login-input-wrap">
                    <UserCircle2 size={17} />
                    <input
                      id="register-name"
                      type="text"
                      autoComplete="name"
                      placeholder="Your full name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      required
                    />
                  </div>
                </>
              )}
              <label className="login-label" htmlFor="login-email">Email address</label>
              <div className="login-input-wrap">
                <Mail size={17} />
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
              {error && <p className="login-feedback error" role="alert">{error}</p>}
              <button className="login-submit" type="submit" disabled={busy}>
                {busy ? 'Sending code…' : purpose === 'login' ? 'Send sign-in code' : 'Verify email and register'}
                {!busy && <span aria-hidden="true">→</span>}
              </button>
              <p className="login-footnote"><LockKeyhole size={13} /> We’ll email you a secure one-time code.</p>
            </form>
          ) : (
            <form onSubmit={verifyCode}>
              <p className="login-success-note" role="status">{message}</p>
              <label className="login-label" htmlFor="login-code">6-digit verification code</label>
              <div className="login-input-wrap code-input-wrap">
                <LockKeyhole size={17} />
                <input
                  id="login-code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                  required
                />
              </div>
              {error && <p className="login-feedback error" role="alert">{error}</p>}
              <button className="login-submit" type="submit" disabled={busy || code.length !== 6}>
                {busy ? 'Verifying…' : 'Verify and sign in'}
                {!busy && <span aria-hidden="true">→</span>}
              </button>
              <button className="login-back" type="button" disabled={busy} onClick={requestCode}>
                Resend code
              </button>
              <button
                className="login-back"
                type="button"
                onClick={() => { setStep('email'); setCode(''); setMessage(''); setError('') }}
              >
                Change email or access
              </button>
            </form>
          )}
          <div className="login-divider"><span>STUDENT SUCCESS PLATFORM</span></div>
          <p className="login-security">Your access is for authorized university staff only.</p>
        </div>
      </section>
    </main>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState('Overview')
  const [user, setUser] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [students, setStudents] = useState([])
  const [appointments, setAppointments] = useState([])
  const [updatingAppointmentId, setUpdatingAppointmentId] = useState(null)
  const [recommendations, setRecommendations] = useState([])
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [riskInsight, setRiskInsight] = useState(null)
  const [modelInfo, setModelInfo] = useState({ exists: false, message: 'No trained model yet.' })
  const [filters, setFilters] = useState({ department: 'All', year: 'All', semester: 'All', risk: 'All' })
  const [search, setSearch] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [authLoading, setAuthLoading] = useState(true)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadPreview, setUploadPreview] = useState([])
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadError, setUploadError] = useState(false)
  const [trainingReady, setTrainingReady] = useState(false)
  const [trainingColumnsMissing, setTrainingColumnsMissing] = useState([])
  const [isStudentFormOpen, setIsStudentFormOpen] = useState(false)
  const [isAppointmentFormOpen, setIsAppointmentFormOpen] = useState(false)
  const [studentForm, setStudentForm] = useState({
    student_id: '',
    name: '',
    department: 'Computer Science',
    year: 2,
    semester: 4,
    attendance_percentage: 80,
    average_marks: 72,
    active_backlogs: 1,
    financial_support: 'Scholarship',
    estimated_risk: 'Medium',
    last_counseling_date: '2026-10-11',
    risk_score: 0.5,
  })
  const [appointmentForm, setAppointmentForm] = useState({
    student_id: '',
    student_name: '',
    counselor_name: 'Prof. Aditi Nair',
    appointment_date: '2026-10-15',
    appointment_time: '09:30',
    session_type: 'Academic counseling',
    status: 'Scheduled',
    follow_up: '2026-10-29',
  })

  const fetchDashboard = async () => {
    const response = await fetch(`${API_BASE}/dashboard`, { credentials: 'include' })
    if (!response.ok) return
    const data = await response.json()
    setDashboard(data)
  }

  const fetchStudents = async () => {
    const response = await fetch(`${API_BASE}/students`, { credentials: 'include' })
    if (!response.ok) return
    const data = await response.json()
    setStudents(data.students || [])
    if (data.students && data.students.length) {
      setSelectedStudent(data.students[0])
      fetchStudentDetails(data.students[0].student_id)
    }
  }

  const fetchStudentDetails = async (studentId) => {
    if (!studentId) return
    const response = await fetch(`${API_BASE}/students/${studentId}`, { credentials: 'include' })
    if (!response.ok) return
    const data = await response.json()
    setSelectedStudent(data.student)
    const riskResponse = await fetch(`${API_BASE}/risk/${studentId}`, { credentials: 'include' })
    if (riskResponse.ok) {
      const riskData = await riskResponse.json()
      setRiskInsight(riskData)
    }
    const recommendationResponse = await fetch(`${API_BASE}/recommendations/${studentId}`, { credentials: 'include' })
    if (recommendationResponse.ok) {
      const recommendationData = await recommendationResponse.json()
      setRecommendations([recommendationData])
    }
  }

  const fetchAppointments = async () => {
    const response = await fetch(`${API_BASE}/appointments`, { credentials: 'include' })
    if (!response.ok) return
    const data = await response.json()
    setAppointments(data.appointments || [])
  }

  const fetchModelInfo = async () => {
    const response = await fetch(`${API_BASE}/model`, { credentials: 'include' })
    if (!response.ok) return
    const data = await response.json()
    setModelInfo(data)
  }

  useEffect(() => {
    let active = true
    fetch(`${API_BASE}/auth/session`, { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) return
        const result = await response.json()
        if (active && result.success) setUser(result.user)
      })
      .catch(() => {
        if (active) setNotice('Could not check your saved sign-in. Please sign in again.')
      })
      .finally(() => {
        if (active) setAuthLoading(false)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!user) return
    const loadData = async () => {
      setLoading(true)
      try {
        await fetchDashboard()
        await fetchStudents()
        await fetchAppointments()
        await fetchModelInfo()
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [user])

  const signOut = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' })
      if (!response.ok) {
        setNotice('Could not sign out. Please try again.')
        return
      }
      setUser(null)
      setNotice('')
    } catch {
      setNotice('Could not reach the sign-in service. Please try again.')
    }
  }

  const completeLogin = (loginUser) => {
    setUser(loginUser)
    setNotice('')
  }

  useEffect(() => {
    if (selectedStudent) {
      fetchStudentDetails(selectedStudent.student_id)
    }
  }, [selectedStudent?.student_id])

  const filteredStudents = useMemo(() => {
    return students.filter((student) => {
      const matchesSearch = !search || student.name.toLowerCase().includes(search.toLowerCase()) || student.student_id.toLowerCase().includes(search.toLowerCase())
      const matchesDepartment = filters.department === 'All' || student.department === filters.department
      const matchesYear = filters.year === 'All' || student.year === Number(filters.year)
      const matchesSemester = filters.semester === 'All' || student.semester === Number(filters.semester)
      const matchesRisk = filters.risk === 'All' || student.estimated_risk === filters.risk
      return matchesSearch && matchesDepartment && matchesYear && matchesSemester && matchesRisk
    })
  }, [students, search, filters])

  const handleUpload = async (event, replaceExisting = false) => {
    const file = event.target.files?.[0]
    if (!file) return
    const input = event.target
    setUploadError(false)
    setUploadMessage('')
    setUploadPreview([])
    setTrainingReady(false)
    setTrainingColumnsMissing([])

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setUploadError(true)
      setUploadMessage('Choose a .csv file. Excel workbooks (.xlsx) are not accepted.')
      input.value = ''
      return
    }
    if (file.size > 16 * 1024 * 1024) {
      setUploadError(true)
      setUploadMessage('This file is larger than the 16 MB upload limit.')
      input.value = ''
      return
    }

    setUploadBusy(true)
    const sendUpload = async (shouldReplace) => {
      const formData = new FormData()
      formData.append('file', file)
      if (shouldReplace) formData.append('replace_existing', 'true')
      const response = await fetch(`${API_BASE}/upload-csv`, { method: 'POST', body: formData, credentials: 'include' })
      const result = await response.json()
      return { response, result }
    }

    try {
      let { response, result } = await sendUpload(replaceExisting)
      if (response.status === 409 && result.replace_required) {
        if (!window.confirm('A dataset is already uploaded. Replace it with this CSV?')) {
          setUploadMessage('Existing dataset kept. No files were replaced.')
          return
        }
        ;({ response, result } = await sendUpload(true))
      }

      if (!response.ok || !result.success) {
        setUploadError(true)
        setUploadMessage(result.message || `Upload failed (${response.status}).`)
        return
      }
      setUploadMessage(result.message || 'Dataset uploaded successfully.')
      setUploadPreview(result.preview || [])
      setTrainingReady(Boolean(result.training_ready))
      setTrainingColumnsMissing(result.missing_training_columns || [])
      setNotice(`${result.students_imported} student record${result.students_imported === 1 ? '' : 's'} imported from the uploaded dataset.`)
      await Promise.all([fetchDashboard(), fetchStudents(), fetchAppointments()])
    } catch (error) {
      setUploadError(true)
      setUploadMessage(`Upload failed: ${error.message}. Check that the backend is running and try again.`)
    } finally {
      setUploadBusy(false)
      input.value = ''
    }
  }

  const handleTrainModel = async () => {
    setUploadBusy(true)
    setUploadError(false)
    try {
      const response = await fetch(`${API_BASE}/train-model`, { method: 'POST', credentials: 'include' })
      const result = await response.json()
      setUploadError(!response.ok || !result.success)
      setUploadMessage(result.message || 'Model training complete')
      if (response.ok && result.success) await fetchModelInfo()
    } catch (error) {
      setUploadError(true)
      setUploadMessage(`Model training failed: ${error.message}`)
    } finally {
      setUploadBusy(false)
    }
  }

  const openStudentForm = (student = null) => {
    if (student) {
      setStudentForm({
        student_id: student.student_id,
        name: student.name,
        department: student.department,
        year: student.year,
        semester: student.semester,
        attendance_percentage: student.attendance_percentage,
        average_marks: student.average_marks,
        active_backlogs: student.active_backlogs,
        financial_support: student.financial_support,
        estimated_risk: student.estimated_risk,
        last_counseling_date: student.last_counseling_date || '2026-10-11',
        risk_score: student.risk_score || 0.5,
      })
    } else {
      setStudentForm({
        student_id: '',
        name: '',
        department: 'Computer Science',
        year: 2,
        semester: 4,
        attendance_percentage: 80,
        average_marks: 72,
        active_backlogs: 1,
        financial_support: 'Scholarship',
        estimated_risk: 'Medium',
        last_counseling_date: '2026-10-11',
        risk_score: 0.5,
      })
    }
    setIsStudentFormOpen(true)
  }

  const saveStudent = async () => {
    const payload = { ...studentForm }
    if (!payload.student_id || !payload.name) {
      setNotice('Student ID and name are required before saving.')
      return
    }
    const response = await fetch(`${API_BASE}/students`, {
      credentials: 'include',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const result = await response.json()
    if (result.success) {
      setNotice(`Student ${payload.name} saved successfully.`)
      setIsStudentFormOpen(false)
      await fetchStudents()
      await fetchDashboard()
    } else {
      setNotice(result.message || 'Student could not be saved.')
    }
  }

  const deleteStudent = async (studentId) => {
    const confirmed = window.confirm(`Delete student ${studentId}? This cannot be undone.`)
    if (!confirmed) return

    const response = await fetch(`${API_BASE}/students/${studentId}`, { method: 'DELETE', credentials: 'include' })
    const result = await response.json()
    if (result.success) {
      setNotice(`Student ${studentId} was removed.`)
      await fetchStudents()
      await fetchDashboard()
    } else {
      setNotice(result.message || 'Student could not be deleted.')
    }
  }

  const createAppointment = async () => {
    const payload = {
      ...appointmentForm,
      student_name: students.find((student) => student.student_id === appointmentForm.student_id)?.name || appointmentForm.student_name,
    }

    if (!payload.student_id || !payload.student_name) {
      setNotice('Select a student before creating an appointment.')
      return
    }

    const response = await fetch(`${API_BASE}/appointments`, {
      credentials: 'include',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const result = await response.json()
    if (result.success) {
      setIsAppointmentFormOpen(false)
      setNotice('Appointment scheduled successfully.')
      await fetchAppointments()
      await fetchDashboard()
    } else {
      setNotice(result.message || 'The appointment could not be created.')
    }
  }

  const exportReport = () => {
    fetch(`${API_BASE}/reports/export.csv`, { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) {
          const result = await response.json().catch(() => ({}))
          throw new Error(result.message || 'Report could not be generated.')
        }
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = 'student_support_report.csv'
        link.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      })
      .catch((error) => setNotice(error.message))
  }

  const updateAppointmentStatus = async (appointmentId, status) => {
    setUpdatingAppointmentId(appointmentId)
    try {
      const response = await fetch(`${API_BASE}/appointments/${appointmentId}`, {
        credentials: 'include',
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        throw new Error(result.message || 'Appointment status could not be updated.')
      }
      setAppointments((current) => current.map((appointment) => (
        appointment.id === appointmentId ? result.appointment : appointment
      )))
      await fetchDashboard()
      setNotice('Appointment status updated.')
    } catch (error) {
      setNotice(error.message || 'Appointment status could not be updated.')
      await fetchAppointments()
    } finally {
      setUpdatingAppointmentId(null)
    }
  }

  const openStudentRiskAnalysis = async (studentId) => {
    setActiveTab('Risk Analysis')
    await fetchStudentDetails(studentId)
  }

  const summaryCards = dashboard?.summary || [
    { label: 'Total Students', value: 0 },
    { label: 'Students Requiring Attention', value: 0 },
    { label: 'High-Risk Students', value: 0 },
    { label: 'Counseling Sessions Pending', value: 0 },
  ]

  const departmentOptions = Array.from(new Set(students.map((s) => s.department)))
  const riskOptions = ['Low', 'Medium', 'High']
  const getStudentIndicators = (student) => {
    const provided = Object.entries(student.data_fields || {}).filter(([key, value]) => (
      !key.startsWith('_')
      && !['student_id', 'name', 'department', 'year', 'semester'].includes(key)
      && value != null
      && String(value).trim() !== ''
    ))
    if (provided.length) return provided
    return [
      ['attendance_percentage', student.attendance_percentage],
      ['average_marks', student.average_marks],
      ['active_backlogs', student.active_backlogs],
      ['financial_support', student.financial_support],
    ].filter(([, value]) => (
      value != null && (typeof value !== 'number' || value >= 0)
    ))
  }

  const renderOverview = () => (
    <div className="page-shell">
      {dashboard?.dataset?.active ? (
        <div className="dataset-status">
          <CheckCircle2 size={16} />
          <span>Dashboard is using {dashboard.dataset.student_count} records from the uploaded dataset. Risk categories are advisory estimates for human review.</span>
        </div>
      ) : null}
      <div className="panel-grid summary-grid">
        {summaryCards.map((item) => (
          <button key={item.label} type="button" className="summary-card" onClick={() => setActiveTab('Student Directory')}>
            <div className="card-label">{item.label}</div>
            <div className="card-value">{item.value}</div>
            <div className="card-meta">{item.detail || 'Live student records'}</div>
          </button>
        ))}
      </div>

      <div className="panel-grid chart-grid">
        <div className="panel card">
          <div className="panel-header">
            <h3>Student risk distribution</h3>
            <span className="chip neutral">Updated today</span>
          </div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={dashboard?.risk_distribution || []} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2}>
                  {((dashboard?.risk_distribution || [])).map((entry, index) => (
                    <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel card">
          <div className="panel-header">
            <h3>Attendance vs performance</h3>
            <span className="chip teal">Academic snapshot</span>
          </div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dashboard?.attendance_data || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="attendance" fill="#1d4ed8" radius={[6, 6, 0, 0]} />
                <Bar dataKey="marks" fill="#14b8a6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel card wide">
          <div className="panel-header">
            <h3>Counseling and intervention trends</h3>
            <span className="chip amber">Monthly</span>
          </div>
          <div style={{ height: 260 }}>
            {dashboard?.counseling_trend?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dashboard.counseling_trend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="sessions" stroke="#0f172a" strokeWidth={3} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="chart-empty">No counseling sessions recorded for this dataset yet.</div>}
          </div>
        </div>

        <div className="panel card">
          <div className="panel-header">
            <h3>Department-wise risk</h3>
            <span className="chip brand">Support distribution</span>
          </div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dashboard?.department_data || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="department" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="low" fill="#16a34a" radius={[6, 6, 0, 0]} />
                <Bar dataKey="medium" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                <Bar dataKey="high" fill="#dc2626" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel card wide">
          <div className="panel-header">
            <h3>Semester-wise academic performance</h3>
            <span className="chip olive">Benchmark trend</span>
          </div>
          <div style={{ height: 250 }}>
            {dashboard?.semester_performance?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dashboard.semester_performance}>
                  <defs>
                    <linearGradient id="academicFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#0f766e" stopOpacity={0.7} />
                      <stop offset="95%" stopColor="#0f766e" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="semester" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="score" stroke="#0f766e" fill="url(#academicFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : <div className="chart-empty">Semester information is not included in the available student records.</div>}
          </div>
        </div>
      </div>

      <div className="panel-grid dashboard-grid">
        <div className="panel card">
          <div className="panel-header">
            <h3>Flagged students</h3>
            <button type="button" className="text-button">View all</button>
          </div>
          <ul className="list">
            {(dashboard?.flagged_students || []).map((student) => (
              <li key={student.student_id} className="list-row clickable" onClick={() => fetchStudentDetails(student.student_id)}>
                <div>
                  <strong>{student.name}</strong>
                  <small>{student.department}</small>
                </div>
                <span className={`risk-badge ${student.risk.toLowerCase()}`}>{student.risk}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel card">
          <div className="panel-header">
            <h3>Follow-up queue</h3>
            <button type="button" className="text-button">Review</button>
          </div>
          <ul className="list">
            {(dashboard?.follow_ups || []).map((student) => (
              <li key={student.student_id} className="list-row">
                <div>
                  <strong>{student.name}</strong>
                  <small>{student.next_step}</small>
                </div>
                <ChevronRight size={16} />
              </li>
            ))}
          </ul>
          {!dashboard?.follow_ups?.length ? <p className="empty-inline">No follow-ups are currently suggested from the available records.</p> : null}
        </div>

        <div className="panel card">
          <div className="panel-header">
            <h3>Upcoming counseling</h3>
            <button type="button" className="text-button" onClick={() => setIsAppointmentFormOpen(true)}>Create appointment</button>
          </div>
          <ul className="list">
            {(dashboard?.upcoming_appointments || []).map((session) => (
              <li key={`${session.student}-${session.date}`} className="list-row">
                <div>
                  <strong>{session.student}</strong>
                  <small>{session.date} · {session.time}</small>
                </div>
                <span className="mini-tag">{session.counselor}</span>
              </li>
            ))}
          </ul>
          {!dashboard?.upcoming_appointments?.length ? <p className="empty-inline">No appointments are scheduled yet.</p> : null}
        </div>
      </div>
    </div>
  )

  const renderDirectory = () => (
    <div className="page-shell">
      <div className="toolbar panel card">
        <div className="search-input">
          <Search size={16} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by student ID or name" />
        </div>
        <div className="filter-row">
          <select value={filters.department} onChange={(event) => setFilters((prev) => ({ ...prev, department: event.target.value }))}>
            <option value="All">All departments</option>
            {departmentOptions.map((dept) => <option key={dept} value={dept}>{dept}</option>)}
          </select>
          <select value={filters.year} onChange={(event) => setFilters((prev) => ({ ...prev, year: event.target.value }))}>
            <option value="All">All years</option>
            {[1,2,3,4].map((year) => <option key={year} value={year}>{year}</option>)}
          </select>
          <select value={filters.semester} onChange={(event) => setFilters((prev) => ({ ...prev, semester: event.target.value }))}>
            <option value="All">All semesters</option>
            {[1,2,3,4,5,6,7,8].map((semester) => <option key={semester} value={semester}>{semester}</option>)}
          </select>
          <select value={filters.risk} onChange={(event) => setFilters((prev) => ({ ...prev, risk: event.target.value }))}>
            <option value="All">All risk levels</option>
            {riskOptions.map((risk) => <option key={risk} value={risk}>{risk}</option>)}
          </select>
          <button className="primary-button" onClick={() => openStudentForm()} type="button">
            <Plus size={16} /> Add student
          </button>
          <button className="primary-button secondary" onClick={() => setIsAppointmentFormOpen(true)} type="button">
            <CalendarClock size={16} /> Schedule
          </button>
          <button className="primary-button secondary" onClick={exportReport} type="button">
            <Download size={16} /> Export CSV
          </button>
        </div>
      </div>

      <div className="table-wrapper panel card">
        <table>
          <thead>
            <tr>
              <th>Student ID</th>
              <th>Name</th>
              <th>Department</th>
              <th>Year/Sem</th>
              <th>Provided indicators</th>
              <th>Risk</th>
              <th>Last Counseling</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredStudents.map((student) => (
              <tr key={student.student_id}>
                <td>{student.student_id}</td>
                <td>{student.name}</td>
                <td>{student.department}</td>
                <td>{student.year > 0 ? student.year : '—'}/{student.semester > 0 ? student.semester : '—'}</td>
                <td>{getStudentIndicators(student).slice(0, 4).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' · ') || 'No indicators recorded'}</td>
                <td><span className={`risk-badge ${student.estimated_risk.toLowerCase()}`}>{student.estimated_risk}</span></td>
                <td>{student.last_counseling_date || '—'}</td>
                <td className="actions-cell">
                  <button type="button" className="small-button" onClick={() => openStudentRiskAnalysis(student.student_id)}>View</button>
                  <button type="button" className="small-button muted" onClick={() => openStudentForm(student)}>Edit</button>
                  <button type="button" className="small-button danger" onClick={() => deleteStudent(student.student_id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!filteredStudents.length ? <div className="panel card empty-state">No student records match the current search and filters.</div> : null}
      {isStudentFormOpen ? (
        <div className="modal-overlay" onClick={() => setIsStudentFormOpen(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="panel-header">
              <h3>{studentForm.student_id ? 'Edit student record' : 'Add student record'}</h3>
              <button type="button" className="text-button" onClick={() => setIsStudentFormOpen(false)}>Close</button>
            </div>
            <div className="form-grid">
              <label>Student ID<input value={studentForm.student_id} onChange={(event) => setStudentForm((prev) => ({ ...prev, student_id: event.target.value }))} /></label>
              <label>Name<input value={studentForm.name} onChange={(event) => setStudentForm((prev) => ({ ...prev, name: event.target.value }))} /></label>
              <label>Department<select value={studentForm.department} onChange={(event) => setStudentForm((prev) => ({ ...prev, department: event.target.value }))}>
                {['Computer Science', 'Electronics', 'Mechanical', 'Civil', 'Biotechnology', 'Business', 'Electrical'].map((dept) => (
                  <option key={dept} value={dept}>{dept}</option>
                ))}
              </select></label>
              <label>Year<input type="number" value={studentForm.year} onChange={(event) => setStudentForm((prev) => ({ ...prev, year: Number(event.target.value) }))} /></label>
              <label>Semester<input type="number" value={studentForm.semester} onChange={(event) => setStudentForm((prev) => ({ ...prev, semester: Number(event.target.value) }))} /></label>
              <label>Attendance %<input type="number" value={studentForm.attendance_percentage} onChange={(event) => setStudentForm((prev) => ({ ...prev, attendance_percentage: Number(event.target.value) }))} /></label>
              <label>Average marks<input type="number" value={studentForm.average_marks} onChange={(event) => setStudentForm((prev) => ({ ...prev, average_marks: Number(event.target.value) }))} /></label>
              <label>Active backlogs<input type="number" value={studentForm.active_backlogs} onChange={(event) => setStudentForm((prev) => ({ ...prev, active_backlogs: Number(event.target.value) }))} /></label>
              <label>Financial support<select value={studentForm.financial_support} onChange={(event) => setStudentForm((prev) => ({ ...prev, financial_support: event.target.value }))}>
                {['Scholarship', 'Need-based Aid', 'No Support'].map((support) => (
                  <option key={support} value={support}>{support}</option>
                ))}
              </select></label>
              <label>Risk category<select value={studentForm.estimated_risk} onChange={(event) => setStudentForm((prev) => ({ ...prev, estimated_risk: event.target.value }))}>
                {riskOptions.map((risk) => (
                  <option key={risk} value={risk}>{risk}</option>
                ))}
              </select></label>
              <label>Last counseling date<input type="date" value={studentForm.last_counseling_date} onChange={(event) => setStudentForm((prev) => ({ ...prev, last_counseling_date: event.target.value }))} /></label>
            </div>
            <div className="modal-actions">
              <button type="button" className="small-button muted" onClick={() => setIsStudentFormOpen(false)}>Cancel</button>
              <button type="button" className="primary-button" onClick={saveStudent}>Save student</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )

  const renderRiskAnalysis = () => (
    <div className="page-shell risk-layout">
      <div className="panel card">
        <div className="panel-header">
          <h3>Student profile</h3>
          <button className="primary-button" type="button">Review Support Recommendations</button>
        </div>
        {selectedStudent ? (
          <div className="profile-block">
            <div className="profile-summary">
              <div className="avatar"><UserCircle2 size={48} /></div>
              <div>
                <h4>{selectedStudent.name}</h4>
                <p>{selectedStudent.student_id} · {selectedStudent.department} · Year {selectedStudent.year}, Semester {selectedStudent.semester}</p>
              </div>
            </div>
            <div className="info-grid">
              {getStudentIndicators(selectedStudent).map(([key, value]) => (
                <div key={key}>
                  <span>{key.replaceAll('_', ' ')}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}
            </div>
            <div className="explain-box">
              <h4>Explainable risk assessment</h4>
              <p>
                {riskInsight?.risk_factors?.length
                  ? `Observed concerns: ${riskInsight.risk_factors.join('; ')}.`
                  : 'No contributing factors were recorded in the available student indicators. This estimate is advisory and requires staff review.'}
                {' '}Assessment source: {riskInsight?.source || 'recorded student data'}.
              </p>
              {riskInsight?.missing_fields?.length ? (
                <p className="missing-data">Not present in the uploaded data: {riskInsight.missing_fields.join(', ')}.</p>
              ) : null}
            </div>
          </div>
        ) : (
          <p>No student selected.</p>
        )}
      </div>

      <div className="panel card">
        <div className="panel-header">
          <h3>Assessment details</h3>
        </div>
        <div className="risk-score-box">
          <div>
            <span className="label">Estimated risk</span>
            <strong className={`risk-badge ${selectedStudent?.estimated_risk?.toLowerCase() || 'low'}`}>{selectedStudent?.estimated_risk || 'Low'}</strong>
          </div>
          <div>
            <span className="label">Prediction score</span>
            <strong>{riskInsight?.score != null ? `${(riskInsight.score * 100).toFixed(1)}%` : 'Not available'}</strong>
          </div>
          <div>
            <span className="label">Latest assessment</span>
            <strong>{selectedStudent?.last_counseling_date || 'No data'}</strong>
          </div>
        </div>
        <div className="factor-list">
          <h4>Top contributing factors</h4>
          <ul>
            {(riskInsight?.risk_factors || []).length ? riskInsight.risk_factors.map((factor) => <li key={factor}>{factor}</li>) : <li>No elevated contributing factors found in the available data.</li>}
          </ul>
        </div>
      </div>
    </div>
  )

  const renderCounseling = () => (
    <div className="page-shell">
      <div className="panel-grid dashboard-grid">
        {recommendations.map((caseItem) => (
          <div key={caseItem.student_id} className="panel card counseling-card">
            <div className="panel-header">
              <h3>{caseItem.student_id}</h3>
              <span className="chip neutral">{caseItem.status}</span>
            </div>
            <div className="case-body">
              <p><strong>Concern:</strong> {caseItem.concerns}</p>
              <p><strong>Recommendation:</strong> {caseItem.recommendations}</p>
              <p><strong>Assigned faculty:</strong> {caseItem.assigned_faculty}</p>
              <p><strong>Appointment:</strong> {caseItem.appointment_date}</p>
              <p><strong>Follow-up:</strong> {caseItem.follow_up_date}</p>
              <p><strong>Notes:</strong> {caseItem.notes}</p>
            </div>
          </div>
        ))}
        {!recommendations.length ? <div className="panel card empty-state">Select a student to view support recommendations based on recorded indicators.</div> : null}
      </div>
    </div>
  )

  const renderAppointments = () => (
    <div className="page-shell">
      <div className="panel card">
        <div className="panel-header">
          <h3>Appointment schedule</h3>
          <button type="button" className="primary-button" onClick={() => setIsAppointmentFormOpen(true)}><CalendarClock size={16} /> New session</button>
        </div>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Faculty</th>
                <th>Date</th>
                <th>Time</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((appointment) => (
                <tr key={appointment.id}>
                  <td>{appointment.student_name}</td>
                  <td>{appointment.counselor_name}</td>
                  <td>{appointment.appointment_date}</td>
                  <td>{appointment.appointment_time}</td>
                  <td>{appointment.session_type}</td>
                  <td>
                    <select
                      aria-label={`Status for ${appointment.student_name} appointment`}
                      value={appointment.status}
                      disabled={updatingAppointmentId === appointment.id}
                      onChange={(event) => updateAppointmentStatus(appointment.id, event.target.value)}
                    >
                      {['Scheduled', 'Pending', 'Completed'].map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!appointments.length ? <p className="empty-inline">No counseling appointments are recorded for the current student dataset.</p> : null}
      </div>
    </div>
  )

  const renderDataModel = () => (
    <div className="page-shell data-layout">
      <div className="panel card">
        <div className="panel-header">
          <h3>Dataset upload & validation</h3>
        </div>
        <div className="upload-box">
          <label className="upload-control">
            {uploadBusy ? <span className="upload-spinner" /> : <Upload size={18} />}
            <span>{uploadBusy ? 'Validating CSV…' : 'Choose CSV file'}</span>
            <input type="file" accept=".csv,text/csv" disabled={uploadBusy} onChange={handleUpload} />
          </label>
          <button type="button" className="primary-button" disabled={uploadBusy} onClick={handleTrainModel}><ShieldCheck size={16} /> Train model</button>
        </div>
        <a className="text-button template-link" href={`${API_BASE}/csv-template`}>Download a CSV template</a>
        <p className={`notice-text ${uploadError ? 'error' : ''}`}>{uploadMessage || 'CSV files up to 16 MB. Add any student details or indicators you have; headers are flexible, and student IDs are generated if omitted. The app analyzes the supplied values. To train a model, include a risk_status, status, dropout_status, or outcome column.'}</p>
        {uploadPreview.length > 0 ? (
          <p className={`upload-readiness ${trainingReady ? 'ready' : 'incomplete'}`}>
            {trainingReady ? 'Analyzed and ready for model training.' : 'Uploaded and analyzed. Training is optional and requires an outcome/status column.'}
          </p>
        ) : null}
        {trainingColumnsMissing.length > 0 ? (
          <p className="upload-hint">Training needs a label column such as {trainingColumnsMissing.join(', ')}. You can still analyze the supplied data without one.</p>
        ) : null}
        {uploadPreview.length ? (
          <div className="table-wrapper mini-table">
            <table>
              <thead>
                <tr>{Object.keys(uploadPreview[0]).map((key) => <th key={key}>{key}</th>)}</tr>
              </thead>
              <tbody>
                {uploadPreview.map((row, index) => (
                  <tr key={index}>{Object.values(row).map((val, idx) => <td key={idx}>{String(val)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="panel card">
        <div className="panel-header">
          <h3>Model status</h3>
        </div>
        <div className="stats-stack">
          <div className="metric-pill"><span>Model exists</span><strong>{modelInfo.exists ? 'Yes' : 'No'}</strong></div>
          <div className="metric-pill"><span>Latest version</span><strong>{modelInfo.latest?.version || 'Not trained'}</strong></div>
          <div className="metric-pill"><span>Dataset</span><strong>{modelInfo.latest?.dataset_name || 'No data file'}</strong></div>
          <div className="metric-pill"><span>F1 score</span><strong>{(modelInfo.latest?.metrics?.metrics?.f1_score ?? modelInfo.latest?.metrics?.f1_score) != null ? (modelInfo.latest.metrics.metrics?.f1_score ?? modelInfo.latest.metrics.f1_score).toFixed(3) : '—'}</strong></div>
          <div className="metric-pill"><span>Current student data</span><strong>{dashboard?.dataset?.active ? `${dashboard.dataset.student_count} imported records` : 'No data imported'}</strong></div>
        </div>
      </div>
    </div>
  )

  const renderReports = () => (
    <div className="page-shell">
      <div className="panel-grid summary-grid">
        {(dashboard?.summary || []).map((metric) => (
          <div key={metric.label} className="summary-card static">
            <div className="card-label">{metric.label}</div>
            <div className="card-value">{metric.value}</div>
            <div className="card-meta">{metric.detail}</div>
          </div>
        ))}
      </div>
      <div className="panel card">
        <div className="panel-header">
          <h3>Report export</h3>
          <button className="primary-button" type="button" onClick={exportReport}><Download size={16} /> Download CSV</button>
        </div>
        <p className="report-text">This report reflects {dashboard?.dataset?.active ? `${dashboard.dataset.student_count} records in the current uploaded dataset` : 'the current student records'}. Risk and follow-up summaries use the same records shown in the directory. Private counseling notes are excluded from exports.</p>
      </div>
    </div>
  )

  const viewByTab = {
    Overview: renderOverview,
    'Student Directory': renderDirectory,
    'Risk Analysis': renderRiskAnalysis,
    'Counseling Center': renderCounseling,
    Appointments: renderAppointments,
    'Dataset & Model': renderDataModel,
    Reports: renderReports,
  }

  if (authLoading) {
    return <div className="loading-screen">Checking your sign-in…</div>
  }

  if (!user) {
    return <LoginPage onAuthenticated={completeLogin} notice={notice} />
  }

  if (loading) {
    return <div className="loading-screen">Loading student support workspace…</div>
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark"><GraduationCap size={18} /></div>
          <div>
            <div className="brand-name">DropoutGuard</div>
          </div>
        </div>

        <div className="title-block">
          <span>{activeTab}</span>
        </div>

        <div className="topbar-tools">
          <div className="search-inline">
            <Search size={16} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Global student search" />
          </div>
          <button type="button" className="icon-button" aria-label="Notifications">
            <Bell size={17} />
          </button>
          <div className="profile-pill">
            <UserCircle2 size={18} />
            <div>
              <strong>{user.name}</strong>
              <small>{user.role}</small>
            </div>
          </div>
          <button type="button" className="sign-out-button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      <div className="content-shell">
        <aside className="sidebar panel">
          <div className="sidebar-header">
            <div className="icon-badge"><LayoutDashboard size={16} /></div>
            <div>
              <h4>Support hub</h4>
              <small>Academic oversight</small>
            </div>
          </div>
          <nav>
            {navItems.map((item) => (
              <button
                key={item}
                type="button"
                className={`nav-item ${activeTab === item ? 'active' : ''}`}
                onClick={() => setActiveTab(item)}
              >
                {item === 'Overview' && <LayoutDashboard size={16} />}
                {item === 'Student Directory' && <Users size={16} />}
                {item === 'Risk Analysis' && <AlertTriangle size={16} />}
                {item === 'Counseling Center' && <MessageSquareText size={16} />}
                {item === 'Appointments' && <CalendarClock size={16} />}
                {item === 'Dataset & Model' && <BookOpen size={16} />}
                {item === 'Reports' && <BriefcaseBusiness size={16} />}
                <span>{item}</span>
              </button>
            ))}
          </nav>
          <div className="sidebar-footer">
            <CheckCircle2 size={16} />
            <span>{notice || 'No recent alerts'}</span>
          </div>
        </aside>

        <main className="main-panel">
          {viewByTab[activeTab] ? viewByTab[activeTab]() : null}
        </main>
      </div>
      {isAppointmentFormOpen ? (
        <div className="modal-overlay" onClick={() => setIsAppointmentFormOpen(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="panel-header">
              <h3>Schedule counseling session</h3>
              <button type="button" className="text-button" onClick={() => setIsAppointmentFormOpen(false)}>Close</button>
            </div>
            <div className="form-grid">
              <label>Student<select value={appointmentForm.student_id} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, student_id: event.target.value }))}>
                <option value="">Select student</option>
                {students.map((student) => <option key={student.student_id} value={student.student_id}>{student.student_id} · {student.name}</option>)}
              </select></label>
              <label>Faculty counselor<select value={appointmentForm.counselor_name} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, counselor_name: event.target.value }))}>
                {['Prof. Aditi Nair', 'Dr. Meera Singh'].map((person) => <option key={person} value={person}>{person}</option>)}
              </select></label>
              <label>Date<input type="date" value={appointmentForm.appointment_date} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, appointment_date: event.target.value }))} /></label>
              <label>Time<input type="time" value={appointmentForm.appointment_time} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, appointment_time: event.target.value }))} /></label>
              <label>Session type<select value={appointmentForm.session_type} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, session_type: event.target.value }))}>
                {['Academic counseling', 'Financial support review', 'Progress review', 'Mentoring session'].map((session) => <option key={session} value={session}>{session}</option>)}
              </select></label>
              <label>Status<select value={appointmentForm.status} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, status: event.target.value }))}>
                {['Scheduled', 'Pending', 'Completed'].map((status) => <option key={status} value={status}>{status}</option>)}
              </select></label>
              <label>Follow-up date<input type="date" value={appointmentForm.follow_up} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, follow_up: event.target.value }))} /></label>
            </div>
            <div className="modal-actions">
              <button type="button" className="small-button muted" onClick={() => setIsAppointmentFormOpen(false)}>Cancel</button>
              <button type="button" className="primary-button" onClick={createAppointment}>Save appointment</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default App
