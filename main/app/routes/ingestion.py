from flask import Blueprint, request, jsonify, flash, redirect, url_for, session, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import secrets
import pandas as pd
import io
import re
import logging

from ..extensions import db, limiter
from ..models import UploadedFile, Transaction, Complaint, POHRefundDetails
from ..utils.file_handling import file_lock, allowed_file
from ..utils.data_processing import (
    sanitize_cell, clean_bank_name, clean_amount, 
    validate_account_number, validate_amount
)
from ..utils.logging import log_usage

logger = logging.getLogger(__name__)

ingestion_bp = Blueprint('ingestion', __name__)

@ingestion_bp.route('/upload', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only .xlsx and .xls allowed'}), 400

    try:
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        # 50MB limit from config? app.py had 50MB but check size here
        if file_size > 50 * 1024 * 1024:
            return jsonify({'error': 'File too large. Maximum 50MB'}), 400

        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{secrets.token_hex(16)}.{ext}"
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to process file. Please check format.'}), 500

@ingestion_bp.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    if 'excel_file' not in request.files:
        flash("No file part", "warning")
        return redirect(url_for('main.index'))
        
    file = request.files['excel_file']
    if not file or not file.filename.endswith('.xlsx'):
        flash("Invalid file format. Please upload a .xlsx file.", "warning")
        return redirect(url_for('main.index'))

    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    with file_lock(file_path):
        existing_file = UploadedFile.query.filter_by(filename=filename).first()
        if existing_file:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError as e:
                logger.warning(f"Failed to delete old file {file_path}: {e}")
            
            Transaction.query.filter_by(upload_id=existing_file.id).delete()
            db.session.delete(existing_file)
            db.session.commit()

    file.save(file_path)

    try:
        xls = pd.ExcelFile(file_path, engine='openpyxl')
        
        def find_sheet_name(xls_obj, target):
            names = xls_obj.sheet_names or []
            if target in names: return target
            for n in names:
                if n and n.strip().lower() == target.strip().lower(): return n
            for n in names:
                if n and target.strip().lower() in n.strip().lower(): return n
            def simple(s): return re.sub(r'[^0-9a-z]+', '', str(s).lower())
            t_simple = simple(target)
            for n in names:
                if simple(n) == t_simple: return n
            return None

        sheet_name = find_sheet_name(xls, 'Money Transfer to')
        if not sheet_name:
            available = ", ".join([f"'{s}'" for s in (xls.sheet_names or [])])
            raise ValueError(f"Worksheet named 'Money Transfer to' not found. Available sheets: {available}")

        tx_df = pd.read_excel(xls, sheet_name=sheet_name)
        
        MAX_ROWS = 100000
        if len(tx_df) > MAX_ROWS:
            xls.close()
            if os.path.exists(file_path): os.remove(file_path)
            flash(f"File contains too many rows. Maximum {MAX_ROWS} rows allowed.", "error")
            return redirect(url_for('main.index'))

        for col in tx_df.columns:
            tx_df[col] = tx_df[col].apply(sanitize_cell)

        acknos_in_excel = tx_df['Acknowledgement No.'].dropna().unique()
        if len(acknos_in_excel) == 0:
            flash("⚠️ No Acknowledgement numbers found in the Excel file!", "warning")
            return redirect(url_for('main.index'))

        existing_acks = Transaction.query.filter(Transaction.ack_no.in_(acknos_in_excel)).all()
        if existing_acks:
            for record in existing_acks:
                db.session.delete(record)
            db.session.commit()
            flash("ℹ️ Existing ACK numbers found — old records replaced.", "info")

        # Re-read file to get binary data for storage
        with open(file_path, 'rb') as f:
            file_data = f.read()

        uploaded_file = UploadedFile(
            filename=filename,
            data=file_data,
            uploader=current_user.username,
            mimetype=file.mimetype
        )
        db.session.add(uploaded_file)
        db.session.commit()
        log_usage('upload_excel', filename=filename)

        atm_df = pd.read_excel(xls, sheet_name='Withdrawal through ATM') if 'Withdrawal through ATM' in xls.sheet_names else pd.DataFrame()
        chq_df = pd.read_excel(xls, sheet_name='Cash Withdrawal through Cheque') if 'Cash Withdrawal through Cheque' in xls.sheet_names else pd.DataFrame()
        hold_df = pd.read_excel(xls, sheet_name='Transaction put on hold') if 'Transaction put on hold' in xls.sheet_names else pd.DataFrame()

        if not atm_df.empty:
            for col in atm_df.columns: atm_df[col] = atm_df[col].apply(sanitize_cell)
        if not chq_df.empty:
            for col in chq_df.columns: chq_df[col] = chq_df[col].apply(sanitize_cell)
        if not hold_df.empty:
            for col in hold_df.columns: hold_df[col] = hold_df[col].apply(sanitize_cell)

        def normalize_columns(df):
            return [str(c).encode('ascii', 'ignore').decode().strip().replace('\u00A0', ' ').replace('\xa0', ' ') for c in df.columns]

        tx_df.columns = normalize_columns(tx_df)
        if not atm_df.empty: atm_df.columns = normalize_columns(atm_df)
        if not chq_df.empty: chq_df.columns = normalize_columns(chq_df)
        if not hold_df.empty: hold_df.columns = normalize_columns(hold_df)
        
        def clean_location(value):
            if pd.isna(value) or value is None: return None
            s = str(value).strip()
            prefixes = ["Place of ATM :-", "Place of ATM :", "Place/Location of ATM :", "Place/Location of ATM", "Place / Location of ATM", "Place of ATM", "Place/Location"]
            for p in prefixes:
                if s.lower().startswith(p.lower()):
                    s = s[len(p):].strip(" :-")
                    break
            return s or None

        def safe_txn_id(val):
            if pd.isna(val) or val is None: return ''
            s = str(val).strip()
            if re.fullmatch(r'\d+\.0', s): s = s[:-2]
            if re.fullmatch(r'\d+(\.\d+)?e\+\d+', s, flags=re.IGNORECASE):
                try:
                    num = pd.to_numeric(val, errors='coerce')
                    if pd.notna(num): s = f"{int(num):d}"
                except: pass
            return s

        def get_first_value(df, columns):
            if df.empty: return None
            for col in columns:
                if col in df.columns:
                    val = df.iloc[0].get(col)
                    if pd.notna(val) and str(val).strip(): return str(val).strip()
            return None
        
        def get_txn_id_from_row(row, utr2_col=None):
            if utr2_col and utr2_col in row.index:
                s = safe_txn_id(row.get(utr2_col, ''))
                if s: return s
            
            variants = ['Transaction ID / UTR Number2', 'Transaction Id / UTR Number2', 'Transaction ID/ UTR Number2', 'Transaction ID/UTR Number2', 'Transaction ID / UTR Number 2', 'Transaction Id / UTR Number 2', 'Txn ID / UTR Number2', 'Txn Id / UTR Number2', 'UTR Number2', 'Txn ID / UTR Number 2', 'Txn Id / UTR Number 2', 'Transaction ID/UTR Number 2', 'Txn ID/UTR Number2', 'Transaction ID / UTR', 'Transaction ID/UTR', 'Txn ID/UTR', 'Transaction ID / UTR Number', 'Txn ID / UTR Number', 'UTR Number', 'UTR']
            for col in variants:
                if col in row.index:
                    s = safe_txn_id(row.get(col, ''))
                    if s: return s
            
            def norm(s):
                s = str(s).replace('\u00a0', ' ')
                s = re.sub(r'[\s/_\-\.]+', ' ', s).lower().strip()
                return s
            
            for col in row.index:
                nc = norm(col)
                if 'utr' in nc and (('number 2' in nc) or ('number2' in nc) or nc.endswith(' 2')) and any(x in nc for x in ['transaction', 'txn', 'id']):
                    s = safe_txn_id(row.get(col, ''))
                    if s: return s
            
            for col in row.index:
                nc = norm(col)
                if 'utr' in nc and 'number' in nc:
                    s = safe_txn_id(row.get(col, ''))
                    if s: return s
            return ''
        
        def find_utr2_column(columns):
            exact_matches = ['Transaction ID / UTR Number2', 'Transaction Id / UTR Number2', 'Transaction ID/ UTR Number2', 'Transaction ID/UTR Number2', 'Transaction ID / UTR Number 2', 'Transaction Id / UTR Number 2', 'Txn ID / UTR Number2', 'Txn Id / UTR Number2', 'Txn ID / UTR Number 2', 'Txn Id / UTR Number 2', 'UTR Number2', 'Txn ID/UTR Number2', 'Transaction ID/UTR Number 2', 'Transaction ID / UTR', 'Transaction ID/UTR', 'Txn ID/UTR', 'Transaction ID / UTR Number']
            for col in columns:
                if col in exact_matches: return col
            
            def norm(s):
                s = str(s).replace('\u00a0', ' ')
                s = re.sub(r'[\s/_\-\.]+', ' ', s).lower().strip()
                return s
            
            known_normalized = ['transaction id utr number2', 'transaction id utr number 2', 'transaction id  utr number2', 'transaction id  utr number 2', 'transaction id number2', 'transaction id utr', 'txn id utr number2', 'txn id utr number 2', 'txn id utr', 'utr number2', 'utr number 2']
            normalized_map = {col: norm(col) for col in columns}
            for col, nc in normalized_map.items():
                if nc in known_normalized: return col
            
            for col, nc in normalized_map.items():
                if 'utr' in nc and (('number 2' in nc) or ('number2' in nc) or nc.endswith(' 2')) and any(x in nc for x in ['transaction', 'txn', 'id']):
                    return col
            
            for col, nc in normalized_map.items():
                if 'utr' in nc and 'number' in nc: return col
            return None

        utr2_col = find_utr2_column(tx_df.columns)
        transactions = []

        for idx, (_, row) in enumerate(tx_df.iterrows()):
            ack_no = str(row.get('Acknowledgement No.', '')).strip()
            if not ack_no: continue

            acc_to = str(row.get('Account No', '')).strip()
            atm_info = atm_df[atm_df['Account No./ (Wallet /PG/PA) Id'].astype(str).str.strip() == acc_to] if not atm_df.empty else pd.DataFrame()
            chq_info = chq_df[chq_df['Account No./ (Wallet /PG/PA) Id'].astype(str).str.strip() == acc_to] if not chq_df.empty else pd.DataFrame()
            hold_info = hold_df[hold_df['Account No./ (Wallet /PG/PA) Id'].astype(str).str.strip() == acc_to] if not hold_df.empty else pd.DataFrame()

            extracted_txn_id = get_txn_id_from_row(row, utr2_col)
            
            from_account = str(row.get('Account No./ (Wallet /PG/PA) Id', '')).strip()
            cleaned_amount = clean_amount(row.get('Transaction Amount'))

            if not validate_account_number(from_account): continue
            if not validate_account_number(acc_to): continue
            if not validate_amount(cleaned_amount): continue

            transaction = Transaction(
                layer=int(row.get('Layer', 0)),
                from_account=from_account,
                to_account=acc_to,
                account_number=acc_to,
                ack_no=ack_no,
                bank_name=clean_bank_name(row.get('Bank/FIs')),
                ifsc_code=str(row.get('Ifsc Code', '')).strip(),
                txn_date=str(row.get('Transaction Date', '')).strip(),
                txn_id=extracted_txn_id,
                amount=cleaned_amount,
                disputed_amount=clean_amount(row.get('Disputed Amount')),
                action_taken=str(row.get('Action Taken By bank', '')).strip(),
                atm_id=str(atm_info.iloc[0]['ATM ID']) if not atm_info.empty else None,
                atm_withdraw_amount=clean_amount(atm_info.iloc[0]['Withdrawal Amount']) if not atm_info.empty else None,
                atm_withdraw_date=str(atm_info.iloc[0]['Withdrawal Date & Time']) if not atm_info.empty else None,
                atm_location=clean_location(get_first_value(atm_info, ['ATM Location', 'Location', 'ATM Location / City', 'ATM Address', 'ATM Location/City', 'Place/Location of ATM', 'Place / Location of ATM'])),
                cheque_no=str(chq_info.iloc[0]['Cheque No']) if not chq_info.empty else None,
                cheque_withdraw_amount=clean_amount(chq_info.iloc[0]['Withdrawal Amount']) if not chq_info.empty else None,
                cheque_withdraw_date=str(chq_info.iloc[0]['Withdrawal Date & Time']) if not chq_info.empty else None,
                cheque_ifsc=str(chq_info.iloc[0]['Ifsc Code']) if not chq_info.empty else None,
                put_on_hold_txn_id=str(hold_info.iloc[0]['Transaction Id / UTR Number']) if not hold_info.empty else None,
                put_on_hold_date=str(hold_info.iloc[0]['Put on hold Date']) if not hold_info.empty else None,
                put_on_hold_amount=clean_amount(hold_info.iloc[0]['Put on hold Amount']) if not hold_info.empty else None,
                upload_id=uploaded_file.id
            )

            if transaction.put_on_hold_txn_id:
                poh_details = POHRefundDetails.query.filter_by(ack_no=transaction.ack_no, txn_id=transaction.put_on_hold_txn_id).first()
                if poh_details:
                    transaction.court_order_date = poh_details.court_order_date
                    transaction.refund_status = poh_details.refund_status
                    transaction.refund_amount = poh_details.refund_amount

            transactions.append(transaction)

        transactions.sort(key=lambda t: t.layer)
        for t in transactions: db.session.add(t)
        db.session.commit()
        flash("✅ Excel uploaded and data saved successfully.", "success")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to process Excel: {e}", exc_info=True)
        flash("Failed to process Excel file. Please check the file format and try again.", "danger")

    return redirect(url_for('main.index'))

@ingestion_bp.route('/download/<filename>')
@login_required
def download_file(filename):
    safe_filename = secure_filename(filename)
    uploaded_file = UploadedFile.query.filter_by(filename=safe_filename).first()
    if not uploaded_file: abort(404)

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_filename)
    upload_dir = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    requested_path = os.path.abspath(file_path)

    if not requested_path.startswith(upload_dir): abort(403)
    if not os.path.isfile(requested_path): abort(404)

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], safe_filename)
