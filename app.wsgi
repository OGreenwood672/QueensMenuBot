import sys
import os

# Add your project to the system path
sys.path.insert(0, os.path.dirname(__file__))

# Activate the virtual environment
activate_this = os.path.expanduser("~/public_html/venv/myprojectenv/bin/activate")
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

from flask_app import app as application
