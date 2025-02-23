from flask import Flask,render_template,request,redirect,url_for,flash,session,Blueprint
from models import db
from models import User, Sponsor, Influencer, SocialMediaMetric
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sponsors import sponsors_bp
from influencers import influencers_bp
from influencers import get_instagram_profile
from werkzeug.security import generate_password_hash, check_password_hash
from utils import generate_breadcrumbs
import os


app = Flask(__name__,static_url_path='/static')




app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Set the UPLOAD_FOLDER in the main app config
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.secret_key = '_protected_key'


# Initialize the database

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.drop_all()  # Only if you want to start fresh
    db.create_all()
    
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'  # Set default login view



# Register blueprints
app.register_blueprint(influencers_bp, url_prefix='/influencers')  # Register the influencers blueprint
app.register_blueprint(sponsors_bp, url_prefix='/sponsors')  # Register the sponsors blueprint

# Create user loader for flask-login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Register the breadcrumb helper function
@app.context_processor
def utility_processor():
    return dict(generate_breadcrumbs=generate_breadcrumbs)

#**************************************************************************************************************#

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form.get('role')
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        bio = request.form.get('bio', '')

        print(f"Received role: {role}")  # Debugging: Check the role received

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('signup'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email already exists.", "danger")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)

        # Create new user
        new_user = User(
            name=name,
            username=username,
            email=email,
            password=hashed_password,
            bio=bio,
            role=role
        )
        db.session.add(new_user)
        db.session.commit()  # Commit to get the user_id

        # Create sponsor or influencer based on role
        if role == 'sponsor':
            company_name = request.form.get('company_name')
            location = request.form.get('location')
            category = request.form.get('category')
            sponsor = Sponsor(
                user_id=new_user.user_id,
                company_name=company_name,
                location=location,
                category=category
            )
            db.session.add(sponsor)
        elif role == 'influencer':
            category = request.form.get('category')
            social_media_name = request.form.get('social_media_name')
            influencer = Influencer(
                user_id=new_user.user_id,
                category=category,
                social_media_name=social_media_name
            )
            db.session.add(influencer)
            
            # Fetch Instagram metrics using new API
            instagram_data = get_instagram_profile(username)
            if instagram_data:
                social_metrics = SocialMediaMetric(
                    user_id=new_user.user_id,
                    followers=instagram_data['followers'],
                    following=instagram_data['following'],
                    posts_count=instagram_data['posts_count'],
                    avg_likes=instagram_data['avg_likes'],
                    avg_comments=instagram_data['avg_comments'],
                    avg_reel_views=instagram_data['avg_reel_views'],
                    engagement_rate=instagram_data['engagement_rate'],
                    is_verified=instagram_data['is_verified'],
                    is_business_account=instagram_data['is_business'],
                    bio=instagram_data['biography'],
                    platform='instagram'
                )
                db.session.add(social_metrics)
            else:
                flash("Unable to fetch Instagram data. Please update your profile later.", "warning")

            

        db.session.commit()  # Commit the sponsor or influencer

        flash("Signup successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')

#**************************************************************************************************************#

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            
            login_user(user)

                # Debug: Check session and current user
            print(f"Session: {session}")
            print(f"Current User: {current_user}")

            flash("Login successful!", "success")

            if user.role == 'sponsor':
                return redirect(url_for('sponsors.dashboard'))  # This links to the sponsors blueprint
            elif user.role == 'influencer':
                return redirect(url_for('influencers.dashboard'))  # This links to the influencers blueprint
            else:
                flash('Invalid role', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Login failed. Check username and/or password.', 'danger')

    return render_template('login.html')
#**************************************************************************************************************#
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clears the session to log the user out
    flash("You have successfully logged out.", "success")
    return redirect(url_for('login'))  # Redirect to the login page
#**************************************************************************************************************#

@app.route('/')
def home():
    return render_template('home.html')



if __name__ == '__main__':
    app.run(debug=True)