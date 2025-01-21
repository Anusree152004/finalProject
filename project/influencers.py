from flask import Blueprint, render_template,redirect,url_for,flash,jsonify,request,current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db,User,Influencer,SocialMediaMetric,Campaign,CampaignRequest,Sponsor,Post,CampaignPhoto
import instaloader
from statistics import mean
from datetime import datetime
import os
import re
from sqlalchemy import func

# Create a Blueprint for influencers
influencers_bp = Blueprint('influencers', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@influencers_bp.route('/dashboard')
@login_required
def dashboard():
    # Get the user based on the current logged-in user
    user = User.query.filter_by(user_id=current_user.user_id).first()
    influencer = Influencer.query.filter_by(user_id=current_user.user_id).first()
    if not user or not influencer:
        flash("User or Influencer not found.", "danger")
        return redirect(url_for('influencers.update_influencer_profile'))
    if user:
        # Get the social media metrics for the current user's ID (user_id)
        metrics = SocialMediaMetric.query.filter_by(user_id=user.user_id).first()
        
        if metrics:
            # Debugging: Check if metrics are fetched
            print(f"Followers: {metrics.followers}, Engagement Rate: {metrics.engagement_rate}")
            followers_data = [metrics.followers]
            engagement_rate_data = [metrics.engagement_rate]
            likes_data = [metrics.likes]
            shares_data = [metrics.shares]
            comments_data = [metrics.comments]
            reach_data = [metrics.reach]

            # Pass data to the template
            return render_template(
                'influencer_dash.html', 
                user=user, 
                metrics=metrics,
                followers_data=followers_data,
                engagement_rate_data=engagement_rate_data,
                likes_data=likes_data,
                shares_data=shares_data,
                comments_data=comments_data,
                reach_data=reach_data
            )
        else:
            flash('No social media metrics found for this user.', 'danger')
            return redirect(url_for('home'))
    else:
        flash('No influencer found for this user.', 'danger')
        return redirect(url_for('home'))



# Function to fetch Instagram data
def fetch_instagram_data(username):
    loader = instaloader.Instaloader()
    try:
        profile = instaloader.Profile.from_username(loader.context, username)

        # Lists to store metrics
        reel_views = []
        post_likes = []
        post_comments = []

        # Iterate through posts to collect metrics
        for post in profile.get_posts():
            if post.is_video:
                reel_views.append(post.video_view_count)
            post_likes.append(post.likes)
            post_comments.append(post.comments)

        # Calculate averages
        avg_reel_views = mean(reel_views) if reel_views else 0
        avg_likes = mean(post_likes) if post_likes else 0
        avg_comments = mean(post_comments) if post_comments else 0

        # Estimate reach
        reach_factor = 1.5  # Example multiplier; adjust as needed
        estimated_reach = avg_likes * reach_factor

        # Calculate engagement rate
        total_followers = profile.followers if profile.followers else 1  # Avoid division by zero
        engagement_rate = ((avg_likes + avg_comments) / total_followers) * 100

        return {
            'followers': profile.followers,
            'likes': avg_likes,
            'shares': avg_reel_views,  # Using reel views as a proxy for shares
            'comments': avg_comments,
            'reach': estimated_reach,
            'engagement_rate': engagement_rate,
        }
    except Exception as e:
        print(f"Error fetching data for {username}: {e}")
        return None

# Endpoint to fetch and save data for influencers
@influencers_bp.route('/fetch_influencer_metrics', methods=['POST'])
def fetch_influencer_metrics():
    try:
        # Query usernames of all influencers from the Users table
        influencer_users = User.query.filter_by(role='influencer').all()

        for user in influencer_users:
            username = user.username  # Fetch username from Users table

            # Fetch Instagram data for this username
            data = fetch_instagram_data(username)

            if data:
                # Check if data already exists for this influencer
                existing_metric = SocialMediaMetric.query.filter_by(user_id=user.user_id).first()

                if existing_metric:
                    # Update existing record
                    existing_metric.followers = data['followers']
                    existing_metric.likes = data['likes']
                    existing_metric.shares = data['shares']
                    existing_metric.comments = data['comments']
                    existing_metric.reach = data['reach']
                    existing_metric.engagement_rate = data['engagement_rate']
                    existing_metric.updated_at = datetime.utcnow()
                else:
                    # Add a new record
                    new_metric = SocialMediaMetric(
                        user_id=user.user_id,  # Using the user ID from Users table as influencer ID
                        sponsor_id=None,  # Populate if necessary
                        followers=data['followers'],
                        likes=data['likes'],
                        shares=data['shares'],
                        comments=data['comments'],
                        reach=data['reach'],
                        engagement_rate=data['engagement_rate'],
                    )
                    db.session.add(new_metric)

        # Commit all changes
        db.session.commit()
        return jsonify({'message': 'Social media metrics fetched and updated successfully!'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

#**************************************************************************************************************#
# Route for updating influencer profile
@influencers_bp.route('/update_influencer_profile', methods=['GET', 'POST'])
@login_required
def update_influencer_profile():
    user = User.query.get(current_user.user_id)
    influencer = Influencer.query.filter_by(user_id=current_user.user_id).first()
    if not user or not influencer:
        flash("User or Influencer not found.", "danger")
        return redirect(url_for('influencers.dashboard'))

    if request.method == 'POST':
        try:
            # Capture form data
            user.name = request.form.get('name')
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.bio = request.form.get('bio')
            influencer.category = request.form.get('category')
            profile_pic = request.files.get('profile_pic')
            
            # Validate form data
            if not user.name or not user.username or not user.email or not influencer.category:
                raise ValueError("Name, username, email, and category are required.")
            
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
            return redirect(url_for('influencers.dashboard'))
        except ValueError as e:
            flash("Invalid input: " + str(e), "danger")
        except Exception as e:
            flash("An unexpected error occurred: " + str(e), "danger")

    return render_template('update_influe_profile.html', user=user, influencer=influencer)

#**************************************************************************************************************#
# Helper function to convert followers range to numerical values
def parse_followers_range(followers_range):
    match = re.match(r'(\d+)([kK]?)\s*-\s*(\d+)([kK]?)', followers_range)
    if match:
        min_followers = int(match.group(1)) * (1000 if match.group(2).lower() == 'k' else 1)
        max_followers = int(match.group(3)) * (1000 if match.group(4).lower() == 'k' else 1)
        return min_followers, max_followers

    match = re.match(r'(\d+)([kK]?)', followers_range)
    if match:
        min_followers = int(match.group(1)) * (1000 if match.group(2).lower() == 'k' else 1)
        return min_followers, None

    return None, None

# Helper function to determine if the followers count is within the range
def is_followers_count_in_range(followers_count, followers_range):
    min_followers, max_followers = parse_followers_range(followers_range)
    if min_followers is not None:
        if max_followers is not None:
            return min_followers <= followers_count <= max_followers
        return followers_count >= min_followers
    return False

# Route for displaying the campaign search form and initial recommended campaigns
@influencers_bp.route('/search_campaigns', methods=['GET'])
@login_required
def search_campaigns():
    influencer = Influencer.query.filter_by(user_id=current_user.user_id).first()
    if not influencer:
        flash("Influencer not found.", "danger")
        return redirect(url_for('influencers.dashboard'))

    # Get the category from the query string (either 'all' or a specific category)
    category = request.args.get('category', 'all')  # Default to 'all' if no category is selected

    # Fetch the social media metric for the influencer
    social_media_metric = SocialMediaMetric.query.filter_by(user_id=current_user.user_id).first()
    if not social_media_metric:
        flash("Social media metrics not found.", "danger")
        return redirect(url_for('influencers.dashboard'))

    followers_count = social_media_metric.followers
    print(f"Followers count: {followers_count}")

    all_campaigns = Campaign.query.all()


    # Query campaigns based on the selected category and sponsor's category
    if category != 'all':
        campaigns = db.session.query(Campaign).join(Sponsor).filter(
            func.lower(Sponsor.category) == category.lower(),  # Match sponsor's category with selected category
            Campaign.sponsor_id == Sponsor.sponsor_id  # Ensure sponsor_id links correctly
        ).all()
    else:
        campaigns = db.session.query(Campaign).join(Sponsor).all()

    # Recommended campaigns: Filter based on influencer's category and followers count
    recommended_campaigns = [
        campaign for campaign in all_campaigns
        if campaign.followers_range and is_followers_count_in_range(followers_count, campaign.followers_range)
    ]
    print(f"Recommended campaigns: {len(recommended_campaigns)}")

    # Fetch the first image for each campaign
    for campaign in all_campaigns:
        campaign.image_url = None
        if campaign.campaign_photo:
            first_photo = campaign.campaign_photo[0]
            if first_photo and first_photo.file_path:  # Ensure file_path is valid
                filename = first_photo.file_path.split('uploads/campaign_photo/')[-1]
                campaign.image_url = url_for('static', filename=f'uploads/campaign_photo/{filename}')
                print(f"Image URL for campaign {campaign.campaign_id}: {campaign.image_url}")

    # Return the template with recommended and all campaigns
    return render_template('campSearch.html', 
                           recommended_campaigns=recommended_campaigns,  # Recommended campaigns based on followers range
                           all_campaigns=campaigns,  # All campaigns, filtered by category if applicable
                           category=category)  # Pass selected category to template
   
#**************************************************************************************************************#
#view profiles of sponsors
@influencers_bp.route('/sponsor_profile/<int:sponsor_id>')
def sponsor_profile(sponsor_id):
    sponsor = Sponsor.query.get(sponsor_id)
    if not sponsor:
        return "Sponsor not found", 404

    # Fetch campaigns related to the sponsor
    campaigns = Campaign.query.filter_by(sponsor_id=sponsor_id).all()

    # Fetch sponsor's profile picture or use a default
    profile_pic = sponsor.user.profile_pic.replace('uploads/profile_pics/', '') if sponsor.user.profile_pic else 'default_profile.jpg'

    # Create a dictionary of campaign_id to campaign photo path or a default
    campaign_photos = {
    campaign.campaign_id: cp.file_path.replace('uploads/campaign_photo/', '') if cp else 'default_campaign.jpg'
    for campaign in campaigns
    for cp in [CampaignPhoto.query.filter_by(campaign_id=campaign.campaign_id).first()]
}

    return render_template(
        'sponsor_profile.html',
        sponsor=sponsor,
        campaigns=campaigns,
        profile_pic=profile_pic,
        campaign_photos=campaign_photos
    )

#**************************************************************************************************************#
# #request to join a campaign
# @influencers_bp.route('/request_campaign/<int:campaign_id>', methods=['POST'])
# def request_campaign(campaign_id):
#     campaign = Campaign.query.get_or_404(campaign_id)
    
#     # Check if the influencer has already requested this campaign
#     existing_request = CampaignRequest.query.filter_by(influencer_id=current_user.id, campaign_id=campaign_id).first()
#     if existing_request:
#         flash('You have already requested this campaign.', 'danger')
#         return redirect(url_for('influencers.dashboard'))

#     # Create a new request
#     request = CampaignRequest(influencer_id=current_user.id, campaign_id=campaign_id)
#     db.session.add(request)
#     db.session.commit()
    
#     flash('Request sent successfully!', 'success')
#     return redirect(url_for('influencers.dashboard'))
