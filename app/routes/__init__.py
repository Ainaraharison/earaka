def register_blueprints(app):
    from .auth import bp as auth_bp
    from .learning import bp as learning_bp
    from .badges import bp as badges_bp
    from .interests import bp as interests_bp
    from .challenge import bp as challenge_bp
    from .quiz import bp as quiz_bp
    from .chat import bp as chat_bp
    from .suggest import bp as suggest_bp
    from .help import bp as help_bp
    from .profile import bp as profile_bp

    for blueprint in [auth_bp, learning_bp, badges_bp, interests_bp, challenge_bp, quiz_bp, chat_bp, suggest_bp, help_bp, profile_bp]:
        app.register_blueprint(blueprint)
