import os
import shutil

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    TEMP_FOLDER = os.path.join(BASE_DIR, 'temp')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB
    WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'base')
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-6')
    HOST = os.environ.get('EDITOR_HOST', '127.0.0.1')
    PORT = int(os.environ.get('EDITOR_PORT', '12795'))
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())

    @classmethod
    def find_claude(cls):
        env_bin = os.environ.get('CLAUDE_BIN')
        if env_bin and os.path.isfile(env_bin):
            return env_bin
        candidates = [
            os.path.join(os.environ.get('HOME', ''), '.local', 'bin', 'claude'),
            '/opt/homebrew/bin/claude',
            '/usr/local/bin/claude',
            os.path.join(os.environ.get('HOME', ''), '.npm', 'bin', 'claude'),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return shutil.which('claude')

    @classmethod
    def has_claude(cls):
        return cls.find_claude() is not None

    @classmethod
    def init_dirs(cls):
        for d in [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER, cls.TEMP_FOLDER]:
            os.makedirs(d, exist_ok=True)
