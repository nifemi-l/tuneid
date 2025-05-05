from flask import Flask
from dotenv import load_dotenv

# Load the environment variables from .env
load_dotenv()

# Create the Flask app
app = Flask(__name__, 
            static_folder="static", template_folder="templates"
)

# Register routes
# - Python loads and executes the body of routes.py once
from app import routes