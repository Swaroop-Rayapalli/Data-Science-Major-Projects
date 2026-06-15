from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    from database.models import StudentPrediction, FeedbackAnalysis, ResumeResult

    # Student stats
    total_students = StudentPrediction.query.count()
    avg_score_result = StudentPrediction.query.with_entities(
        func.avg(StudentPrediction.predicted_score)
    ).scalar()
    avg_score = round(float(avg_score_result), 1) if avg_score_result else 0

    # Risk distribution
    low_risk = StudentPrediction.query.filter_by(risk_level='Low Risk').count()
    medium_risk = StudentPrediction.query.filter_by(risk_level='Medium Risk').count()
    high_risk = StudentPrediction.query.filter_by(risk_level='High Risk').count()

    # Sentiment stats
    total_feedback = FeedbackAnalysis.query.count()
    positive_count = FeedbackAnalysis.query.filter_by(sentiment='Positive').count()
    negative_count = FeedbackAnalysis.query.filter_by(sentiment='Negative').count()
    positive_pct = round((positive_count / total_feedback * 100), 1) if total_feedback > 0 else 0

    # Resume stats
    total_resumes = ResumeResult.query.count()
    avg_match_result = ResumeResult.query.with_entities(
        func.avg(ResumeResult.match_score)
    ).scalar()
    avg_match = round(float(avg_match_result), 1) if avg_match_result else 0

    # Top resume categories
    from collections import Counter
    resume_categories_raw = ResumeResult.query.with_entities(ResumeResult.category).all()
    category_counts = Counter([r[0] for r in resume_categories_raw])
    top_categories = category_counts.most_common(6)

    # Recent activity
    recent_students = StudentPrediction.query.order_by(
        StudentPrediction.created_at.desc()
    ).limit(5).all()

    recent_feedback = FeedbackAnalysis.query.order_by(
        FeedbackAnalysis.created_at.desc()
    ).limit(5).all()

    recent_resumes = ResumeResult.query.order_by(
        ResumeResult.created_at.desc()
    ).limit(5).all()

    return render_template('dashboard.html',
        # Summary cards
        total_students=total_students,
        avg_score=avg_score,
        positive_pct=positive_pct,
        total_resumes=total_resumes,
        avg_match=avg_match,
        total_feedback=total_feedback,

        # Chart data
        low_risk=low_risk,
        medium_risk=medium_risk,
        high_risk=high_risk,
        positive_count=positive_count,
        negative_count=negative_count,
        top_categories=top_categories,

        # Recent records
        recent_students=recent_students,
        recent_feedback=recent_feedback,
        recent_resumes=recent_resumes
    )
