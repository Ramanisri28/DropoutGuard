import json
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / 'trained_model.joblib'
TARGET_COLUMN_ALIASES = {
    'dropout',
    'dropout_status',
    'dropout_risk',
    'historical_outcome',
    'outcome',
    'at_risk',
    'risk',
    'risk_status',
    'risk_category',
    'risk_label',
    'risk_level',
    'status',
    'outcome_status',
    'student_outcome',
    'student_status',
    'academic_status',
    'retention_status',
}
METADATA_COLUMNS = {
    'student_id',
    'id',
    'name',
    'student_name',
    'full_name',
    'department',
    'dept',
    'program',
    'course',
    'year',
    'academic_year',
    'study_year',
    'semester',
    'term',
    'last_counseling_date',
    'counseling_date',
}
POSITIVE_TARGET_VALUES = {
    '1',
    'yes',
    'true',
    'high',
    'medium',
    'at risk',
    'atrisk',
    'dropout risk',
    'dropout',
    'dropped out',
    'fail',
    'failed',
    'failing',
    'not retained',
    'unsuccessful',
    'critical',
    'needs support',
}
NEGATIVE_TARGET_VALUES = {
    '0',
    'no',
    'false',
    'low',
    'safe',
    'on track',
    'active',
    'retained',
    'success',
    'successful',
    'no risk',
    'not at risk',
    'stable',
}


def get_target_column(columns):
    return next((column for column in columns if column in TARGET_COLUMN_ALIASES), None)


def get_training_readiness(columns):
    target_column = get_target_column(columns)
    feature_columns = [
        column for column in columns
        if column != target_column and column not in METADATA_COLUMNS
    ]
    missing_columns = []
    if not target_column:
        missing_columns.append('risk_status or outcome')
    if target_column and not feature_columns:
        missing_columns.append('student data columns')
    return target_column, feature_columns, missing_columns


def _normalize_binary_column(values, column_name):
    normalized = (
        values.astype('string')
        .str.strip()
        .str.lower()
        .str.replace(r'[_-]+', ' ', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
    )
    mapped = normalized.map(
        {value: 1 for value in POSITIVE_TARGET_VALUES}
        | {value: 0 for value in NEGATIVE_TARGET_VALUES}
    )
    unknown_values = normalized[normalized.notna() & mapped.isna()].unique().tolist()
    if unknown_values:
        raise ValueError(
            f"Column '{column_name}' must use 0/1, Yes/No, or True/False values. "
            f"Unsupported values: {', '.join(unknown_values[:5])}"
        )
    return mapped


def _get_dataset_path():
    upload_dir = BASE_DIR / 'uploads'
    active_dataset = upload_dir / 'active_dataset.csv'
    if active_dataset.exists():
        return active_dataset
    legacy_dataset = upload_dir / 'uploaded_students.csv'
    if legacy_dataset.exists():
        return legacy_dataset
    candidates = sorted(upload_dir.glob('*.csv'))
    if not candidates:
        raise FileNotFoundError('No uploaded dataset found. Please upload a CSV file first.')
    return candidates[-1]


def _infer_risk_labels(df, feature_cols):
    """Auto-generate risk labels (0/1) based on data characteristics."""
    risk_flags = pd.Series(0, index=df.index, dtype=int)
    
    # Check for low attendance (< 75%)
    attendance_cols = [col for col in feature_cols if 'attendance' in col.lower()]
    for col in attendance_cols:
        numeric_vals = pd.to_numeric(df[col], errors='coerce')
        risk_flags += (numeric_vals < 75).fillna(False).astype(int)
    
    # Check for low marks/grades (< 60)
    marks_cols = [col for col in feature_cols if any(x in col.lower() for x in ['mark', 'score', 'grade', 'gpa', 'average'])]
    for col in marks_cols:
        numeric_vals = pd.to_numeric(df[col], errors='coerce')
        risk_flags += (numeric_vals < 60).fillna(False).astype(int)
    
    # Check for high backlogs (>= 2)
    backlog_cols = [col for col in feature_cols if 'backlog' in col.lower()]
    for col in backlog_cols:
        numeric_vals = pd.to_numeric(df[col], errors='coerce')
        risk_flags += (numeric_vals >= 2).fillna(False).astype(int)
    
    # Check for financial difficulty indicators
    financial_cols = [col for col in feature_cols if any(x in col.lower() for x in ['financial', 'support', 'aid'])]
    for col in financial_cols:
        str_vals = df[col].astype(str).str.lower()
        risk_flags += (str_vals.isin(['yes', 'high', 'critical', 'needed', 'required'])).astype(int)
    
    # Normalize: students with 2+ risk factors are high-risk (1), otherwise low-risk (0)
    return (risk_flags >= 2).astype(int)


def train_model_from_file(dataset_path=None):
    path = Path(dataset_path) if dataset_path else _get_dataset_path()
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError('The dataset is empty. Please upload a valid CSV file.')

    target_column, feature_cols, missing_columns = get_training_readiness(df.columns)
    
    # If no target column exists, auto-generate labels based on risk indicators
    if not target_column:
        if not feature_cols:
            raise ValueError('Add at least one student data column to train the model.')
        feature_cols = [column for column in feature_cols if df[column].notna().any()]
        if not feature_cols:
            raise ValueError('The student data columns are empty; add at least one value before training.')
        y = _infer_risk_labels(df, feature_cols)
    else:
        if not feature_cols:
            raise ValueError('Add at least one student data column besides the outcome/status.')
        feature_cols = [column for column in feature_cols if df[column].notna().any()]
        if not feature_cols:
            raise ValueError('The student data columns are empty; add at least one value before training.')
        y = _normalize_binary_column(df[target_column], target_column)
        if y.isna().any():
            raise ValueError(f"Column '{target_column}' cannot contain blank values.")
    if y.value_counts().min() < 2:
        raise ValueError('The outcome/status column needs at least two rows for each class.')
    if y.nunique() < 2:
        raise ValueError('The target column has only one class, so the model cannot be trained reliably.')

    X = df[feature_cols].copy()
    numeric_columns = []
    categorical_columns = []
    for column in feature_cols:
        raw_values = X[column]
        numeric_source = (
            raw_values.astype('string')
            .str.replace(',', '', regex=False)
            .str.replace('%', '', regex=False)
        )
        numeric_values = pd.to_numeric(numeric_source, errors='coerce')
        if raw_values.notna().sum() and numeric_values.notna().sum() == raw_values.notna().sum():
            X[column] = numeric_values
            numeric_columns.append(column)
        else:
            categorical_columns.append(column)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    transformers = []
    if numeric_columns:
        transformers.append((
            'numeric',
            Pipeline(steps=[('imputer', SimpleImputer(strategy='median'))]),
            numeric_columns,
        ))
    if categorical_columns:
        transformers.append((
            'categorical',
            Pipeline(
                steps=[
                    ('imputer', SimpleImputer(strategy='most_frequent')),
                    ('onehot', OneHotEncoder(handle_unknown='ignore')),
                ]
            ),
            categorical_columns,
        ))

    preprocessor = ColumnTransformer(
        transformers=transformers,
    )

    model = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')
    pipeline = Pipeline(steps=[('preprocessor', preprocessor), ('model', model)])
    pipeline.fit(X_train, y_train)

    preds = pipeline.predict(X_test)
    precision = precision_score(y_test, preds, average='weighted', zero_division=0)
    recall = recall_score(y_test, preds, average='weighted', zero_division=0)
    f1 = f1_score(y_test, preds, average='weighted', zero_division=0)
    acc = accuracy_score(y_test, preds)
    confusion = confusion_matrix(y_test, preds, labels=[0, 1]).tolist()

    payload = {
        'model_name': 'RandomForestClassifier',
        'version': 'v1.0.0',
        'dataset_name': path.name,
        'metrics': {
            'accuracy': float(acc),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'confusion_matrix': confusion,
            'target_distribution': {str(k): int(v) for k, v in y.value_counts().sort_index().to_dict().items()},
        },
        'trained_at': pd.Timestamp.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    joblib.dump({'model': pipeline, 'feature_columns': feature_cols, 'metadata': payload}, MODEL_PATH)
    return payload


def load_model():
    if not MODEL_PATH.exists():
        return None
    loaded = joblib.load(MODEL_PATH)
    return loaded


def predict_student_risk(student_record, model_bundle=None):
    if model_bundle is None:
        model_bundle = load_model()
    if model_bundle is None:
        return {'risk_category': 'Medium', 'score': 0.5, 'source': 'rule-based demo mode'}

    pipeline = model_bundle['model']
    feature_names = model_bundle['feature_columns']
    data = pd.DataFrame([student_record])[feature_names]
    positive_class_indices = [index for index, label in enumerate(pipeline.classes_) if str(label) == '1']
    probability = (
        float(pipeline.predict_proba(data)[0][positive_class_indices[0]])
        if positive_class_indices
        else 0.5
    )
    if probability >= 0.7:
        risk_category = 'High'
    elif probability >= 0.4:
        risk_category = 'Medium'
    else:
        risk_category = 'Low'
    return {
        'risk_category': risk_category,
        'score': float(probability),
        'source': 'trained model',
    }
