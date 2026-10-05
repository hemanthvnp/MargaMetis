from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), default='user', nullable=False)

    def __init__(self, username, password, role='user'):
        self.username      = username
        self.password_hash = generate_password_hash(password)
        self.role          = role

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class SearchHistory(db.Model):
    __tablename__ = 'search_history'

    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    origin             = db.Column(db.String(255), nullable=False)
    destination        = db.Column(db.String(255), nullable=False)
    route_type         = db.Column(db.String(50), nullable=False)
    vehicle_type       = db.Column(db.String(50), nullable=False)
    distance_m         = db.Column(db.Float, nullable=False)
    estimated_time_min = db.Column(db.Float, nullable=True)
    result_json        = db.Column(db.JSON, nullable=True)
    origin_geom        = db.Column(
        Geometry(geometry_type='POINT', srid=4326, spatial_index=False).with_variant(
            db.Text(), 'sqlite'
        ),
        nullable=True,
    )
    dest_geom          = db.Column(
        Geometry(geometry_type='POINT', srid=4326, spatial_index=False).with_variant(
            db.Text(), 'sqlite'
        ),
        nullable=True,
    )
    created_at         = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    user = db.relationship('User', backref=db.backref('searches', lazy=True))


class OSMNode(db.Model):
    __tablename__ = 'osm_nodes'

    id = db.Column(BigInteger, primary_key=True)
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False)

    __table_args__ = (
        Index('idx_osm_nodes_geom', 'geom', postgresql_using='gist'),
    )


class OSMEdge(db.Model):
    __tablename__ = 'osm_edges'

    id = db.Column(BigInteger, primary_key=True, autoincrement=True)
    u = db.Column(BigInteger, nullable=False)
    v = db.Column(BigInteger, nullable=False)
    key = db.Column(Integer, nullable=False)
    length_m = db.Column(Float, nullable=False)
    highway = db.Column(String(80), nullable=False)
    geom = db.Column(Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=False), nullable=False)
    attrs = db.Column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint('u', 'v', 'key', name='uq_osm_edges_u_v_key'),
        Index('idx_osm_edges_geom', 'geom', postgresql_using='gist'),
        Index('idx_osm_edges_u', 'u'),
        Index('idx_osm_edges_v', 'v'),
    )


def add_user(username, password, role='user'):
    if User.query.filter_by(username=username).first():
        return False
    db.session.add(User(username, password, role))
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
