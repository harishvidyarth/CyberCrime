import os
import secrets
import contextlib
import logging

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)

@contextlib.contextmanager
def file_lock(filepath):
    """Context manager for file locking (Cross-platform)"""
    lock_file = f"{filepath}.lock"
    # Create lock file if it doesn't exist
    lock_fd = os.open(lock_file, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
    try:
        if os.name == 'nt':
            # Windows: Blocking lock for 10 attempts (approx 10s)
            msvcrt.locking(lock_fd, msvcrt.LK_RLCK, 1)
        else:
            # Unix: Exclusive blocking lock
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        
        yield
    finally:
        # Unlock and clean up
        if os.name == 'nt':
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        
        os.close(lock_fd)
        try:
            os.remove(lock_file)
        except OSError:
            pass

def allowed_file(filename, allowed_extensions={'xlsx', 'xls'}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, upload_folder):
    """Save a file with a secure random name and return the filename."""
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{secrets.token_hex(16)}.{ext}"
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    return filename

import sys
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS   # PyInstaller
    else:
        # Assuming we are in app/utils/
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)
