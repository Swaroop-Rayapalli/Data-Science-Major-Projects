from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
import joblib
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

student_bp = Blueprint('student', __name__)

# Load model once at module level
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'student_performance_model.pkl')

try:
    student_model = joblib.load(MODEL_PATH)
    print(f"[Student] Model loaded successfully: {type(student_model).__name__}")
except Exception as e:
    student_model = None
    print(f"[Student] ERROR loading model: {e}")


def get_risk_level(score):
    """Determine risk level based on predicted score."""
    score = round(score, 2)
    if score >= 80:
        return 'Low Risk', 'success'
    elif score >= 60:
        return 'Medium Risk', 'warning'
    else:
        return 'High Risk', 'danger'


@student_bp.route('/', methods=['GET', 'POST'])
@login_required
def predict():
    from __init__ import db
    from database.models import StudentPrediction

    result = None
    recent_predictions = StudentPrediction.query.order_by(
        StudentPrediction.created_at.desc()
    ).limit(5).all()

    if request.method == 'POST':
        try:
            student_name = request.form.get('student_name', 'Anonymous').strip() or 'Anonymous'
            hours_studied = float(request.form.get('hours_studied', 0))
            previous_scores = float(request.form.get('previous_scores', 0))
            extracurricular = int(request.form.get('extracurricular', 0))
            sleep_hours = float(request.form.get('sleep_hours', 0))
            sample_papers = int(request.form.get('sample_papers', 0))

            if student_model is None:
                flash('Student prediction model is not available.', 'danger')
                return redirect(url_for('student.predict'))

            # Features: Hours Studied, Previous Scores, Extracurricular Activities, Sleep Hours, Sample Question Papers Practiced
            features = np.array([[hours_studied, previous_scores, extracurricular, sleep_hours, sample_papers]])
            predicted_score = float(student_model.predict(features)[0])
            predicted_score = max(0, min(100, predicted_score))  # Clamp to [0, 100]

            risk_level, risk_class = get_risk_level(predicted_score)

            # Save to database
            prediction = StudentPrediction(
                student_name=student_name,
                hours_studied=hours_studied,
                previous_scores=previous_scores,
                extracurricular=extracurricular,
                sleep_hours=sleep_hours,
                sample_papers=sample_papers,
                predicted_score=predicted_score,
                risk_level=risk_level
            )
            db.session.add(prediction)
            db.session.commit()

            result = {
                'student_name': student_name,
                'predicted_score': round(predicted_score, 2),
                'risk_level': risk_level,
                'risk_class': risk_class,
                'hours_studied': hours_studied,
                'previous_scores': previous_scores,
                'sleep_hours': sleep_hours,
                'sample_papers': sample_papers
            }

            recent_predictions = StudentPrediction.query.order_by(
                StudentPrediction.created_at.desc()
            ).limit(5).all()

        except ValueError as e:
            flash(f'Invalid input: Please enter valid numbers. {str(e)}', 'danger')
        except Exception as e:
            flash(f'Prediction error: {str(e)}', 'danger')

    return render_template('student.html', result=result, recent=recent_predictions)
