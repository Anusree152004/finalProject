from flask import Blueprint, render_template,redirect,url_for,flash
from flask_login import login_required, current_user
from models import Sponsor
# Create a Blueprint for sponsors
sponsors_bp = Blueprint('sponsors', __name__)

# Sponsor Dashboard Route
@sponsors_bp.route('/dashboard')
@login_required
def dashboard():
    # Query the Sponsor object associated with the current user
    sponsor = Sponsor.query.filter_by(user_id=current_user.user_id).first()

    if sponsor:
        return render_template('sponsor_dash.html', sponsor=sponsor)
    else:
        # If no sponsor exists, handle the case (maybe redirect or show an error)
        flash('No sponsor found.', 'danger')
        return redirect(url_for('home'))