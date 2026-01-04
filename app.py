#!/usr/bin/env python3
"""
Flask API server for ChatGPT Bot
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from gemini_bot import ChatGPTBot

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "ChatGPT Bot API"
    }), 200


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Chat API endpoint.

    Expected JSON body:
    {
        "prompt": "Your question here"
    }

    Returns:
    {
        "response": "ChatGPT response",
        "success": true/false,
        "error": "error message if failed"
    }
    """
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data:
            return jsonify({
                "response": "",
                "success": False,
                "error": "No JSON data provided"
            }), 400

        # Extract prompt
        prompt = data.get('prompt', '').strip()

        if not prompt:
            return jsonify({
                "response": "",
                "success": False,
                "error": "Prompt is required and cannot be empty"
            }), 400

        # Create bot instance (headless mode)
        bot = ChatGPTBot(headless=True)

        # Send message and get response
        response = bot.send_message(prompt)

        if response:
            return jsonify({
                "response": response,
                "success": True
            }), 200
        else:
            return jsonify({
                "response": "",
                "success": False,
                "error": "Failed to get response from ChatGPT"
            }), 500

    except Exception as e:
        return jsonify({
            "response": "",
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/chat', methods=['GET'])
def chat_get():
    """
    Chat API endpoint (GET method for simple testing).

    Query parameter: ?prompt=Your question here
    """
    try:
        # Get prompt from query parameter
        prompt = request.args.get('prompt', '').strip()

        if not prompt:
            return jsonify({
                "response": "",
                "success": False,
                "error": "Prompt parameter is required. Use ?prompt=Your question"
            }), 400

        # Create bot instance (headless mode)
        bot = ChatGPTBot(headless=True)

        # Send message and get response
        response = bot.send_message(prompt)

        if response:
            return jsonify({
                "response": response,
                "success": True
            }), 200
        else:
            return jsonify({
                "response": "",
                "success": False,
                "error": "Failed to get response from ChatGPT"
            }), 500

    except Exception as e:
        return jsonify({
            "response": "",
            "success": False,
            "error": str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": [
            "GET /health",
            "POST /api/chat",
            "GET /api/chat?prompt=your_question"
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        "error": "Internal server error",
        "message": str(error)
    }), 500


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='ChatGPT Bot Flask API Server')
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ChatGPT Bot API Server")
    print("=" * 60)
    print(f"Server starting on http://{args.host}:{args.port}")
    print(f"Health check: http://{args.host}:{args.port}/health")
    print(f"API endpoint: http://{args.host}:{args.port}/api/chat")
    print("=" * 60)

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )
