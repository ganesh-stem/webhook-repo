from flask import Blueprint, request, jsonify, render_template
from app.extensions import mongo
from datetime import datetime
import json

webhook = Blueprint('webhook', __name__, url_prefix='/webhook')

@webhook.route('/receiver', methods=["POST"])
def receiver():
    try:
        # Get the webhook payload
        payload = request.get_json()
        
        if not payload:
            return jsonify({"error": "No payload received"}), 400
        
        # Process different GitHub events
        event_type = request.headers.get('X-GitHub-Event', '')
        
        if event_type == 'push':
            process_push_event(payload)
        elif event_type == 'pull_request':
            process_pull_request_event(payload)
        elif event_type == 'merge':
            process_merge_event(payload)
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

def process_push_event(payload):
    """Process push events"""
    try:
        author = payload['pusher']['name']
        branch = payload['ref'].split('/')[-1]  # Extract branch name from refs/heads/branch-name
        timestamp = datetime.utcnow()
        
        event_data = {
            'event_type': 'push',
            'author': author,
            'to_branch': branch,
            'timestamp': timestamp,
            'message': f"{author} pushed to {branch} on {timestamp.strftime('%d %B %Y - %I:%M %p UTC')}"
        }
        
        # Store in MongoDB
        mongo.db.github_events.insert_one(event_data)
        print(f"Push event stored: {event_data['message']}")
        
    except Exception as e:
        print(f"Error processing push event: {str(e)}")

def process_pull_request_event(payload):
    """Process pull request events"""
    try:
        # Only process when PR is opened
        if payload['action'] != 'opened':
            return
            
        author = payload['pull_request']['user']['login']
        from_branch = payload['pull_request']['head']['ref']
        to_branch = payload['pull_request']['base']['ref']
        timestamp = datetime.utcnow()
        
        event_data = {
            'event_type': 'pull_request',
            'author': author,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'timestamp': timestamp,
            'message': f"{author} submitted a pull request from {from_branch} to {to_branch} on {timestamp.strftime('%d %B %Y - %I:%M %p UTC')}"
        }
        
        # Store in MongoDB
        mongo.db.github_events.insert_one(event_data)
        print(f"Pull request event stored: {event_data['message']}")
        
    except Exception as e:
        print(f"Error processing pull request event: {str(e)}")

def process_merge_event(payload):
    """Process merge events (when PR is merged)"""
    try:
        # Check if this is a merged pull request
        if payload.get('action') != 'closed' or not payload.get('pull_request', {}).get('merged'):
            return
            
        author = payload['pull_request']['merged_by']['login']
        from_branch = payload['pull_request']['head']['ref']
        to_branch = payload['pull_request']['base']['ref']
        timestamp = datetime.utcnow()
        
        event_data = {
            'event_type': 'merge',
            'author': author,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'timestamp': timestamp,
            'message': f"{author} merged branch {from_branch} to {to_branch} on {timestamp.strftime('%d %B %Y - %I:%M %p UTC')}"
        }
        
        # Store in MongoDB
        mongo.db.github_events.insert_one(event_data)
        print(f"Merge event stored: {event_data['message']}")
        
    except Exception as e:
        print(f"Error processing merge event: {str(e)}")

@webhook.route('/')
def dashboard():
    """Display the dashboard"""
    return render_template('dashboard.html')

@webhook.route('/api/events')
def get_events():
    """API endpoint to get latest events"""
    try:
        # Get latest 20 events, sorted by timestamp (newest first)
        events = list(mongo.db.github_events.find(
            {}, 
            {'_id': 0}  # Exclude MongoDB _id field
        ).sort('timestamp', -1).limit(20))
        
        # Format timestamps for display
        for event in events:
            if 'timestamp' in event:
                event['timestamp'] = event['timestamp'].isoformat()
        
        return jsonify(events)
        
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return jsonify([]), 500