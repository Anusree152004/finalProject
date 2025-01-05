from flask import Blueprint, render_template,redirect,url_for,flash
from flask_login import login_required, current_user
from models import Influencer
# Create a Blueprint for influencers
influencers_bp = Blueprint('influencers', __name__)

# Influencer Dashboard Route
@influencers_bp.route('/dashboard')
@login_required
def dashboard():
    influencer = Influencer.query.filter_by(user_id=current_user.user_id).first()
    if influencer:
        return render_template('influencer_dash.html', influencer=influencer)
    else:
        flash('No influencer found for this user.', 'danger')
        return redirect(url_for('home'))