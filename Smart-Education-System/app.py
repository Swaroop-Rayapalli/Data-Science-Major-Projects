import sys
import os

# Ensure the project root is on sys.path so all modules resolve correctly on Vercel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from __init__ import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
