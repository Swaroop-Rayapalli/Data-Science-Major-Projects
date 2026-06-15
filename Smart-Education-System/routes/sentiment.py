from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
import joblib
import os
import warnings
warnings.filterwarnings('ignore')

sentiment_bp = Blueprint('sentiment', __name__)

# Load model and vectorizer once at module level
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VECTORIZER_PATH = os.path.join(BASE_DIR, 'models', 'vectorizer (1).pkl')
SENTIMENT_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sentiment_model.pkl')

try:
    vectorizer = joblib.load(VECTORIZER_PATH)
    sentiment_model = joblib.load(SENTIMENT_MODEL_PATH)
    print(f"[Sentiment] Models loaded successfully.")
    print(f"  Vectorizer: {type(vectorizer).__name__}")
    print(f"  Model: {type(sentiment_model).__name__}, Classes: {sentiment_model.classes_}")
except Exception as e:
    vectorizer = None
    sentiment_model = None
    print(f"[Sentiment] ERROR loading models: {e}")

# Class mapping: 0=Negative, 1=Positive
SENTIMENT_LABELS = {0: 'Negative', 1: 'Positive'}
SENTIMENT_ICONS = {'Positive': '😊', 'Negative': '😞', 'Neutral': '😐'}
SENTIMENT_CLASSES = {'Positive': 'success', 'Negative': 'danger', 'Neutral': 'secondary'}


@sentiment_bp.route('/', methods=['GET', 'POST'])
@login_required
def analyze():
    from __init__ import db
    from database.models import FeedbackAnalysis

    result = None
    recent_feedback = FeedbackAnalysis.query.order_by(
        FeedbackAnalysis.created_at.desc()
    ).limit(5).all()

    if request.method == 'POST':
        try:
            student_name = request.form.get('student_name', 'Anonymous').strip() or 'Anonymous'
            feedback_text = request.form.get('feedback', '').strip()

            if not feedback_text:
                flash('Please enter feedback text to analyze.', 'warning')
                return redirect(url_for('sentiment.analyze'))

            if vectorizer is None or sentiment_model is None:
                flash('Sentiment analysis model is not available.', 'danger')
                return redirect(url_for('sentiment.analyze'))

            # Transform and predict
            X = vectorizer.transform([feedback_text])
            pred_class = int(sentiment_model.predict(X)[0])
            proba = sentiment_model.predict_proba(X)[0]
            confidence = float(max(proba))

            sentiment = SENTIMENT_LABELS.get(pred_class, 'Neutral')

            # Save to database
            analysis = FeedbackAnalysis(
                student_name=student_name,
                feedback=feedback_text,
                sentiment=sentiment,
                confidence=confidence
            )
            db.session.add(analysis)
            db.session.commit()

            result = {
                'student_name': student_name,
                'feedback': feedback_text,
                'sentiment': sentiment,
                'confidence': round(confidence * 100, 1),
                'sentiment_icon': SENTIMENT_ICONS.get(sentiment, '🤔'),
                'sentiment_class': SENTIMENT_CLASSES.get(sentiment, 'secondary'),
                'proba_positive': round(float(proba[1]) * 100, 1) if len(proba) > 1 else 0,
                'proba_negative': round(float(proba[0]) * 100, 1)
            }

            recent_feedback = FeedbackAnalysis.query.order_by(
                FeedbackAnalysis.created_at.desc()
            ).limit(5).all()

        except Exception as e:
            flash(f'Analysis error: {str(e)}', 'danger')

    return render_template('sentiment.html', result=result, recent=recent_feedback)
