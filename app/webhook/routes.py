from flask import Blueprint, request, jsonify, render_template
from app.extensions import mongo
from datetime import datetime
import json
import hashlib

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
        # Note: GitHub doesn't have a separate 'merge' event, it's part of pull_request
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

def generate_request_id(payload, event_type, action=None):
    """Generate a unique request_id based on payload content"""
    if event_type == 'push':
        # Use commit hash for push events
        commits = payload.get('commits', [])
        if commits:
            return commits[0].get('id', '')[:12]  # First 12 chars of commit hash
    elif event_type == 'pull_request':
        # Use PR number with action suffix for pull request events
        pr_number = payload.get('pull_request', {}).get('number', '')
        if action == 'opened':
            return f"pr-{pr_number}-opened"
        elif action == 'closed' and payload.get('pull_request', {}).get('merged'):
            return f"pr-{pr_number}-merged"
        else:
            return f"pr-{pr_number}-{action or 'unknown'}"
    
    # Fallback: generate hash from payload
    payload_str = json.dumps(payload, sort_keys=True)
    return hashlib.md5(payload_str.encode()).hexdigest()[:12]

def process_push_event(payload):
    """Process push events"""
    try:
        author = payload['pusher']['name']
        branch = payload['ref'].split('/')[-1]  # Extract branch name from refs/heads/branch-name
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')  # UTC datetime string
        request_id = generate_request_id(payload, 'push')
        
        event_data = {
            'request_id': request_id,
            'author': author,
            'action': 'PUSH',
            'from_branch': None,  # Push events don't have from_branch
            'to_branch': branch,
            'timestamp': timestamp
        }
        
        # Store in MongoDB
        mongo.db.github_events.insert_one(event_data)
        print(f"Push event stored: {author} pushed to {branch}")
        
    except Exception as e:
        print(f"Error processing push event: {str(e)}")

def process_pull_request_event(payload):
    """Process pull request events"""
    try:
        action = payload.get('action', '')
        
        # Handle both opened PR and merged PR
        if action == 'opened':
            author = payload['pull_request']['user']['login']
            from_branch = payload['pull_request']['head']['ref']
            to_branch = payload['pull_request']['base']['ref']
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            request_id = generate_request_id(payload, 'pull_request', action)
            
            event_data = {
                'request_id': request_id,
                'author': author,
                'action': 'PULL_REQUEST',
                'from_branch': from_branch,
                'to_branch': to_branch,
                'timestamp': timestamp
            }
            
            # Store in MongoDB
            mongo.db.github_events.insert_one(event_data)
            print(f"Pull request event stored: {author} submitted PR from {from_branch} to {to_branch}")
            
        elif action == 'closed' and payload.get('pull_request', {}).get('merged'):
            # This is a merge event
            author = payload['pull_request']['merged_by']['login']
            from_branch = payload['pull_request']['head']['ref']
            to_branch = payload['pull_request']['base']['ref']
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            request_id = generate_request_id(payload, 'pull_request', action)
            
            event_data = {
                'request_id': request_id,
                'author': author,
                'action': 'MERGE',
                'from_branch': from_branch,
                'to_branch': to_branch,
                'timestamp': timestamp
            }
            
            # Store in MongoDB
            mongo.db.github_events.insert_one(event_data)
            print(f"Merge event stored: {author} merged {from_branch} to {to_branch}")
        
    except Exception as e:
        print(f"Error processing pull request event: {str(e)}")

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
        
        # Add formatted messages for display (keeping schema intact)
        for event in events:
            action = event.get('action', '').lower()
            author = event.get('author', 'Unknown')
            timestamp_str = event.get('timestamp', '')
            
            # Format timestamp for display
            try:
                if timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%d %B %Y - %I:%M %p UTC')
                else:
                    formatted_time = 'Unknown time'
            except:
                formatted_time = timestamp_str
            
            # Generate display message based on action
            if action == 'push':
                to_branch = event.get('to_branch', 'unknown')
                event['display_message'] = f"{author} pushed to {to_branch} on {formatted_time}"
            elif action == 'pull_request':
                from_branch = event.get('from_branch', 'unknown')
                to_branch = event.get('to_branch', 'unknown')
                event['display_message'] = f"{author} submitted a pull request from {from_branch} to {to_branch} on {formatted_time}"
            elif action == 'merge':
                from_branch = event.get('from_branch', 'unknown')
                to_branch = event.get('to_branch', 'unknown')
                event['display_message'] = f"{author} merged branch {from_branch} to {to_branch} on {formatted_time}"
            else:
                event['display_message'] = f"{author} performed {action} on {formatted_time}"
        
        return jsonify(events)
        
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return jsonify([]), 500