from flask import Flask, render_template, request, jsonify
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import pandas as pd
import plotly.express as px
import plotly.io as pio
# Make sure to create a config.py with your API key
from config import YOUTUBE_API_KEY
from textblob import TextBlob

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


# Create the database
# with app.app_context():
#     db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. You can now log in.')
        return redirect(url_for('login'))

    return render_template('register.html')

# Login Route


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful.')
            return redirect(url_for('landing'))
        else:
            flash('Login failed. Check your username and/or password.')
            return redirect(url_for('login'))

    return render_template('login.html')

# Dashboard Route (for logged in users)


# @app.route('/dashboard')
# @login_required
# def dashboard():
#     return render_template('dashboard.html', username=current_user.username)

# Logout Route


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. You can now log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/landing')
def landing():
    return render_template('index.html')


def fetch_youtube_data(username):
    # Step 1: Search for channels matching the username
    search_url = f'https://www.googleapis.com/youtube/v3/search?key={
        YOUTUBE_API_KEY}&q={username}&type=channel&part=id,snippet'
    search_response = requests.get(search_url)
    search_data = search_response.json()

    # Check if any channels were found
    if 'items' not in search_data or len(search_data['items']) == 0:
        return pd.DataFrame(), None  # Return empty DataFrame if no channels found

    # Assume the first result is the most relevant channel
    channel_id = search_data['items'][0]['id']['channelId']
    channel_title = search_data['items'][0]['snippet']['title']

    # Step 2: Fetch videos using the channel ID
    video_url = f'https://www.googleapis.com/youtube/v3/search?key={
        YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id&order=date&type=video'
    response = requests.get(video_url)
    videos_data = response.json().get('items', [])

    videos = []
    for video in videos_data:
        video_id = video['id']['videoId']
        title = video['snippet']['title']

        # Fetch video statistics
        stats_url = f'https://www.googleapis.com/youtube/v3/videos?key={
            YOUTUBE_API_KEY}&id={video_id}&part=statistics'
        stats_response = requests.get(stats_url)
        stats_data = stats_response.json().get('items', [])[0].get('statistics', {})

        views = int(stats_data.get('viewCount', 0))
        likes = int(stats_data.get('likeCount', 0))
        comments_count = int(stats_data.get('commentCount', 0))

        videos.append({
            'title': title,
            'video_id': video_id,
            'views': views,
            'likes': likes,
            'comments_count': comments_count,
        })

    return pd.DataFrame(videos), channel_title


def fetch_trending_videos(region_code='ZW'):
    trending_url = f'https://www.googleapis.com/youtube/v3/videos?key={
        YOUTUBE_API_KEY}&part=snippet,statistics&chart=mostPopular&regionCode={region_code}'
    response = requests.get(trending_url)
    trending_data = response.json().get('items', [])

    trending_videos = []
    for video in trending_data:
        video_id = video['id']
        title = video['snippet']['title']
        views = int(video['statistics'].get('viewCount', 0))
        likes = int(video['statistics'].get('likeCount', 0))
        comments_count = int(video['statistics'].get('commentCount', 0))

        trending_videos.append({
            'title': title,
            'video_id': video_id,
            'views': views,
            'likes': likes,
            'comments_count': comments_count,
        })

    return pd.DataFrame(trending_videos)


@app.route('/trending', methods=['POST'])
def trending_videos():
    region_code = request.form['region_code']
    trending_videos_df = fetch_trending_videos(region_code)

    # Check if the DataFrame is empty
    if trending_videos_df.empty:
        return render_template('trending.html', error="No trending videos found for the given region.")

    return render_template('trending.html', trending_videos=trending_videos_df.to_dict(orient='records'), region_code=region_code)


# @app.route('/video/<video_id>')
# def video_details(video_id):
#     # Fetch video statistics using the video ID
#     stats_url = f'https://www.googleapis.com/youtube/v3/videos?key={
#         YOUTUBE_API_KEY}&id={video_id}&part=statistics'
#     stats_response = requests.get(stats_url)
#     stats_data = stats_response.json().get('items', [])[0].get('statistics', {})

#     # Extract statistics
#     views = int(stats_data.get('viewCount', 0))
#     likes = int(stats_data.get('likeCount', 0))
#     # Get dislikes if available
#     dislikes = int(stats_data.get('dislikeCount', 0))

#     # Create DataFrame for views and likes
#     views_data = {
#         'Metric': ['Views', 'Likes'],
#         'Count': [views, likes]
#     }
#     views_df = pd.DataFrame(views_data)

#     # Create DataFrame for sentiment analysis (Likes vs Dislikes)
#     sentiment_data = {
#         'Sentiment': ['Likes', 'Dislikes'],
#         'Count': [likes, dislikes]
#     }
#     sentiment_df = pd.DataFrame(sentiment_data)

#     # Create plots
#     views_fig = px.bar(views_df, x='Metric', y='Count',
#                        title=f'Views and Likes for Video ID: {video_id}',
#                        labels={'Count': 'Count', 'Metric': 'Metric'})

#     sentiment_fig = px.bar(sentiment_df, x='Sentiment', y='Count',
#                            title=f'Sentiment Analysis for Video ID: {
#                                video_id}',
#                            labels={'Count': 'Count', 'Sentiment': 'Sentiment'})

#     views_graph_json = pio.to_json(views_fig)
#     sentiment_graph_json = pio.to_json(sentiment_fig)

#     return render_template('video_details.html',
#                            views_graph_json=views_graph_json,
#                            sentiment_graph_json=sentiment_graph_json,
#                            video_id=video_id)


# @app.route('/video/<video_id>')
# def video_details(video_id):
#     # Fetch video statistics
#     stats_url = f'https://www.googleapis.com/youtube/v3/videos?key={
#         YOUTUBE_API_KEY}&id={video_id}&part=statistics'
#     stats_response = requests.get(stats_url)
#     stats_data = stats_response.json().get('items', [])[0].get('statistics', {})

#     views = int(stats_data.get('viewCount', 0))
#     likes = int(stats_data.get('likeCount', 0))
#     dislikes = int(stats_data.get('dislikeCount', 0))  # Get dislikes

#     # Fetch comments for the video
#     comments_url = f'https://www.googleapis.com/youtube/v3/commentThreads?key={
#         YOUTUBE_API_KEY}&videoId={video_id}&part=snippet&maxResults=100'
#     comments_response = requests.get(comments_url)
#     comments_data = comments_response.json().get('items', [])

#     # Analyze sentiments
#     positive_comments = 0
#     negative_comments = 0

#     for item in comments_data:
#         comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
#         analysis = TextBlob(comment)
#         if analysis.sentiment.polarity > 0:
#             positive_comments += 1
#         elif analysis.sentiment.polarity < 0:
#             negative_comments += 1

#     # Create DataFrames for plotting
#     views_data = {
#         'Metric': ['Views', 'Likes'],
#         'Count': [views, likes]
#     }
#     views_df = pd.DataFrame(views_data)

#     sentiment_data = {
#         'Sentiment': ['Likes', 'Dislikes'],
#         'Count': [likes, dislikes]
#     }
#     sentiment_df = pd.DataFrame(sentiment_data)

#     # Comment sentiment analysis DataFrame
#     comment_sentiment_data = {
#         'Sentiment': ['Positive', 'Negative'],
#         'Count': [positive_comments, negative_comments]
#     }
#     comment_sentiment_df = pd.DataFrame(comment_sentiment_data)

#     # Create plots
#     views_fig = px.bar(views_df, x='Metric', y='Count',
#                        title=f'Views and Likes for Video ID: {video_id}',
#                        labels={'Count': 'Count', 'Metric': 'Metric'})

#     sentiment_fig = px.bar(sentiment_df, x='Sentiment', y='Count',
#                            title=f'Sentiment Analysis for Video ID: {
#                                video_id}',
#                            labels={'Count': 'Count', 'Sentiment': 'Sentiment'})

#     comment_sentiment_fig = px.bar(comment_sentiment_df, x='Sentiment', y='Count',
#                                    title=f'Comment Sentiment Analysis for Video ID: {
#                                        video_id}',
#                                    labels={'Count': 'Count', 'Sentiment': 'Sentiment'})

#     views_graph_json = pio.to_json(views_fig)
#     sentiment_graph_json = pio.to_json(sentiment_fig)
#     comment_sentiment_graph_json = pio.to_json(comment_sentiment_fig)

#     return render_template('video_details.html',
#                            views_graph_json=views_graph_json,
#                            sentiment_graph_json=sentiment_graph_json,
#                            comment_sentiment_graph_json=comment_sentiment_graph_json,
#                            video_id=video_id)


@app.route('/video/<video_id>')
def video_details(video_id):
    # Fetch video statistics
    stats_url = f'https://www.googleapis.com/youtube/v3/videos?key={
        YOUTUBE_API_KEY}&id={video_id}&part=statistics'
    stats_response = requests.get(stats_url)
    stats_data = stats_response.json().get('items', [])[0].get('statistics', {})

    views = int(stats_data.get('viewCount', 0))
    likes = int(stats_data.get('likeCount', 0))
    dislikes = int(stats_data.get('dislikeCount', 0))  # Get dislikes

    # Fetch comments for the video
    comments_url = f'https://www.googleapis.com/youtube/v3/commentThreads?key={
        YOUTUBE_API_KEY}&videoId={video_id}&part=snippet&maxResults=100'
    comments_response = requests.get(comments_url)
    comments_data = comments_response.json().get('items', [])

    # Analyze sentiments
    positive_comments = 0
    negative_comments = 0

    for item in comments_data:
        comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
        analysis = TextBlob(comment)
        if analysis.sentiment.polarity > 0:
            positive_comments += 1
        elif analysis.sentiment.polarity < 0:
            negative_comments += 1

    # Create DataFrames for plotting
    views_data = {
        'Metric': ['Views', 'Likes'],
        'Count': [views, likes]
    }
    views_df = pd.DataFrame(views_data)

    sentiment_data = {
        'Sentiment': ['Likes', 'Dislikes'],
        'Count': [likes, dislikes]
    }
    sentiment_df = pd.DataFrame(sentiment_data)

    # Comment sentiment analysis DataFrame for pie chart
    comment_sentiment_data = {
        'Sentiment': ['Positive', 'Negative'],
        'Count': [positive_comments, negative_comments]
    }
    comment_sentiment_df = pd.DataFrame(comment_sentiment_data)

    # Create plots
    views_fig = px.bar(views_df, x='Metric', y='Count',
                       title=f'Views and Likes for Video ID: {video_id}',
                       labels={'Count': 'Count', 'Metric': 'Metric'})

    sentiment_fig = px.bar(sentiment_df, x='Sentiment', y='Count',
                           title=f'Sentiment Analysis for Video ID: {
                               video_id}',
                           labels={'Count': 'Count', 'Sentiment': 'Sentiment'})

    # Create a pie chart for comment sentiment analysis with custom colors
    comment_sentiment_fig = px.pie(comment_sentiment_df, values='Count', names='Sentiment',
                                   title=f'Comment Sentiment Analysis for Video ID: {
                                       video_id}',
                                   color='Sentiment',
                                   # Green for positive, Red for negative
                                   color_discrete_sequence=['green', 'brown'])

    views_graph_json = pio.to_json(views_fig)
    sentiment_graph_json = pio.to_json(sentiment_fig)
    comment_sentiment_graph_json = pio.to_json(comment_sentiment_fig)

    return render_template('video_details.html',
                           views_graph_json=views_graph_json,
                           sentiment_graph_json=sentiment_graph_json,
                           comment_sentiment_graph_json=comment_sentiment_graph_json,
                           video_id=video_id)


def analyze_sentiment(title):
    analysis = TextBlob(title)
    return analysis.sentiment.polarity  # Return a sentiment score


@app.route('/channel', methods=['POST'])
@login_required
def channel_analysis():
    username = request.form['channel_id']
    videos_df, channel_title = fetch_youtube_data(username)

    if videos_df.empty:
        return render_template('channel_analysis.html', error="No videos found for the given username.")

    # Fetch trending videos
    trending_videos_df = fetch_trending_videos()

    # Sort videos to find most and least viewed
    most_viewed_df = videos_df.sort_values(by='views', ascending=False).head(5)
    least_viewed_df = videos_df.sort_values(by='views').head(5)

    # Analyze sentiment for most and least viewed
    most_viewed_df['sentiment'] = most_viewed_df['title'].apply(
        analyze_sentiment)
    least_viewed_df['sentiment'] = least_viewed_df['title'].apply(
        analyze_sentiment)

    # Visualization: Number of Likes per Video
    fig = px.bar(videos_df, x='title', y='likes', title='Number of Likes per Video', labels={
                 'likes': 'Likes', 'title': 'Video Title'})
    graph_json = pio.to_json(fig)

    # Visualization: Sentiment Analysis
    sentiment_fig = px.bar(most_viewed_df, x='title', y='sentiment', title='Sentiment of Most Viewed Videos', labels={
                           'sentiment': 'Sentiment Score', 'title': 'Video Title'})
    sentiment_graph_json = pio.to_json(sentiment_fig)

    return render_template('channel_analysis.html',
                           graph_json=graph_json,
                           sentiment_graph_json=sentiment_graph_json,
                           videos=videos_df.to_dict(orient='records'),
                           channel_title=channel_title,
                           most_viewed_videos=most_viewed_df.to_dict(
                               orient='records'),
                           least_viewed_videos=least_viewed_df.to_dict(
                               orient='records'),
                           trending_videos=trending_videos_df.to_dict(orient='records'))


@app.route('/video_data/<video_id>')
def video_data(video_id):
    # Fetch video statistics
    stats_url = f'https://www.googleapis.com/youtube/v3/videos?key={
        YOUTUBE_API_KEY}&id={video_id}&part=statistics,snippet'
    stats_response = requests.get(stats_url)

    if stats_response.status_code != 200:
        return jsonify({'error': 'Video not found'}), 404

    stats_data = stats_response.json().get('items', [])[0]
    title = stats_data['snippet']['title']
    views = int(stats_data['statistics'].get('viewCount', 0))
    likes = int(stats_data['statistics'].get('likeCount', 0))
    comments_count = int(stats_data['statistics'].get('commentCount', 0))

    # For sentiment analysis on comments
    # Implement this function to fetch comments
    comments = fetch_video_comments(video_id)
    sentiment_scores = [analyze_sentiment(comment) for comment in comments]

    # Calculate average sentiment score for comments
    avg_sentiment = sum(sentiment_scores) / \
        len(sentiment_scores) if sentiment_scores else 0

    return jsonify({
        'title': title,
        'views': views,
        'likes': likes,
        'avg_sentiment': avg_sentiment,
        'comments_count': comments_count,
    })


def fetch_video_comments(video_id):
    # Function to fetch comments from a video
    comments = []
    next_page_token = None

    while True:
        comment_url = f'https://www.googleapis.com/youtube/v3/commentThreads?key={
            YOUTUBE_API_KEY}&textFormat=plainText&part=snippet&videoId={video_id}&pageToken={next_page_token}'
        response = requests.get(comment_url)

        if response.status_code != 200:
            break

        comments_data = response.json().get('items', [])
        for item in comments_data:
            comment_text = item['snippet']['topLevelComment']['snippet']['textDisplay']
            comments.append(comment_text)

        next_page_token = response.json().get('nextPageToken')
        if not next_page_token:
            break

    return comments


if __name__ == '__main__':
    app.run(debug=True)
