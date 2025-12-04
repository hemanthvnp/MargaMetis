#!/usr/bin/env python
"""
Run the Flask development server.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add the parent directory (project root) to the path so we can import route_optimizer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

if __name__ == '__main__':
    app = create_app()
    print("Database configured successfully!")
    print(f"Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    app.run(debug=True, host='0.0.0.0', port=5000)
