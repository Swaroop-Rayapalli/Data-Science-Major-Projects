from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required
import joblib
import os
import re
import warnings
warnings.filterwarnings('ignore')

resume_bp = Blueprint('resume', __name__)

# Load model and label encoder once at module level
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RESUME_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'resume_model.pkl')
LABEL_ENCODER_PATH = os.path.join(BASE_DIR, 'models', 'label_encoder.pkl')

try:
    resume_pipeline = joblib.load(RESUME_MODEL_PATH)
    label_encoder = joblib.load(LABEL_ENCODER_PATH)
    print(f"[Resume] Models loaded successfully.")
    print(f"  Pipeline: {type(resume_pipeline).__name__}")
    print(f"  Categories: {len(label_encoder.classes_)} classes")
except Exception as e:
    resume_pipeline = None
    label_encoder = None
    print(f"[Resume] ERROR loading models: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Category name mapping (24 job categories)
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_NAMES = {
    0: 'Advocate', 1: 'Arts', 2: 'Automation Testing', 3: 'Blockchain',
    4: 'Business Analyst', 5: 'Civil Engineer', 6: 'Data Science',
    7: 'Database', 8: 'DevOps Engineer', 9: 'DotNet Developer',
    10: 'ETL Developer', 11: 'Electrical Engineering', 12: 'HR',
    13: 'Hadoop', 14: 'Health and Fitness', 15: 'Java Developer',
    16: 'Mechanical Engineer', 17: 'Network Security Engineer',
    18: 'Operations Manager', 19: 'PMO', 20: 'Python Developer',
    21: 'SAP Developer', 22: 'Sales', 23: 'Testing'
}

# ─────────────────────────────────────────────────────────────────────────────
# Per-category keyword sets used for match scoring
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    'Data Science':             ['python', 'machine learning', 'data', 'pandas', 'numpy', 'tensorflow', 'sklearn', 'statistics', 'sql'],
    'Java Developer':           ['java', 'spring', 'maven', 'hibernate', 'jvm', 'j2ee', 'microservices'],
    'Python Developer':         ['python', 'django', 'flask', 'fastapi', 'pandas', 'numpy', 'aws'],
    'DevOps Engineer':          ['docker', 'kubernetes', 'jenkins', 'ci/cd', 'aws', 'linux', 'ansible', 'terraform'],
    'Database':                 ['sql', 'mysql', 'postgresql', 'oracle', 'mongodb', 'nosql', 'query'],
    'Blockchain':               ['blockchain', 'ethereum', 'solidity', 'smart contract', 'web3', 'crypto'],
    'HR':                       ['recruitment', 'human resources', 'hr', 'talent', 'payroll', 'onboarding'],
    'Network Security Engineer':['network', 'security', 'firewall', 'cisco', 'vpn', 'penetration testing'],
    'Testing':                  ['testing', 'selenium', 'junit', 'test automation', 'qa', 'quality assurance'],
    'Automation Testing':       ['selenium', 'appium', 'robot framework', 'pytest', 'qa', 'automation', 'ci/cd'],
    'Civil Engineer':           ['civil', 'construction', 'autocad', 'structural', 'project management'],
    'Electrical Engineering':   ['electrical', 'circuit', 'plc', 'scada', 'power', 'matlab', 'embedded'],
    'Mechanical Engineer':      ['mechanical', 'solidworks', 'autocad', 'catia', 'manufacturing', 'cad'],
    'DotNet Developer':         ['c#', '.net', 'asp.net', 'entity framework', 'wpf', 'azure', 'mvc'],
    'ETL Developer':            ['etl', 'informatica', 'ssis', 'talend', 'data warehouse', 'sql', 'pipeline'],
    'Hadoop':                   ['hadoop', 'hive', 'spark', 'hdfs', 'mapreduce', 'kafka', 'big data'],
    'Business Analyst':         ['business analysis', 'requirements', 'stakeholder', 'agile', 'jira', 'bpmn', 'sql'],
    'SAP Developer':            ['sap', 'abap', 'hana', 's/4hana', 'fiori', 'bapi', 'bdc'],
    'PMO':                      ['project management', 'pmp', 'agile', 'scrum', 'risk management', 'pmo', 'prince2'],
    'Operations Manager':       ['operations', 'supply chain', 'logistics', 'kpi', 'process improvement', 'lean', 'six sigma'],
    'Sales':                    ['sales', 'crm', 'lead generation', 'target', 'revenue', 'b2b', 'negotiation'],
    'Advocate':                 ['legal', 'law', 'litigation', 'court', 'contract', 'compliance', 'attorney'],
    'Arts':                     ['design', 'creative', 'photoshop', 'illustrator', 'portfolio', 'adobe', 'visual'],
    'Health and Fitness':       ['fitness', 'nutrition', 'health', 'wellness', 'personal trainer', 'exercise', 'diet'],
}

# ─────────────────────────────────────────────────────────────────────────────
# Per-category suggestions
# Each entry: skills_to_add, tools, certifications, action_tips
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_SUGGESTIONS = {
    'Data Science': {
        'skills_missing':  ['Deep Learning', 'NLP', 'Feature Engineering', 'A/B Testing', 'Data Visualization'],
        'tools':           ['TensorFlow / PyTorch', 'Power BI / Tableau', 'Apache Spark', 'MLflow', 'Jupyter'],
        'certifications':  ['Google Data Analytics Certificate', 'IBM Data Science Professional', 'AWS Certified ML – Specialty'],
        'tips': [
            'Build end-to-end ML projects on Kaggle and host on GitHub.',
            'Contribute to open-source datasets or Kaggle competitions.',
            'Add a portfolio section with interactive dashboards (Streamlit / Plotly).',
            'Quantify impact: "Improved model accuracy by 12% using feature engineering."',
        ],
    },
    'Python Developer': {
        'skills_missing':  ['FastAPI', 'Async Programming', 'Celery', 'Redis', 'Unit Testing (pytest)'],
        'tools':           ['Docker', 'CI/CD (GitHub Actions)', 'PostgreSQL', 'Swagger/OpenAPI', 'Redis'],
        'certifications':  ['Python Institute PCEP / PCAP', 'AWS Certified Developer', 'Django REST Framework Specialist'],
        'tips': [
            'Showcase REST APIs with Swagger docs in your portfolio.',
            'Add coverage reports and unit tests to every GitHub repo.',
            'Highlight async/concurrent Python (asyncio, aiohttp).',
            'Include deployed projects (Heroku / Render / AWS EC2).',
        ],
    },
    'Java Developer': {
        'skills_missing':  ['Spring Boot', 'Microservices', 'Kafka', 'JUnit 5', 'CI/CD'],
        'tools':           ['IntelliJ IDEA', 'Maven/Gradle', 'Docker', 'Kafka', 'SonarQube'],
        'certifications':  ['Oracle Certified Java Programmer (OCP)', 'Spring Professional Certification', 'AWS Developer Associate'],
        'tips': [
            'Add system design experience (e.g., high-throughput microservices).',
            'Show expertise in REST + GraphQL API design.',
            'Highlight experience with JVM tuning and garbage collection.',
            'Include code quality tools: Checkstyle, SpotBugs, SonarQube.',
        ],
    },
    'DevOps Engineer': {
        'skills_missing':  ['Terraform IaC', 'GitOps', 'Prometheus + Grafana', 'ArgoCD', 'Istio Service Mesh'],
        'tools':           ['Kubernetes (K8s)', 'Helm Charts', 'GitHub Actions', 'Datadog', 'HashiCorp Vault'],
        'certifications':  ['CKA – Certified Kubernetes Administrator', 'AWS DevOps Engineer Pro', 'HashiCorp Terraform Associate'],
        'tips': [
            'List specific cloud cost savings achieved (e.g., "Reduced AWS spend by 30%").',
            'Highlight zero-downtime deployment strategies.',
            'Document SRE practices: SLOs, SLIs, error budgets.',
            'Build a homelab and share configs on GitHub.',
        ],
    },
    'Database': {
        'skills_missing':  ['Query Optimization', 'Partitioning & Sharding', 'Graph Databases', 'Redis Caching', 'Data Modelling'],
        'tools':           ['PostgreSQL', 'MongoDB Atlas', 'Redis', 'DBeaver', 'Apache Cassandra'],
        'certifications':  ['Oracle Database SQL Certified Associate', 'MongoDB Associate DBA', 'AWS Database Specialty'],
        'tips': [
            'Include examples of complex query optimisation (execution plans).',
            'Showcase ETL pipelines or data migration projects.',
            'Add experience with replication, failover, and disaster recovery.',
            'List the largest database volume you have managed.',
        ],
    },
    'Blockchain': {
        'skills_missing':  ['Solidity / Rust', 'Smart Contract Auditing', 'DeFi Protocols', 'Layer 2 Solutions', 'IPFS'],
        'tools':           ['Hardhat / Truffle', 'MetaMask', 'IPFS', 'OpenZeppelin', 'Etherscan'],
        'certifications':  ['Certified Blockchain Developer (CBDE)', 'ConsenSys Ethereum Developer', 'Hyperledger Fabric Developer'],
        'tips': [
            'Publish audited smart contracts on Etherscan.',
            'Contribute to open-source DeFi / NFT projects.',
            'Add links to testnet-deployed contracts in your resume.',
            'Highlight gas optimisation techniques used.',
        ],
    },
    'HR': {
        'skills_missing':  ['HRIS Systems', 'People Analytics', 'Employer Branding', 'DEI Initiatives', 'Compensation Benchmarking'],
        'tools':           ['Workday', 'SAP SuccessFactors', 'BambooHR', 'LinkedIn Recruiter', 'Tableau'],
        'certifications':  ['SHRM-CP / SHRM-SCP', 'PHR – Professional in HR', 'Google Data Analytics (for HR metrics)'],
        'tips': [
            'Quantify hiring impact: "Reduced time-to-hire from 45 to 28 days."',
            'Highlight retention programs you designed and their outcomes.',
            'Show experience running performance management cycles.',
            'Add employer branding initiatives or employee NPS scores.',
        ],
    },
    'Network Security Engineer': {
        'skills_missing':  ['Zero Trust Architecture', 'SIEM Tools', 'Cloud Security (AWS/Azure)', 'Incident Response', 'Threat Hunting'],
        'tools':           ['Splunk / QRadar', 'Wireshark', 'Nessus', 'CrowdStrike', 'Palo Alto NGFW'],
        'certifications':  ['CompTIA Security+', 'CEH – Certified Ethical Hacker', 'CISSP / CISM'],
        'tips': [
            'List CVEs discovered or vulnerabilities remediated.',
            'Show pentesting reports (sanitized) or CTF achievements.',
            'Include specific compliance frameworks: ISO 27001, NIST, SOC 2.',
            'Add an online lab environment (TryHackMe / HackTheBox profile).',
        ],
    },
    'Testing': {
        'skills_missing':  ['API Testing (Postman/RestAssured)', 'Performance Testing (JMeter)', 'BDD (Cucumber)', 'Mobile Testing', 'Security Testing Basics'],
        'tools':           ['Selenium WebDriver', 'JMeter', 'Postman', 'Allure Reports', 'TestRail'],
        'certifications':  ['ISTQB Foundation Level', 'Certified Agile Tester', 'Selenium with Java / Python (Udemy)'],
        'tips': [
            'Include defect density and test coverage metrics.',
            'Showcase shift-left testing experience.',
            'Add a testing framework you built or significantly improved.',
            'Highlight cross-browser and cross-device testing experience.',
        ],
    },
    'Automation Testing': {
        'skills_missing':  ['Page Object Model', 'API Automation (RestAssured)', 'CI/CD Integration', 'Performance Automation', 'AI-based Testing'],
        'tools':           ['Selenium / Playwright / Cypress', 'TestNG / JUnit', 'Jenkins', 'Allure', 'Appium'],
        'certifications':  ['ISTQB Agile Tester', 'Test Automation University (TAU)', 'Postman API Fundamentals'],
        'tips': [
            'Show test execution time reduction achieved through automation.',
            'Highlight framework architecture you designed from scratch.',
            'Include CI/CD pipeline integration steps.',
            'Add test failure analytics dashboards built.',
        ],
    },
    'Civil Engineer': {
        'skills_missing':  ['BIM (Building Information Modelling)', 'GIS Mapping', 'Cost Estimation', 'Sustainability / Green Building', 'STAAD Pro'],
        'tools':           ['AutoCAD / Civil 3D', 'Revit BIM', 'ETABS', 'MS Project', 'Primavera P6'],
        'certifications':  ['PMP – Project Management Professional', 'LEED Green Associate', 'AutoCAD Certified User'],
        'tips': [
            'List project values (e.g., "Managed construction of ₹50Cr commercial complex").',
            'Show on-time and on-budget delivery records.',
            'Include safety record (zero accidents / LTI-free duration).',
            'Add site photos / renders to your LinkedIn portfolio.',
        ],
    },
    'Electrical Engineering': {
        'skills_missing':  ['Embedded Systems (ARM/RTOS)', 'PCB Design (Altium)', 'Power Electronics', 'IoT Protocols', 'MATLAB/Simulink'],
        'tools':           ['Altium Designer', 'MATLAB / Simulink', 'LabVIEW', 'KiCad', 'Proteus'],
        'certifications':  ['Certified Automation Professional (CAP)', 'Six Sigma Green Belt', 'PLC Programming (Siemens)'],
        'tips': [
            'Add patent applications or R&D project outcomes.',
            'Show power savings or efficiency gains achieved.',
            'Include experience with industrial standards (IEC, IEEE).',
            'Share PCB designs / schematics on GitHub or Hackster.io.',
        ],
    },
    'Mechanical Engineer': {
        'skills_missing':  ['FEA / CFD Analysis', 'GD&T (Geometric Dimensioning)', 'Lean Manufacturing', '3D Printing / Additive Mfg', 'Industry 4.0'],
        'tools':           ['SolidWorks / CATIA', 'ANSYS', 'Creo / NX', 'AutoCAD', 'MS Project'],
        'certifications':  ['Certified SolidWorks Professional (CSWP)', 'Six Sigma Green Belt', 'PMP'],
        'tips': [
            'Quantify design improvements (weight reduction, cost savings).',
            'Show cross-functional collaboration (design + manufacturing + QA).',
            'Add prototyping or hands-on lab experience.',
            'Include DFM / DFT (Design for Manufacturability / Testability) knowledge.',
        ],
    },
    'DotNet Developer': {
        'skills_missing':  ['Azure Cloud Services', 'Blazor WebAssembly', 'gRPC', 'SignalR', 'Entity Framework Core'],
        'tools':           ['Visual Studio / VS Code', 'Azure DevOps', 'SQL Server', 'Redis', 'RabbitMQ'],
        'certifications':  ['Microsoft Certified: Azure Developer Associate', 'MCP – .NET', 'AZ-204 Azure Developer'],
        'tips': [
            'Showcase migrated legacy .NET Framework apps to .NET 6/8.',
            'Add API versioning and OpenAPI/Swagger documentation.',
            'Highlight Clean Architecture / CQRS / MediatR patterns used.',
            'Include Azure hosting and deployment experience.',
        ],
    },
    'ETL Developer': {
        'skills_missing':  ['Cloud ETL (AWS Glue / Azure Data Factory)', 'Apache Airflow', 'dbt (Data Build Tool)', 'Delta Lake', 'Real-time Streaming (Kafka)'],
        'tools':           ['Informatica', 'SSIS / SSRS', 'Talend', 'Apache Airflow', 'Spark'],
        'certifications':  ['AWS Data Analytics Specialty', 'Azure Data Engineer Associate (DP-203)', 'Informatica Certified Developer'],
        'tips': [
            'Show data pipeline throughput (records/sec, TB processed).',
            'Highlight error handling, retry logic and alerting built.',
            'Add data quality and lineage tracking experience.',
            'Mention SLA adherence for batch jobs.',
        ],
    },
    'Hadoop': {
        'skills_missing':  ['Apache Spark (PySpark)', 'Kafka Streams', 'Delta Lake / Iceberg', 'Cloud Data Lakes (S3/ADLS)', 'DataBricks'],
        'tools':           ['Cloudera / Hortonworks', 'Apache Hive', 'Spark', 'Kafka', 'Zookeeper'],
        'certifications':  ['Cloudera Certified Associate (CCA)', 'AWS Big Data Specialty', 'Databricks Certified Associate'],
        'tips': [
            'Show data volumes processed (PBs, TBs).',
            'Highlight job tuning (memory, parallelism, partition strategy).',
            'Add real-time streaming pipeline examples.',
            'Transition examples to cloud-native data lakes (AWS/Azure).',
        ],
    },
    'Business Analyst': {
        'skills_missing':  ['Process Modelling (BPMN)', 'SQL for Data Analysis', 'Stakeholder Management', 'UAT Coordination', 'Wireframing (Figma/Balsamiq)'],
        'tools':           ['JIRA / Confluence', 'Power BI / Tableau', 'Lucidchart', 'MS Visio', 'Salesforce'],
        'certifications':  ['CBAP – Certified Business Analysis Professional', 'PMI-PBA', 'Agile BA (IIBA)'],
        'tips': [
            'Quantify business impact: "Reduced process cycle time by 35%."',
            'Show experience translating business needs to technical requirements.',
            'Add examples of dashboards built that drove decisions.',
            'Include cross-functional project coordination examples.',
        ],
    },
    'SAP Developer': {
        'skills_missing':  ['SAP S/4HANA Migration', 'SAP Fiori / UI5', 'SAP BTP (Business Technology Platform)', 'ABAP OO', 'SAP Integration Suite'],
        'tools':           ['SAP GUI', 'SAP Business Studio', 'Eclipse ADT', 'SAP HANA Studio', 'Postman (for APIs)'],
        'certifications':  ['SAP Certified Development Associate – ABAP', 'SAP Certified Associate – SAP Fiori', 'SAP S/4HANA Implementation'],
        'tips': [
            'Show end-to-end SAP implementation or upgrade projects.',
            'Add ABAP performance tuning and code inspector experience.',
            'Highlight custom development for specific SAP modules (FI, MM, SD).',
            'Include integration with non-SAP systems (REST/SOAP/OData).',
        ],
    },
    'PMO': {
        'skills_missing':  ['Earned Value Management (EVM)', 'Risk Register Management', 'Portfolio Management', 'Change Management', 'Resource Levelling'],
        'tools':           ['MS Project / Primavera', 'JIRA / Monday.com', 'Power BI (for dashboards)', 'Smartsheet', 'Confluence'],
        'certifications':  ['PMP – Project Management Professional', 'PRINCE2 Practitioner', 'PMI-ACP (Agile Certified Practitioner)'],
        'tips': [
            'Quantify project scale: budget managed, team size, duration.',
            'Show on-time and on-budget delivery percentages across portfolio.',
            'Add governance frameworks you designed or enforced.',
            'Highlight executive-level stakeholder reporting experience.',
        ],
    },
    'Operations Manager': {
        'skills_missing':  ['Lean Six Sigma', 'Supply Chain Optimisation', 'Workforce Planning', 'P&L Management', 'ERP Systems'],
        'tools':           ['SAP ERP / Oracle SCM', 'Power BI', 'MS Project', 'Tableau', 'WMS (Warehouse Mgmt)'],
        'certifications':  ['Six Sigma Black Belt', 'APICS CPIM / CSCP', 'PMP'],
        'tips': [
            'Use numbers: "Reduced operational costs by 22% YoY."',
            'Show SLA adherence and customer satisfaction scores.',
            'Highlight cross-department process improvements.',
            'Add team size managed and P&L ownership details.',
        ],
    },
    'Sales': {
        'skills_missing':  ['CRM Management (Salesforce/HubSpot)', 'Sales Forecasting', 'Account-based Marketing', 'Negotiation & Closing', 'Social Selling'],
        'tools':           ['Salesforce', 'HubSpot', 'LinkedIn Sales Navigator', 'Gong.io', 'Outreach'],
        'certifications':  ['Salesforce Certified Sales Cloud Consultant', 'HubSpot Sales Software Certification', 'Dale Carnegie Sales Training'],
        'tips': [
            'Lead with revenue numbers: "Generated ₹2.5Cr in new ARR in FY23."',
            'Show win rates, deal sizes and sales cycle lengths.',
            'Add territory or key account management experience.',
            'Highlight quota attainment % each year.',
        ],
    },
    'Advocate': {
        'skills_missing':  ['Legal Research (LexisNexis/Manupatra)', 'Contract Drafting', 'Dispute Resolution / ADR', 'Intellectual Property Law', 'Data Privacy (GDPR/IT Act)'],
        'tools':           ['LexisNexis / Westlaw', 'Manupatra', 'Clio / PracticePanther (Legal CRM)', 'Relativity (eDiscovery)', 'MS Word legal templates'],
        'certifications':  ['Bar Council Enrollment', 'LLM in specialisation', 'Certificate in Arbitration (CIArb)'],
        'tips': [
            'List landmark cases argued or notable wins.',
            'Quantify scope: "Handled a portfolio of 150+ active litigation matters."',
            'Add publications, law review articles, or conference presentations.',
            'Include pro-bono work and legal aid contributions.',
        ],
    },
    'Arts': {
        'skills_missing':  ['Motion Graphics (After Effects)', 'UX/UI Design (Figma)', 'Brand Identity Design', '3D Modelling (Blender)', 'Typography'],
        'tools':           ['Adobe Creative Suite', 'Figma / Sketch', 'Procreate', 'Blender', 'Canva Pro'],
        'certifications':  ['Adobe Certified Professional', 'Google UX Design Certificate', 'Coursera Graphic Design Specialization'],
        'tips': [
            'Link to an online portfolio (Behance, Dribbble, personal site).',
            'Show client briefs and before/after transformation work.',
            'Include measurable impact: "Redesign increased click-through by 40%."',
            'Add social media growth metrics for brands you designed for.',
        ],
    },
    'Health and Fitness': {
        'skills_missing':  ['Sports Nutrition Certification', 'Rehabilitation & Injury Prevention', 'Group Fitness Instruction', 'Wearable Tech / Data Analysis', 'Mental Wellness Coaching'],
        'tools':           ['MyFitnessPal / Cronometer', 'TrueCoach / Mindbody', 'Garmin / Polar Analytics', 'Zoom (for virtual coaching)', 'InBody (body composition)'],
        'certifications':  ['NASM Certified Personal Trainer (CPT)', 'ACE Health Coach', 'Precision Nutrition Level 1'],
        'tips': [
            'Add client transformation stories (with permission).',
            'Show client retention rate and average program duration.',
            'Highlight specialisations: weight loss, athlete performance, rehab.',
            'Include social proof: reviews, testimonials, follower count.',
        ],
    },
}

# Default suggestion for categories not explicitly covered
DEFAULT_SUGGESTIONS = {
    'skills_missing':  ['Communication Skills', 'Data Analysis', 'Project Management', 'Agile Methodology', 'Leadership'],
    'tools':           ['MS Office / Google Workspace', 'Slack / Teams', 'JIRA', 'Tableau / Power BI', 'Zoom'],
    'certifications':  ['PMP – Project Management Professional', 'Google Career Certificate', 'LinkedIn Learning Path'],
    'tips': [
        'Quantify every achievement with numbers and percentages.',
        'Tailor your resume for each job description using keywords.',
        'Add a professional summary highlighting your unique value.',
        'Keep your LinkedIn profile 100% aligned with your resume.',
    ],
}

ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path):
    """Extract text AND hyperlinks from a PDF using PyPDF2."""
    try:
        import PyPDF2
        text = ""
        links = []

        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(reader.pages):
                # Extract plain text
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

                # Extract annotation-based hyperlinks (clickable links in PDF)
                if '/Annots' in page:
                    try:
                        annots = page['/Annots']
                        for annot in annots:
                            obj = annot.get_object()
                            if obj.get('/Subtype') == '/Link':
                                a = obj.get('/A', {})
                                uri = a.get('/URI')
                                if uri:
                                    link_str = str(uri)
                                    if link_str not in links:
                                        links.append(link_str)
                    except Exception:
                        pass

        # Also extract plain-text URLs embedded in the text (not clickable annotations)
        url_pattern = re.compile(
            r'https?://[^\s\)\]\>\"\']+|'
            r'www\.[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[^\s\)\]\>\"\']*|'
            r'linkedin\.com/[^\s\)\]\>\"\']+|'
            r'github\.com/[^\s\)\]\>\"\']+',
            re.IGNORECASE
        )
        text_links = url_pattern.findall(text)
        for lnk in text_links:
            if lnk not in links:
                links.append(lnk)

        return text.strip(), links

    except Exception as e:
        print(f"[Resume] PDF extraction error: {e}")
        return "", []


# ─────────────────────────────────────────────────────────────────────────────
# Tiered keyword weights per category
# core (3pts) — signature terms almost exclusive to this category
# strong (2pts) — very relevant, may appear in adjacent domains
# supporting (1pt) — general terms that add weight
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_WEIGHTED_KW = {
    'Data Science': {
        'core':       ['machine learning', 'deep learning', 'tensorflow', 'pytorch', 'sklearn', 'scikit', 'neural network', 'nlp', 'natural language processing', 'computer vision', 'data scientist'],
        'strong':     ['python', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter', 'statistics', 'regression', 'classification', 'clustering', 'feature engineering', 'model training', 'kaggle', 'mlflow', 'xgboost'],
        'supporting': ['sql', 'data', 'analysis', 'visualization', 'tableau', 'power bi', 'a/b testing'],
    },
    'Python Developer': {
        'core':       ['django', 'flask', 'fastapi', 'python developer', 'rest api', 'python backend'],
        'strong':     ['python', 'celery', 'redis', 'postgresql', 'sqlalchemy', 'pytest', 'asyncio', 'aiohttp', 'gunicorn', 'uvicorn'],
        'supporting': ['docker', 'aws', 'api', 'microservices', 'linux'],
    },
    'Java Developer': {
        'core':       ['java', 'spring boot', 'spring framework', 'hibernate', 'j2ee', 'jvm', 'java developer'],
        'strong':     ['maven', 'gradle', 'springboot', 'microservices', 'junit', 'jpa', 'servlet', 'restful'],
        'supporting': ['sql', 'docker', 'kafka', 'aws', 'jenkins'],
    },
    'DevOps Engineer': {
        'core':       ['docker', 'kubernetes', 'k8s', 'jenkins', 'ci/cd', 'terraform', 'ansible', 'devops'],
        'strong':     ['aws', 'azure', 'gcp', 'linux', 'helm', 'argocd', 'github actions', 'pipeline', 'prometheus', 'grafana'],
        'supporting': ['python', 'bash', 'monitoring', 'nginx', 'cloud'],
    },
    'Database': {
        'core':       ['dba', 'database administrator', 'oracle dba', 'mysql dba', 'postgresql dba', 'sql server'],
        'strong':     ['sql', 'mysql', 'postgresql', 'oracle', 'mongodb', 'nosql', 'query optimisation', 'indexing', 'stored procedure', 'replication'],
        'supporting': ['etl', 'data warehouse', 'backup', 'recovery', 'performance tuning'],
    },
    'Blockchain': {
        'core':       ['blockchain', 'ethereum', 'solidity', 'smart contract', 'web3', 'defi', 'nft', 'hyperledger'],
        'strong':     ['crypto', 'decentralized', 'truffle', 'hardhat', 'ipfs', 'metamask', 'token'],
        'supporting': ['python', 'javascript', 'consensus', 'ledger'],
    },
    'HR': {
        'core':       ['human resources', 'hr manager', 'recruitment', 'talent acquisition', 'hrm', 'hris'],
        'strong':     ['hr', 'payroll', 'onboarding', 'employee relations', 'performance management', 'talent', 'workforce'],
        'supporting': ['compliance', 'training', 'benefits', 'kpi'],
    },
    'Network Security Engineer': {
        'core':       ['penetration testing', 'ethical hacking', 'siem', 'firewall', 'network security', 'cybersecurity', 'zero trust'],
        'strong':     ['cisco', 'vpn', 'ids', 'ips', 'nmap', 'wireshark', 'splunk', 'threat hunting', 'ceh', 'cissp'],
        'supporting': ['network', 'security', 'compliance', 'iso 27001', 'nist'],
    },
    'Testing': {
        'core':       ['qa engineer', 'quality assurance', 'test engineer', 'manual testing', 'test cases', 'bug reporting'],
        'strong':     ['testing', 'selenium', 'junit', 'test plan', 'regression testing', 'jira', 'testng', 'defect'],
        'supporting': ['agile', 'scrum', 'postman', 'api testing'],
    },
    'Automation Testing': {
        'core':       ['automation testing', 'selenium webdriver', 'appium', 'cypress', 'playwright', 'robot framework', 'test automation'],
        'strong':     ['pytest', 'testng', 'bdd', 'cucumber', 'page object model', 'ci/cd', 'automation framework'],
        'supporting': ['java', 'python', 'jenkins', 'github actions', 'allure'],
    },
    'Civil Engineer': {
        'core':       ['civil engineering', 'structural engineering', 'site engineer', 'construction management'],
        'strong':     ['autocad', 'staad pro', 'etabs', 'revit', 'primavera', 'concrete', 'structural', 'site supervision'],
        'supporting': ['project management', 'survey', 'estimation', 'mep'],
    },
    'Electrical Engineering': {
        'core':       ['electrical engineering', 'plc', 'scada', 'embedded systems', 'power systems', 'vlsi'],
        'strong':     ['matlab', 'circuit design', 'pcb', 'microcontroller', 'arduino', 'raspberry pi', 'motor drives', 'inverter'],
        'supporting': ['autocad', 'labview', 'iot', 'firmware'],
    },
    'Mechanical Engineer': {
        'core':       ['mechanical engineering', 'solidworks', 'catia', 'cad design', 'cae', 'fea', 'cfd'],
        'strong':     ['autocad', 'ansys', 'creo', 'nx cad', 'manufacturing', 'gd&t', 'tolerance'],
        'supporting': ['product design', 'quality', 'lean', 'production'],
    },
    'DotNet Developer': {
        'core':       ['c#', '.net', 'asp.net', 'dotnet', '.net core', 'blazor', 'wpf', 'winforms'],
        'strong':     ['entity framework', 'mvc', 'web api', 'azure', 'visual studio', 'linq', 'nuget'],
        'supporting': ['sql server', 'docker', 'microservices', 'signalr'],
    },
    'ETL Developer': {
        'core':       ['etl', 'informatica', 'ssis', 'talend', 'etl developer', 'data pipeline', 'data integration'],
        'strong':     ['data warehouse', 'dwh', 'azure data factory', 'aws glue', 'airflow', 'dbt'],
        'supporting': ['sql', 'spark', 'python', 'scheduling'],
    },
    'Hadoop': {
        'core':       ['hadoop', 'hive', 'hdfs', 'mapreduce', 'cloudera', 'hortonworks', 'big data'],
        'strong':     ['spark', 'pyspark', 'kafka', 'hbase', 'zookeeper', 'sqoop', 'flume', 'databricks'],
        'supporting': ['python', 'java', 'linux', 'yarn', 'cloud'],
    },
    'Business Analyst': {
        'core':       ['business analyst', 'business analysis', 'requirements gathering', 'brd', 'frd', 'bpmn'],
        'strong':     ['stakeholder management', 'use case', 'user stories', 'gap analysis', 'jira', 'confluence', 'wireframe'],
        'supporting': ['agile', 'scrum', 'sql', 'tableau', 'visio'],
    },
    'SAP Developer': {
        'core':       ['sap', 'abap', 'sap hana', 's/4hana', 'fiori', 'sap btp', 'sap modules'],
        'strong':     ['bapi', 'bdc', 'idoc', 'smartforms', 'sap mm', 'sap sd', 'sap fi', 'odata'],
        'supporting': ['rfc', 'function module', 'workflow', 'sap basis'],
    },
    'PMO': {
        'core':       ['pmo', 'project management office', 'pmp', 'prince2', 'program manager', 'portfolio management'],
        'strong':     ['project manager', 'agile', 'scrum', 'risk management', 'stakeholder', 'ms project', 'primavera'],
        'supporting': ['budget', 'milestone', 'delivery', 'governance', 'reporting'],
    },
    'Operations Manager': {
        'core':       ['operations manager', 'supply chain', 'logistics manager', 'warehouse', 'operations management'],
        'strong':     ['lean', 'six sigma', 'kpi', 'process improvement', 'erp', 'inventory', 'vendor management'],
        'supporting': ['team management', 'sla', 'escalation', 'procurement'],
    },
    'Sales': {
        'core':       ['sales', 'business development', 'crm', 'lead generation', 'account manager', 'b2b', 'b2c'],
        'strong':     ['revenue', 'quota', 'target', 'client acquisition', 'negotiation', 'salesforce', 'hubspot'],
        'supporting': ['cold calling', 'pitching', 'upselling', 'pipeline'],
    },
    'Advocate': {
        'core':       ['advocate', 'barrister', 'solicitor', 'litigation', 'legal counsel', 'law firm', 'llb', 'llm'],
        'strong':     ['legal', 'law', 'court', 'contract', 'arbitration', 'compliance', 'attorney', 'judiciary'],
        'supporting': ['dispute', 'drafting', 'due diligence', 'intellectual property'],
    },
    'Arts': {
        'core':       ['graphic designer', 'ui designer', 'ux designer', 'visual artist', 'illustrator', 'creative director'],
        'strong':     ['photoshop', 'adobe', 'figma', 'sketch', 'indesign', 'after effects', 'portfolio', 'branding'],
        'supporting': ['creative', 'typography', 'colour theory', 'visual'],
    },
    'Health and Fitness': {
        'core':       ['personal trainer', 'fitness coach', 'nutritionist', 'physiotherapist', 'dietitian', 'gym'],
        'strong':     ['fitness', 'nutrition', 'wellness', 'health', 'exercise', 'strength training', 'rehabilitation'],
        'supporting': ['diet', 'body composition', 'bmi', 'sports'],
    },
}


def keyword_classify(text):
    """
    Classify a resume using tiered weighted keyword matching.
    Returns (category_name, match_score, confidence_pct).

    Weights: core=3, strong=2, supporting=1
    match_score = (earned_points / max_possible_points) * 100
    confidence  = how much the winner outscores the runner-up (0-100)
    """
    text_lower = text.lower()
    scores = {}

    for cat, tiers in CATEGORY_WEIGHTED_KW.items():
        earned = 0
        max_pts = 0
        for kw in tiers.get('core', []):
            max_pts += 3
            if kw in text_lower:
                earned += 3
        for kw in tiers.get('strong', []):
            max_pts += 2
            if kw in text_lower:
                earned += 2
        for kw in tiers.get('supporting', []):
            max_pts += 1
            if kw in text_lower:
                earned += 1
        scores[cat] = earned / max(max_pts, 1)

    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = sorted_cats[0]
    second_score        = sorted_cats[1][1] if len(sorted_cats) > 1 else 0

    match_score = round(best_score * 100, 1)

    # Confidence = how much the winner dominates the runner-up (normalised 0-100)
    if best_score == 0:
        confidence = 0.0
    else:
        gap = best_score - second_score
        confidence = round(min(100.0, (gap / best_score) * 100 + 40), 1)

    return best_cat, match_score, confidence


def calculate_match_score(text, category_name):
    """Honest keyword match score — 0% means no keywords, 100% means all matched."""
    text_lower = text.lower()
    tiers = CATEGORY_WEIGHTED_KW.get(category_name, {})
    if not tiers:
        # fallback for unknown categories
        kws = CATEGORY_KEYWORDS.get(category_name, [])
        matches = sum(1 for kw in kws if kw in text_lower)
        return round((matches / max(len(kws), 1)) * 100, 1)

    earned = 0
    max_pts = 0
    for kw in tiers.get('core', []):
        max_pts += 3
        if kw in text_lower:
            earned += 3
    for kw in tiers.get('strong', []):
        max_pts += 2
        if kw in text_lower:
            earned += 2
    for kw in tiers.get('supporting', []):
        max_pts += 1
        if kw in text_lower:
            earned += 1
    return round((earned / max(max_pts, 1)) * 100, 1)


def get_suggestions(category_name, text, match_score):
    """
    Build actionable, personalised suggestions for the candidate.
    Returns a dict with: skills_to_add, tools, certifications, tips, found_keywords, missing_keywords
    """
    suggestions = CATEGORY_SUGGESTIONS.get(category_name, DEFAULT_SUGGESTIONS)
    keywords = CATEGORY_KEYWORDS.get(category_name, [])
    text_lower = text.lower()

    found_keywords   = [kw for kw in keywords if kw in text_lower]
    missing_keywords = [kw for kw in keywords if kw not in text_lower]

    # Determine urgency based on match score
    if match_score >= 75:
        urgency = 'Strong profile! A few refinements will make it exceptional.'
        urgency_class = 'success'
    elif match_score >= 50:
        urgency = 'Good foundation. Adding the recommended skills will significantly boost your profile.'
        urgency_class = 'warning'
    else:
        urgency = 'Needs improvement. Focus on adding core domain keywords and certifications.'
        urgency_class = 'danger'

    return {
        'skills_to_add':   suggestions.get('skills_missing',  []),
        'tools':           suggestions.get('tools',           []),
        'certifications':  suggestions.get('certifications',  []),
        'tips':            suggestions.get('tips',            []),
        'found_keywords':  found_keywords,
        'missing_keywords': missing_keywords,
        'urgency':         urgency,
        'urgency_class':   urgency_class,
    }


@resume_bp.route('/', methods=['GET', 'POST'])
@login_required
def screen():
    from __init__ import db
    from database.models import ResumeResult

    result = None
    recent_results = ResumeResult.query.order_by(
        ResumeResult.created_at.desc()
    ).limit(5).all()

    if request.method == 'POST':
        try:
            candidate_name = request.form.get('candidate_name', 'Candidate').strip() or 'Candidate'

            if 'resume_file' not in request.files:
                flash('No file part in the request.', 'warning')
                return redirect(url_for('resume.screen'))

            file = request.files['resume_file']

            if file.filename == '':
                flash('No file selected. Please upload a PDF resume.', 'warning')
                return redirect(url_for('resume.screen'))

            if not allowed_file(file.filename):
                flash('Only PDF files are allowed.', 'warning')
                return redirect(url_for('resume.screen'))

            # No longer blocked by model availability — keyword classifier works standalone
            # (ML pipeline kept for potential future fix but not used for prediction)

            # Save uploaded file
            from werkzeug.utils import secure_filename
            import uuid
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = current_app.config['UPLOAD_FOLDER']
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)

            # Extract text AND hyperlinks from PDF
            extracted_text, hyperlinks = extract_text_from_pdf(file_path)

            if not extracted_text:
                flash('Could not extract text from PDF. Ensure the PDF contains selectable text.', 'warning')
                os.remove(file_path)
                return redirect(url_for('resume.screen'))

            # ── Classify using weighted keyword engine (version-independent) ──
            category_name, match_score, confidence = keyword_classify(extracted_text)

            # ── Recalculate detailed match score for the winning category ──
            match_score = calculate_match_score(extracted_text, category_name)

            # Generate actionable suggestions
            suggestions = get_suggestions(category_name, extracted_text, match_score)

            # Save to database
            resume_record = ResumeResult(
                candidate_name=candidate_name,
                filename=filename,
                category=category_name,
                match_score=match_score,
                extracted_text_preview=extracted_text[:500]
            )
            db.session.add(resume_record)
            db.session.commit()

            result = {
                'candidate_name': candidate_name,
                'filename':       filename,
                'category':       category_name,
                'match_score':    match_score,
                'text_preview':   extracted_text[:300] + '...' if len(extracted_text) > 300 else extracted_text,
                'word_count':     len(extracted_text.split()),
                'hyperlinks':     hyperlinks,          # NEW: clickable links from PDF
                'suggestions':    suggestions,         # NEW: career improvement panel
            }

            recent_results = ResumeResult.query.order_by(
                ResumeResult.created_at.desc()
            ).limit(5).all()

        except Exception as e:
            flash(f'Resume screening error: {str(e)}', 'danger')

    return render_template('resume.html', result=result, recent=recent_results)
