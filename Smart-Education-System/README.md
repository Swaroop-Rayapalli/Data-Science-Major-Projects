# 🎓 Smart Education Analytics Platform

A full-stack Flask web application powered by Machine Learning for student performance prediction, feedback sentiment analysis, and resume screening.

## 🚀 Features

| Module | Technology | Description |
|--------|-----------|-------------|
| **Student Prediction** | Linear Regression | Predicts student performance score from academic habits |
| **Sentiment Analysis** | Naive Bayes + CountVectorizer | Classifies student feedback as Positive/Negative |
| **Resume Screening** | LinearSVC + TF-IDF Pipeline | Categorizes resumes into 24 job domains |
| **Dashboard** | Chart.js | Analytics overview with real-time charts |
| **Database** | SQLite / SQLAlchemy | Persistent storage of all predictions |

## 📁 Project Structure

```
Smart-Education-System/
├── app.py                          # Flask entry point
├── __init__.py                     # App factory
├── requirements.txt                # Dependencies
├── Procfile                        # Render deployment
├── runtime.txt                     # Python version
│
├── models/                         # Trained ML models
│   ├── student_performance_model.pkl   # LinearRegression
│   ├── sentiment_model.pkl             # MultinomialNB
│   ├── vectorizer (1).pkl              # CountVectorizer
│   ├── resume_model.pkl                # Pipeline (TF-IDF + LinearSVC)
│   └── label_encoder.pkl               # Label Encoder
│
├── routes/                         # Flask Blueprints
│   ├── dashboard.py                # Dashboard analytics
│   ├── student.py                  # Student prediction
│   ├── sentiment.py                # Sentiment analysis
│   └── resume.py                   # Resume screening
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html                   # Shared layout
│   ├── dashboard.html              # Main dashboard
│   ├── student.html                # Student form
│   ├── sentiment.html              # Feedback form
│   └── resume.html                 # Resume upload
│
├── static/
│   ├── css/style.css               # Dark theme stylesheet
│   └── js/app.js                   # Platform JavaScript
│
├── database/
│   └── smart_education.db          # SQLite database (auto-created)
│
└── uploads/                        # Uploaded resume PDFs
```

## ⚙️ Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Open: http://127.0.0.1:5000

## 🤖 Model Details

### Student Performance Prediction
- **Model**: Linear Regression
- **Features**: Hours Studied, Previous Scores, Extracurricular Activities, Sleep Hours, Sample Papers
- **Output**: Predicted Score (0-100), Risk Level (Low/Medium/High)
- **Risk Logic**: ≥80 = Low Risk | 60-79 = Medium Risk | <60 = High Risk

### Feedback Sentiment Analysis  
- **Model**: Multinomial Naive Bayes
- **Vectorizer**: CountVectorizer
- **Classes**: 0 = Negative, 1 = Positive
- **Output**: Sentiment label + confidence probability

### Resume Screening
- **Model**: Pipeline (TF-IDF Vectorizer + LinearSVC)
- **Categories**: 24 job domains (Data Science, Java Developer, HR, etc.)
- **Output**: Category, Match Score (keyword-based)

## 🗄️ Database Schema

```sql
StudentPrediction: id, student_name, hours_studied, previous_scores, 
                   extracurricular, sleep_hours, sample_papers, 
                   predicted_score, risk_level, created_at

FeedbackAnalysis:  id, student_name, feedback, sentiment, 
                   confidence, created_at

ResumeResult:      id, candidate_name, filename, category, 
                   match_score, extracted_text_preview, created_at
```

## 📊 Power BI Integration

Connect Power BI Desktop to the SQLite database:
1. Open Power BI → Get Data → ODBC
2. Navigate to: `database/smart_education.db`
3. Import tables: `student_predictions`, `feedback_analysis`, `resume_results`

## 🚢 Deployment (Render)

1. Push to GitHub repository
2. Create new Web Service on [render.com](https://render.com)
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Add environment variable: `FLASK_ENV=production`

## 🔧 MySQL Migration

To upgrade from SQLite to MySQL, update `__init__.py`:
```python
# Replace SQLite URI with MySQL URI
app.config['SQLALCHEMY_DATABASE_URI'] = \
    'mysql+pymysql://username:password@localhost/smart_education'
```

Install: `pip install PyMySQL`

## 📦 Tech Stack

- **Backend**: Flask 3.0, SQLAlchemy, Werkzeug
- **ML**: scikit-learn 1.6.1, joblib, numpy, pandas
- **PDF**: PyPDF2
- **Frontend**: Bootstrap 5, Chart.js 4, Bootstrap Icons
- **DB**: SQLite (dev) / MySQL (prod)
- **Deploy**: Render + Gunicorn

---
Built with ❤️ | Smart Education Analytics Platform
