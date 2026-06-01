from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import defer
from datetime import datetime, timezone, timedelta
import io
import os

from ..extensions import db
from ..models import User, UploadedFile, Transaction, UsageLog, Complaint
from ..utils.security import admin_required
from ..utils.logging import log_usage

# ReportLab imports for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin_dashboard')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', username=current_user.username)

@admin_bp.route('/view_officers')
@login_required
@admin_required
def view_officers():
    officers = User.query.filter_by(role='Investigative Officer').all()
    officer_data = []
    for officer in officers:
        computed_upload_count = UploadedFile.query.filter_by(uploader=officer.username).count()
        upload_count = officer.manual_upload_count if officer.manual_upload_count is not None else computed_upload_count
        officer_data.append({
            'username': officer.username,
            'role': officer.role,
            'upload_count': upload_count,
            'computed_upload_count': computed_upload_count,
            'manual_upload_count': officer.manual_upload_count,
            'name': officer.name,
            'rank': officer.rank,
            'email': officer.email
        })
    return render_template('view_officers.html', officers=officer_data)

@admin_bp.route('/update_officer', methods=['POST'])
@login_required
@admin_required
def update_officer():
    username = (request.form.get('username') or '').strip()
    if not username:
        flash('Invalid request.')
        return redirect(url_for('admin.view_officers'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Officer not found.')
        return redirect(url_for('admin.view_officers'))

    if user.role != 'Investigative Officer':
        flash('Only Investigative Officers can be edited here.')
        return redirect(url_for('admin.view_officers'))

    user.name = (request.form.get('name') or '').strip() or None
    user.rank = (request.form.get('rank') or '').strip() or None
    user.email = (request.form.get('email') or '').strip() or None

    manual_upload_count_raw = (request.form.get('manual_upload_count') or '').strip()
    if manual_upload_count_raw == '':
        user.manual_upload_count = None
    else:
        try:
            user.manual_upload_count = int(manual_upload_count_raw)
        except ValueError:
            flash('No. of Files Uploaded must be a number (or leave blank).')
            return redirect(url_for('admin.view_officers'))

    db.session.commit()
    flash(f'Officer {username} updated successfully.')
    return redirect(url_for('admin.view_officers'))

@admin_bp.route('/edit_officer/<int:officer_id>', methods=['POST'])
@login_required
@admin_required
def edit_officer(officer_id):
    officer = User.query.get(officer_id)
    if not officer:
        return jsonify({'error': 'Officer not found'}), 404

    password = request.json.get('password')
    if password:
        try:
            officer.set_password(password)
            db.session.commit()
            return jsonify({'message': 'Password updated successfully'})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    return jsonify({'error': 'No password provided'}), 400

@admin_bp.route('/add_officer', methods=['GET', 'POST'])
@login_required
@admin_required
def add_officer():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        name = request.form.get('name')
        rank = request.form.get('rank')
        email = request.form.get('email')

        if not username or not password or not role:
            flash('Username, Password, and Role are required.')
            return redirect(url_for('admin.add_officer'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
            return redirect(url_for('admin.add_officer'))

        try:
            new_user = User(username=username, role=role, name=name, rank=rank, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash(f'Officer {username} added successfully.')
            return redirect(url_for('admin.view_officers'))
        except ValueError as e:
            flash(str(e))
            return redirect(url_for('admin.add_officer'))
    
    return render_template('add_officer.html')

@admin_bp.route('/delete_officer', methods=['POST'])
@login_required
@admin_required
def delete_officer():
    username = request.form.get('username')
    if not username:
        flash('Invalid request.')
        return redirect(url_for('admin.view_officers'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Officer not found.')
        return redirect(url_for('admin.view_officers'))

    if user.role == 'Admin':
        flash('Cannot delete admin user.')
        return redirect(url_for('admin.view_officers'))

    db.session.delete(user)
    db.session.commit()    
    flash(f'Officer {username} deleted successfully.')
    return redirect(url_for('admin.view_officers'))

@admin_bp.route('/view_analytics')
@login_required
@admin_required
def view_analytics():
    log_usage('view_analytics')
    total_uploaded_files = db.session.query(func.count(func.distinct(UploadedFile.filename))).scalar()
    total_txns = db.session.query(func.count(Transaction.id)).scalar()
    total_amount = db.session.query(func.sum(Transaction.amount)).scalar() or 0

    txns_per_file = db.session.query(
        UploadedFile.filename,
        func.count(Transaction.id).label("txn_count")
    ).join(Transaction, Transaction.upload_id == UploadedFile.id)\
     .group_by(UploadedFile.filename)\
     .all()

    officer_uploads = db.session.query(
        User.username,
        func.count(UploadedFile.id).label('upload_count')
    ).join(UploadedFile, UploadedFile.uploader == User.username)\
     .filter(User.role == 'Investigative Officer')\
     .group_by(User.username)\
     .all()

    frequent_ifsccodes = db.session.query(
        Transaction.ifsc_code,
        func.count(Transaction.id).label('count')
    ).group_by(Transaction.ifsc_code)\
     .order_by(desc(func.count(Transaction.id)))\
     .limit(5)\
     .all()

    return render_template("view_analytics.html",
        total_uploaded_files=total_uploaded_files,
        total_txns=total_txns,
        total_amount=total_amount,
        txns_per_file=txns_per_file,
        officer_uploads=officer_uploads,
        frequent_ifsccodes=frequent_ifsccodes
    )

@admin_bp.route('/download_logs')
@login_required
@admin_required
def download_logs():
    try:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        logs = UsageLog.query.filter(UsageLog.timestamp >= start_of_day, UsageLog.timestamp < end_of_day).order_by(UsageLog.timestamp.asc()).all()
        
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        width, height = landscape(A4)
        y = height - 50
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30, y, f"Usage Logs - {start_of_day.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d')}")
        y -= 30
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(30, y, "Timestamp")
        c.drawString(180, y, "User (Role)")
        c.drawString(350, y, "Action")
        c.drawString(500, y, "Details (File/Ack)")
        y -= 20
        c.line(30, y+15, 810, y+15)
        
        c.setFont("Helvetica", 9)
        
        for l in logs:
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica-Bold", 10)
                c.drawString(30, y, "Timestamp")
                c.drawString(180, y, "User (Role)")
                c.drawString(350, y, "Action")
                c.drawString(500, y, "Details (File/Ack)")
                y -= 20
                c.line(30, y+15, 810, y+15)
                c.setFont("Helvetica", 9)

            ts_ist = l.timestamp.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
            ts_str = ts_ist.strftime('%Y-%m-%d %H:%M:%S')
            u = l.username or ''
            r = l.role or ''
            a = l.action or ''
            f = l.filename or ''
            an = l.ack_no or ''
            
            details = f"{f} {an}".strip()
            user_role = f"{u} ({r})"
            if len(user_role) > 35: user_role = user_role[:32] + "..."

            c.drawString(30, y, ts_str)
            c.drawString(180, y, user_role)
            c.drawString(350, y, a)
            c.drawString(500, y, details)
            
            y -= 15
            
        c.save()
        buf.seek(0)
        
        fname = f"usage_logs_{start_of_day.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d')}.pdf"
        log_usage('download_logs')
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)
    except Exception as e:
        return f"Failed to generate logs: {e}", 500

@admin_bp.route('/delete_complaint/<int:complaint_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    db.session.delete(complaint)
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/delete_by_ack', methods=['POST'])
@login_required
@admin_required
def delete_by_ack():
    ack_no = request.form.get('ack_no', '').strip()
    if not ack_no:
        flash("Please provide an Acknowledgement Number.", "warning")
        return redirect(url_for('admin.admin_dashboard'))

    try:
        Transaction.query.filter_by(ack_no=ack_no).delete()
        Complaint.query.filter_by(ack_no=ack_no).delete()
        db.session.commit()
        flash(f"Successfully deleted records for ACK {ack_no}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting records: {e}", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/view_all_complaints')
@login_required
def view_all_complaints():
    log_usage('view_all_complaints')
    # Use defer to skip loading the large 'data' column
    complaints = UploadedFile.query.options(defer(UploadedFile.data)).order_by(UploadedFile.upload_time.desc()).all()

    upload_ack_rows = (
        db.session.query(Transaction.upload_id, Transaction.ack_no)
        .filter(Transaction.ack_no.isnot(None))
        .distinct()
        .all()
    )

    upload_id_to_acks = {}
    for uid, ack in upload_ack_rows:
        if not ack or not uid:
            continue
        upload_id_to_acks.setdefault(uid, set()).add(ack)

    for c in complaints:
        if c.upload_time:
            c.upload_time = c.upload_time.replace(tzinfo=timezone.utc).astimezone(
                timezone(timedelta(hours=5, minutes=30))
            )
        ack_set = upload_id_to_acks.get(c.id, set())
        c.ack_nos = sorted(list(ack_set)) if ack_set else []

    seen_acks = set()
    unique_complaints = []
    for c in complaints:
        ack_value = c.ack_nos[0] if c.ack_nos else None
        if ack_value and ack_value in seen_acks:
            continue
        if ack_value:
            seen_acks.add(ack_value)
        unique_complaints.append(c)

    return render_template("view_all_complaints.html", complaint_data=unique_complaints)
