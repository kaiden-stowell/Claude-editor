import os

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    TEMP_FOLDER = os.path.join(BASE_DIR, 'temp')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'base')
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    HOST = os.environ.get('EDITOR_HOST', '127.0.0.1')
    PORT = int(os.environ.get('EDITOR_PORT', '12795'))
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())

    @classmethod
    def init_dirs(cls):
        for d in [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER, cls.TEMP_FOLDER]:
            os.makedirs(d, exist_ok=True)
