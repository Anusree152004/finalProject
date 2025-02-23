from flask import Blueprint, render_template,redirect,url_for,flash,jsonify,request,current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db,User,Influencer,SocialMediaMetric,Campaign,CampaignRequest,Sponsor,Post,CampaignPhoto
from datetime import datetime, timedelta
import os
import re
from sqlalchemy import func
import requests
import time
import random

# Create a Blueprint for influencers
influencers_bp = Blueprint('influencers', __name__)

# Try to import Gemini AI, fallback gracefully if not available
try:
    import google.generativeai as genai
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'AIzaSyBwRfTwzPbHbK06RRyac0V-ngV_6R8cil0')
    genai.configure(api_key=GOOGLE_API_KEY)
    GEMINI_AVAILABLE = True
except ImportError:
    print("Warning: google.generativeai not available. AI analysis will be disabled.")
    GEMINI_AVAILABLE = False

class RateLimiter:
    def __init__(self, max_requests=150, per_hours=1):
        self.max_requests = max_requests
        self.per_hours = per_hours
        self.requests = []
    
    def wait_if_needed(self):
        now = datetime.now()
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(hours=self.per_hours)]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + timedelta(hours=self.per_hours) - now).total_seconds()
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.requests.pop(0)
        
        self.requests.append(now)

rate_limiter = RateLimiter()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def analyze_profile_with_gemini(metrics):
    """
    Analyze influencer profile using Gemini API and extract rating
    """
    if not GEMINI_AVAILABLE:
        return "AI analysis currently unavailable"
        
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Rate this Instagram profile as an influencer on a scale of 1-10 and explain why in 2-3 short sentences. 
        Format your response exactly like this example:
        Rating: 7
        Analysis: This is a strong micro-influencer account with excellent engagement...

        Profile Data:
        - Followers: {metrics.followers:,}
        - Avg Likes: {metrics.avg_likes:,}
        - Avg Comments: {metrics.avg_comments:,}
        - Avg Reel Views: {metrics.avg_reel_views:,}
        - Engagement Rate: {metrics.engagement_rate}%
        - Verified: {metrics.is_verified}
        - Business Account: {metrics.is_business_account}
        """
        
        # Generate response
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Parse rating and analysis
        try:
            rating_line = response_text.split('\n')[0]
            rating = int(rating_line.split(':')[1].strip())
            analysis = response_text.split('\n')[1].split(':')[1].strip()
            
            # Update the metrics object with AI analysis
            metrics.ai_analysis = analysis
            metrics.ai_rating = rating
            db.session.commit()
            
            return response_text
        except Exception as e:
            print(f"Error parsing AI response: {str(e)}")
            return response_text
            
    except Exception as e:
        print(f"Error analyzing profile: {str(e)}")
        return "Unable to analyze profile at this time."

@influencers_bp.route('/dashboard')
@login_required
def dashboard():
    user = User.query.filter_by(user_id=current_user.user_id).first()
    influencer = Influencer.query.filter_by(user_id=current_user.user_id).first()
    
    if not user or not influencer:
        flash("User or Influencer not found.", "danger")
        return redirect(url_for('influencers.update_influencer_profile'))

    metrics = SocialMediaMetric.query.filter_by(user_id=user.user_id).first()
    
    if metrics:
        # Only get AI analysis if Gemini is available
        profile_analysis = analyze_profile_with_gemini(metrics) if GEMINI_AVAILABLE else None
        
        metrics_data = {
            'followers': metrics.followers,
            'following': metrics.following,
            'posts': metrics.posts_count,
            'avg_likes': metrics.avg_likes,
            'avg_comments': metrics.avg_comments,
            'avg_reel_views': metrics.avg_reel_views,
            'engagement_rate': metrics.engagement_rate
        }
        
        return render_template(
            'influencer_dash.html', 
            user=user, 
            metrics=metrics,
            metrics_data=metrics_data,
            profile_analysis=profile_analysis,
            ai_enabled=GEMINI_AVAILABLE
        )
    else:
        flash('No social media metrics found for this user.', 'danger')
        return redirect(url_for('home'))

def get_instagram_profile(username, max_retries=5):
    """
    Fetch Instagram profile data with rate limiting and retries
    """
    def make_request():
        time.sleep(random.uniform(3, 7))
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-IG-App-ID': '936619743392459',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        rate_limiter.wait_if_needed()
        return requests.get(url, headers=headers)

    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            response = make_request()
            
            if response.status_code == 200:
                data = response.json()
                user_data = data['data']['user']
                timeline_media = user_data['edge_owner_to_timeline_media']
                
                recent_posts = timeline_media.get('edges', [])[:12]
                total_likes = 0
                total_comments = 0
                total_views = 0
                reel_count = 0
                
                for post in recent_posts:
                    node = post.get('node', {})
                    total_likes += node.get('edge_liked_by', {}).get('count', 0)
                    total_comments += node.get('edge_media_to_comment', {}).get('count', 0)
                    if node.get('is_video', False):
                        reel_count += 1
                        total_views += node.get('video_view_count', 0)
                
                avg_likes = total_likes / len(recent_posts) if recent_posts else 0
                avg_comments = total_comments / len(recent_posts) if recent_posts else 0
                avg_views = total_views / reel_count if reel_count else 0
                engagement_rate = ((avg_likes + avg_comments) / user_data['edge_followed_by']['count']) * 100 if user_data['edge_followed_by']['count'] > 0 else 0
                
                return {
                    'followers': user_data['edge_followed_by']['count'],
                    'following': user_data['edge_follow']['count'],
                    'posts_count': user_data['edge_owner_to_timeline_media']['count'],
                    'biography': user_data.get('biography', ''),
                    'avg_likes': int(avg_likes),
                    'avg_comments': int(avg_comments),
                    'avg_reel_views': int(avg_views),
                    'engagement_rate': round(engagement_rate, 2),
                    'is_verified': user_data.get('is_verified', False),
                    'is_business': user_data.get('is_business_account', False),
                    'category': user_data.get('category_name', '')
                }
            
            elif response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 60))
                print(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Got status code {response.status_code}. Retrying...")
                time.sleep(random.uniform(5, 10))
            
        except Exception as e:
            last_error = str(e)
            print(f"Error occurred: {last_error}. Retry {retry_count + 1}/{max_retries}")
            time.sleep(random.uniform(5, 10))
        
        retry_count += 1
    
    return None

@influencers_bp.route('/fetch_influencer_metrics', methods=['POST'])
@login_required
def fetch_influencer_metrics():
    try:
        user = User.query.get(current_user.user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Fetch Instagram data
        data = get_instagram_profile(user.username)
        if not data:
            return jsonify({'error': 'Failed to fetch Instagram data'}), 500

        # Update or create metrics
        metrics = SocialMediaMetric.query.filter_by(user_id=user.user_id).first()
        if not metrics:
            metrics = SocialMediaMetric(user_id=user.user_id)
            db.session.add(metrics)

        # Update metrics with new data
        metrics.followers = data['followers']
        metrics.following = data['following']
        metrics.posts_count = data['posts_count']
        metrics.avg_likes = data['avg_likes']
        metrics.avg_comments = data['avg_comments']
        metrics.avg_reel_views = data['avg_reel_views']
        metrics.engagement_rate = data['engagement_rate']
        metrics.is_verified = data['is_verified']
        metrics.is_business_account = data['is_business']
        metrics.bio = data['biography']
        metrics.platform = 'instagram'
        metrics.updated_at = datetime.utcnow()

        # Get AI analysis and store it
        analyze_profile_with_gemini(metrics)
        
        db.session.commit()
        return jsonify({'message': 'Metrics and analysis updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
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
@influencers_bp.route('/send_request/<int:campaign_id>', methods=['POST'])
@login_required
def send_request(campaign_id):
    influencer_id = current_user.influencer.influencer_id
    request_description = request.form.get('request_description')

    # Check if the influencer has already sent a request for this campaign
    existing_request = CampaignRequest.query.filter_by(
        influencer_id=influencer_id, campaign_id=campaign_id).first()

    if existing_request:
        flash('You have already sent a request for this campaign.', 'warning')
        return redirect(url_for('influencers.campaign_influe'))

    # Create a new CampaignRequest
    new_request = CampaignRequest(
        campaign_id=campaign_id,
        influencer_id=influencer_id,
        sponsor_id=Campaign.query.get(campaign_id).sponsor_id,
        request_description=request_description,
        status='PENDING'
    )
    db.session.add(new_request)
    db.session.commit()

    flash('Request sent successfully!', 'success')
    return redirect(url_for('influencers.campaign_influe'))  # Redirect to the campInflue page



@influencers_bp.route('/campaign_influe')
@login_required
def campaign_influe():
    influencer_id = current_user.influencer.influencer_id

    # Fetch requests sent by the current influencer
    requests = CampaignRequest.query.filter_by(influencer_id=influencer_id).all()
# Convert the Enum status to a string (e.g., 'pending', 'accepted', 'rejected')
    for request in requests:
        request.status = request.status.value  # This will give you the string representation
    # Pass data to the template
    return render_template('campInflue.html', requests=requests)
