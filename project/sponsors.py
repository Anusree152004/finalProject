from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from flask_login import login_required, current_user
from models import db, User,Sponsor, Campaign, CampaignPhoto,Influencer,SocialMediaMetric,CampaignRequest

# Create a Blueprint for sponsors
sponsors_bp = Blueprint('sponsors', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

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

#************************************************************************************************************#

# Route for updating profile
@sponsors_bp.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    user = User.query.get(current_user.user_id)
    sponsor = Sponsor.query.filter_by(user_id=current_user.user_id).first()
    if not user or not sponsor:
        flash("User or Sponsor not found.", "danger")
        return redirect(url_for('sponsors.dashboard'))

    if request.method == 'POST':
        try:
            # Capture form data
            user.name = request.form.get('name')
            user.email = request.form.get('email')
            user.bio = request.form.get('bio')
            sponsor.category = request.form.get('category')
            profile_pic = request.files.get('profile_pic')
            
            # Validate form data
            if not user.name or not user.email or not sponsor.category:
                raise ValueError("Name, email, and category are required.")
            
            # Save profile picture
            if profile_pic and allowed_file(profile_pic.filename):
                filename = secure_filename(profile_pic.filename)
                uploads_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pics')
                if not os.path.exists(uploads_dir):
                    os.makedirs(uploads_dir)
                image_filename = os.path.join(uploads_dir, filename)
                profile_pic.save(image_filename)
                user.profile_pic = os.path.join('uploads', 'profile_pics', filename).replace('\\', '/')
            
            db.session.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('sponsors.dashboard'))
        except ValueError as e:
            flash("Invalid input: " + str(e), "danger")
        except Exception as e:
            flash("An unexpected error occurred: " + str(e), "danger")

    return render_template('update_profile.html', user=user, sponsor=sponsor)
#************************************************************************************************************#
# Route for creating a campaign
import logging

logging.basicConfig(level=logging.DEBUG)

@sponsors_bp.route('/create_campaign', methods=['GET', 'POST'])
@login_required
def create_campaign():
    if request.method == 'POST':
        try:
            # Capture form data
            title = request.form.get('title')
            description = request.form.get('description')
            budget = request.form.get('budget')
            followers_range = request.form.get('followers_range')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            campaign_photo = request.files.get('campaign_photo')

            # Debugging: Print form data
            print(f"Form Data: title={title}, description={description}, budget={budget}, followers_range={followers_range}, start_date={start_date}, end_date={end_date}, campaign_photo={campaign_photo}")

            # Validate form data
            if not title or not description or not budget or not followers_range or not start_date or not end_date:
                raise ValueError("All fields are required.")
            
            # Convert dates
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Save campaign photo
            image_filename = None
            if campaign_photo and allowed_file(campaign_photo.filename):
                filename = secure_filename(campaign_photo.filename)
                uploads_dir = current_app.config['UPLOAD_FOLDER']
                if not os.path.exists(uploads_dir):
                    os.makedirs(uploads_dir)
                image_filename = os.path.join(uploads_dir, filename)
                campaign_photo.save(image_filename)
                
            # Get sponsor info (ensure the current user is a sponsor)
            sponsor = Sponsor.query.filter_by(user_id=current_user.user_id).first()
            if not sponsor:
                raise ValueError("No sponsor found for the current user.")

            # Create new campaign with correct sponsor_id
            new_campaign = Campaign(
                title=title,
                description=description,
                budget=budget,
                followers_range=followers_range,
                start_date=start_date,
                end_date=end_date,
                sponsor_id=sponsor.sponsor_id  # Use sponsor.sponsor_id instead of current_user.user_id
            )

            db.session.add(new_campaign)
            db.session.commit()

            # Save Campaign Photo
            if image_filename:
                new_campaign_photo = CampaignPhoto(
                    campaign_id=new_campaign.campaign_id,
                    file_path=os.path.join('uploads', 'campaign_photo', filename).replace('\\', '/')  # Store relative path
                )
                db.session.add(new_campaign_photo)
                db.session.commit()

            flash("Campaign created successfully!", "success")
            return redirect(url_for('sponsors.view_campaigns'))
        except ValueError as e:
            flash("Invalid input: " + str(e), "danger")
            print(f"ValueError: {e}")
        except Exception as e:
            flash("An unexpected error occurred: " + str(e), "danger")
            print(f"Exception: {e}")

    return render_template('createCamp.html')  # Render the form for GET requests

#************************************************************************************************************#
# Route for viewing all campaigns
@sponsors_bp.route('/view_campaigns')
@login_required  # Ensure the user is logged in
def view_campaigns():
    # Get the sponsor info
    sponsor = Sponsor.query.filter_by(user_id=current_user.user_id).first()
    if not sponsor:
        flash("No sponsor found for the current user.", "danger")
        return redirect(url_for('sponsors.create_campaign'))

    # Get all campaigns created by the current sponsor
    campaigns = Campaign.query.filter_by(sponsor_id=sponsor.sponsor_id).all()

    return render_template('viewCamp.html', campaigns=campaigns)

#************************************************************************************************************#
# Route for updating a campaign
@sponsors_bp.route('/update_campaign/<int:campaign_id>', methods=['GET', 'POST'])
@login_required
def update_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.sponsor_id != current_user.sponsor.sponsor_id:
        flash("You are not authorized to update this campaign.", "danger")
        return redirect(url_for('sponsors.view_campaigns'))

    if request.method == 'POST':
        try:
            # Capture form data
            campaign.title = request.form.get('title')
            campaign.description = request.form.get('description')
            campaign.budget = request.form.get('budget')
            campaign.followers_range = request.form.get('followers_range')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            campaign_photo = request.files.get('campaign_photo')
            
            # Validate form data
            if not campaign.title or not campaign.description or not campaign.budget or not campaign.followers_range or not start_date or not end_date:
                raise ValueError("All fields are required.")
            
            # Convert dates
            campaign.start_date = datetime.strptime(start_date, '%Y-%m-%d')
            campaign.end_date = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Save campaign photo
            if campaign_photo and allowed_file(campaign_photo.filename):
                filename = secure_filename(campaign_photo.filename)
                uploads_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'campaign_photo')
                if not os.path.exists(uploads_dir):
                    os.makedirs(uploads_dir)
                image_filename = os.path.join(uploads_dir, filename)
                campaign_photo.save(image_filename)
                
                # Update campaign photo
                campaign_photo_record = CampaignPhoto.query.filter_by(campaign_id=campaign_id).first()
                if campaign_photo_record:
                    campaign_photo_record.file_path = os.path.join('uploads', 'campaign_photo', filename).replace('\\', '/')
                else:
                    new_campaign_photo = CampaignPhoto(
                        campaign_id=campaign_id,
                        file_path=os.path.join('uploads', 'campaign_photo', filename).replace('\\', '/')
                    )
                    db.session.add(new_campaign_photo)
            
            db.session.commit()
            flash("Campaign updated successfully!", "success")
            return redirect(url_for('sponsors.view_campaigns'))
        except ValueError as e:
            flash("Invalid input: " + str(e), "danger")
        except Exception as e:
            flash("An unexpected error occurred: " + str(e), "danger")

    return render_template('updateCamp.html', campaign=campaign)

#************************************************************************************************************#
# Route for deleting a campaign
@sponsors_bp.route('/delete_campaign/<int:campaign_id>', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.sponsor_id != current_user.sponsor.sponsor_id:
        flash("You are not authorized to delete this campaign.", "danger")
        return redirect(url_for('sponsors.view_campaigns'))

    try:
        # Delete associated campaign photos
        CampaignPhoto.query.filter_by(campaign_id=campaign_id).delete()
        
        # Delete the campaign
        db.session.delete(campaign)
        db.session.commit()
        flash("Campaign deleted successfully!", "success")
    except Exception as e:
        flash("An unexpected error occurred: " + str(e), "danger")
        print(f"Exception: {e}")

    return redirect(url_for('sponsors.view_campaigns'))
#************************************************************************************************************#

# Route for displaying influencers based on sponsor's category
@sponsors_bp.route('/influe_search', methods=['GET'])
@login_required
def influe_search():
    sponsor = Sponsor.query.filter_by(user_id=current_user.user_id).first()
    if not sponsor:
        flash("Sponsor not found.", "danger")
        return redirect(url_for('sponsors.dashboard'))

    # Fetch influencers matching the sponsor's category and join with User and SocialMediaMetrics tables
    influencers = db.session.query(Influencer, User, SocialMediaMetric).join(User, Influencer.user_id == User.user_id).join(SocialMediaMetric, User.user_id == SocialMediaMetric.user_id).filter(Influencer.category == sponsor.category).order_by(SocialMediaMetric.reach.desc()).all()

    return render_template('influeSearch.html', sponsor=sponsor, influencers=influencers)
#************************************************************************************************************#
# #route for view campaign requests
# @sponsors_bp.route('/view_campaign_requests/<int:campaign_id>')
# def view_campaign_requests(campaign_id):
#     campaign = Campaign.query.get_or_404(campaign_id)
    
#     # Get all requests for this campaign
#     requests = CampaignRequest.query.filter_by(campaign_id=campaign_id, status='pending').all()

#     return render_template('view_campaign_requests.html', campaign=campaign, requests=requests)
# #************************************************************************************************************#
# # Route for accepting or rejecting a campaign request
# @sponsors_bp.route('/update_request_status/<int:request_id>', methods=['POST'])
# def update_request_status(request_id):
#     request = CampaignRequest.query.get_or_404(request_id)
    
#     # Check if the current user is the sponsor of the campaign
#     if request.campaign.sponsor_id != current_user.id:
#         flash('You are not authorized to manage this request.', 'danger')
#         return redirect(url_for('sponsors.dashboard'))

#     # Update the request status
#     action = request.form.get('action')
#     if action == 'accept':
#         request.status = 'accepted'
#     elif action == 'reject':
#         request.status = 'rejected'

#     db.session.commit()
    
#     flash(f'Request has been {request.status}.', 'success')
#     return redirect(url_for('sponsors.view_campaign_requests', campaign_id=request.campaign_id))
#************************************************************************************************************#