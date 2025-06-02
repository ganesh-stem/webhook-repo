from app import create_app
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = create_app()

if __name__ == '__main__': 
    # Use port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # For production, set debug=False
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)