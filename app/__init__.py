from flask import Flask
from app.extensions import mongo
from app.webhook.routes import webhook

def create_app():
    app = Flask(__name__)
    
    # MongoDB Configuration
    app.config['MONGO_URI'] = 'mongodb://localhost:27017/github_webhooks'
    
    # Initialize extensions
    mongo.init_app(app)
    
    # Register blueprints
    app.register_blueprint(webhook)
    
    return app