from flask import Blueprint, render_template, redirect, url_for, session

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return redirect(url_for('auth.login'))

@main_bp.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    return render_template('index.html')

@main_bp.route('/complaints')
def complaints():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    # Placeholder for actual complaints logic if needed
    dummy_complaints = [
        {'ack_no': 'ACK123', 'victim_name': 'John Doe', 'date': '2024-12-10', 'status': 'Under Review'},
        {'ack_no': 'ACK456', 'victim_name': 'Jane Smith', 'date': '2024-12-11', 'status': 'Resolved'},
    ]
    return render_template('complaint.html', complaints=dummy_complaints)
