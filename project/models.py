from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Enum
from enum import Enum as PyEnum
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

# Enums
class StatusEnum(PyEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

# # Association Table for Many-to-Many Relationship
# campaign_influencer = db.Table(
#     'campaign_influencer',
#     db.Column('campaign_id', db.Integer, db.ForeignKey('campaign.campaign_id')),
#     db.Column('influencer_id', db.Integer, db.ForeignKey('influencer.influencer_id'))
# )

# User Table
class User(db.Model,UserMixin):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(120), nullable=False)

    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(200))
    role = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def get_id(self):
        # Return the user_id as a string (required for Flask-Login)
        return str(self.user_id)
    
    # Relationships
    sponsor = db.relationship('Sponsor', backref='user', uselist=False)
    influencer = db.relationship('Influencer', backref='user', uselist=False)
    social_media_metrics = db.relationship('SocialMediaMetric', backref='user', lazy=True)
    post = db.relationship('Post', backref='user', lazy=True)
 #   notification = db.relationship('Notification', backref='user', lazy=True)

# Sponsor Table
class Sponsor(db.Model):
    __tablename__ = 'sponsor'
    sponsor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    company_name = db.Column(db.String(200), index=True)
    location = db.Column(db.String(255), index=True)
    category = db.Column(db.String(100), index=True)
    # Relationships
    campaigns = db.relationship('Campaign', backref='sponsor', lazy=True)
    campaign_requests = db.relationship('CampaignRequest', backref='sponsor', lazy=True)
    influencer_requests = db.relationship('InfluencerRequest', backref='sponsor_requests', lazy=True)

# Influencer Table
class Influencer(db.Model):
    __tablename__ = 'influencer'
    influencer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    social_media_name = db.Column(db.String(100), nullable=False, index=True)
    
    # Relationships
    # campaigns = db.relationship('Campaign', secondary=campaign_influencer, backref='influencers', lazy=True)
    campaign_requests = db.relationship('CampaignRequest', backref='influencer', lazy=True)
    influencer_requests = db.relationship('InfluencerRequest', backref='influencer_requests', lazy=True)
   # social_media_metrics = db.relationship('SocialMediaMetric', backref='influencer', lazy=True)
    #metrics_history = db.relationship('MetricsHistory', backref='influencer', lazy=True)

# Campaign Table
class Campaign(db.Model):
    __tablename__ = 'campaign'
    campaign_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.sponsor_id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    budget = db.Column(db.Float, nullable=False, index=True)
    followers_range = db.Column(db.String(100))
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    # Relationships
   # sponsor = db.relationship('Sponsor', backref='campaign', lazy=True)
   # influencers = db.relationship('Influencer', secondary=campaign_influencer, backref='campaigns', lazy=True)
    campaign_photo = db.relationship('CampaignPhoto', backref='campaign', lazy=True)
    campaign_request = db.relationship('CampaignRequest', backref='campaign', lazy=True)

# Campaign Photos Table
class CampaignPhoto(db.Model):
    __tablename__ = 'campaign_photo'
    photo_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.campaign_id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    #campaign = db.relationship('Campaign', backref='campaign_photo', lazy=True)

 # Campaign Requests Table
class CampaignRequest(db.Model):
    __tablename__ = 'campaign_request'
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.campaign_id'), nullable=False, index=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.sponsor_id'), nullable=False, index=True)
    influencer_id = db.Column(db.Integer, db.ForeignKey('influencer.influencer_id'), nullable=False, index=True)
    status = db.Column(Enum(StatusEnum), default=StatusEnum.PENDING, nullable=False, index=True)
    request_description = db.Column(db.Text)
    # Relationships to Sponsor and Influencer
    ##campaign = db.relationship('Campaign', backref='campaign_request', lazy=True)
    #sponsor = db.relationship('Sponsor', backref='campaign_request')
    #influencer = db.relationship('Influencer', backref='campaign_request')

 # Influencer Requests Table
class InfluencerRequest(db.Model):
    __tablename__ = 'influencer_request'
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    influencer_id = db.Column(db.Integer, db.ForeignKey('influencer.influencer_id'), nullable=False, index=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.sponsor_id'), nullable=False, index=True)
    influencer_id = db.Column(db.Integer, db.ForeignKey('influencer.influencer_id'), nullable=False, index=True)
    status = db.Column(Enum(StatusEnum), default=StatusEnum.PENDING, nullable=False, index=True)
    request_description = db.Column(db.Text)
    # Relationships to Sponsor and Influencer
 #   sponsor = db.relationship('Sponsor', backref='influencer_requests')
 #   influencer = db.relationship('Influencer', backref='influencer_requests')

# Social Media Metrics Table
class SocialMediaMetric(db.Model):
    __tablename__ = 'social_media_metrics'
    metric_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.sponsor_id'), index=True,nullable=True)
    followers = db.Column(db.Integer, nullable=False)
    following = db.Column(db.Integer)
    posts_count = db.Column(db.Integer)
    avg_likes = db.Column(db.Float)
    avg_comments = db.Column(db.Float)
    avg_reel_views = db.Column(db.Float)
    engagement_rate = db.Column(db.Float, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_business_account = db.Column(db.Boolean, default=False)
    bio = db.Column(db.Text)
    platform = db.Column(db.String(50), default='instagram')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    ai_analysis = db.Column(db.Text)  # New field for storing AI analysis
    ai_rating = db.Column(db.Integer)  # New field for storing AI rating

    #user = db.relationship('User', backref='social_media_metrics', lazy=True)


  #  influencer = db.relationship('Influencer', backref='metrics_history', lazy=True)

# # Users Posts Table
class Post(db.Model):
    __tablename__ = 'post'
    post_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    content_text = db.Column(db.Text)
    title = db.Column(db.String(255))
    url = db.Column(db.String(255))
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
   # user = db.relationship('User', backref='post')
    post_metrics = db.relationship('PostMetric', backref='post', lazy=True)

# Post Metrics Table
class PostMetric(db.Model):
    __tablename__ = 'post_metric'
    metric_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.post_id'), nullable=False, index=True)
    likes = db.Column(db.Integer, nullable=False)
    shares = db.Column(db.Integer)
    comments = db.Column(db.Integer)
    engagement_rate = db.Column(db.Float)
    reach = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
  #  post = db.relationship('Post', backref='post_metrics', lazy=True)

# # Notification Table
# class Notification(db.Model):
#     __tablename__ = 'notification'
#     notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
#     message = db.Column(db.String(255), nullable=False)
#     status = db.Column(Enum(StatusEnum), default=StatusEnum.PENDING, nullable=False, index=True)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
