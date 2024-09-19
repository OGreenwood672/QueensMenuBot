import sys
import os

# Set the path to the QueensMenuBot folder
sys.path.insert(0, os.path.dirname(__file__))

# Add the virtual environment's site-packages to sys.path
venv_path = os.path.join(os.path.dirname(__file__), 'venv', 'lib', 'python3.x', 'site-packages')
sys.path.insert(0, venv_path)

# Add the 'api' folder to the system path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

# Import the Flask app (assuming the app is defined as 'app' in api/app.py)
from app import app as application