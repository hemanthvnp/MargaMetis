from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)
    
    def __init__(self, username, password, role='user'):
        self.username = username
        self.password_hash = generate_password_hash(password)
        self.role = role

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Search history model
class SearchHistory(db.Model):
    __tablename__ = 'search_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    origin = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    route_type = db.Column(db.String(50), nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    distance_m = db.Column(db.Float, nullable=False)
    estimated_time_min = db.Column(db.Float, nullable=True)
    result_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    user = db.relationship('User', backref=db.backref('searches', lazy=True))

# Utility functions

def add_user(username, password, role='user'):
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return False
    new_user = User(username, password, role)
    db.session.add(new_user)
    db.session.commit()
    return True

def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None

def get_user_role(username):
    user = User.query.filter_by(username=username).first()
    return user.role if user else None
