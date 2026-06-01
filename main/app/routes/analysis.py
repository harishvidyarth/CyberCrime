from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, distinct
import logging
import json
import io
import os
import pandas as pd
from collections import defaultdict
import concurrent.futures

from ..extensions import db
from ..models import User, Transaction, UploadedFile, Complaint, POHRefundDetails, KYCDetails
from ..utils.security import check_case_access
from ..utils.logging import log_usage
from ..utils.data_processing import (
    format_indian_currency, get_state_from_api, 
    load_ifsc_cache, save_ifsc_cache, ordinal
)

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/view_graph')
@login_required
def view_graph():
    ack_no = request.args.get('ack_no')
    check_case_access(ack_no)
    try:
        fname_row = db.session.query(UploadedFile.filename).join(Transaction, Transaction.upload_id == UploadedFile.id).filter(Transaction.ack_no == ack_no).order_by(UploadedFile.upload_time.desc()).first()
        fname = fname_row[0] if fname_row else None
        log_usage('view_graph', filename=fname, ack_no=ack_no)
    except Exception as e:
        logger.error(f"UsageLog view_graph error: {e}")
    return redirect(url_for('analysis.graph_tree1', ack_no=ack_no))

@analysis_bp.route('/graph/<ack_no>')
@login_required
def graph_tree1(ack_no):
    check_case_access(ack_no)
    try:
        fname_row = db.session.query(UploadedFile.filename).join(Transaction, Transaction.upload_id == UploadedFile.id).filter(Transaction.ack_no == ack_no).order_by(UploadedFile.upload_time.desc()).first()
        fname = fname_row[0] if fname_row else None
        log_usage('graph_page', filename=fname, ack_no=ack_no)
    except Exception as e:
        logger.error(f"UsageLog graph_page error: {e}")

    layer_1_total = 0.0
    formatted_l1_total = "0.00"
    try:
        l1_txns = Transaction.query.filter_by(ack_no=ack_no, layer=1).all()
        if l1_txns:
            layer_1_total = sum(t.amount for t in l1_txns if t.amount)
        formatted_l1_total = format_indian_currency(layer_1_total)
    except Exception as e:
        logger.error(f"Error calculating layer 1 total: {e}")

    return render_template('graph_tree1.html', ack_no=ack_no, role=session.get('role'), layer_1_total=formatted_l1_total)

@analysis_bp.route('/graph_data/<ack_no>')
@login_required
def graph_data(ack_no):
    check_case_access(ack_no)
    try:
        ack_no = ack_no.strip()
        transactions = Transaction.query.filter_by(ack_no=ack_no).all()

        try:
            poh_details_list = POHRefundDetails.query.filter_by(ack_no=ack_no).all()
            if poh_details_list:
                poh_map = {p.txn_id: p for p in poh_details_list}
                for t in transactions:
                    if t.put_on_hold_txn_id and t.put_on_hold_txn_id in poh_map:
                        pdata = poh_map[t.put_on_hold_txn_id]
                        t.court_order_date = pdata.court_order_date
                        t.refund_status = pdata.refund_status
                        t.refund_amount = pdata.refund_amount
        except Exception as e:
            logger.error(f"Error restoring POH details in graph_data: {e}")

        try:
            txn_ids = [t.txn_id for t in transactions if t.txn_id]
            if txn_ids:
                kyc_list = KYCDetails.query.filter(KYCDetails.txn_id.in_(txn_ids)).all()
                kyc_map = {k.txn_id: k for k in kyc_list}
                for t in transactions:
                    if t.txn_id and t.txn_id in kyc_map:
                        kdata = kyc_map[t.txn_id]
                        t.kyc_name = kdata.name
                        t.kyc_aadhar = kdata.aadhar
                        t.kyc_mobile = kdata.mobile
                        t.kyc_address = kdata.address
        except Exception as e:
            logger.error(f"Error restoring KYC details in graph_data: {e}")

        if not transactions:
            return jsonify({'error': 'No transactions found for this Acknowledgement No.'})

        from_to_map = defaultdict(lambda: defaultdict(list))
        for t in transactions:
            from_to_map[t.from_account][t.to_account].append({
                'txn_id': t.txn_id,
                'amount': t.amount,
                'date': t.txn_date,
                'ack_no': t.ack_no
            })

        from_layer_map = {t.from_account: t.layer for t in transactions if t.from_account}

        def build_hierarchy(rows):
            root = {'name': 'Flow', 'children': []}
            def find_node(n, target):
                if n['name'] == target: return n
                for c in n.get('children', []):
                    found = find_node(c, target)
                    if found: return found
                return None

            for t in rows:
                if t.layer == 1:
                    parent = next((c for c in root['children'] if c['name'] == t.from_account), None)
                    if not parent:
                        parent = {'name': t.from_account, 'children': [], 'kyc_name': t.kyc_name, 'kyc_aadhar': t.kyc_aadhar, 'kyc_mobile': t.kyc_mobile, 'kyc_address': t.kyc_address, 'action': t.action_taken}
                        root['children'].append(parent)
                else:
                    parent = find_node(root, t.from_account)

                if parent:
                    existing = next((c for c in parent['children'] if c['name'] == t.to_account), None)
                    if not existing:
                        child = {
                            'name': t.to_account, 'children': [], 'layer': from_layer_map.get(t.to_account, t.layer), 'ack': t.ack_no, 'bank': t.bank_name, 'ifsc': t.ifsc_code, 'date': t.txn_date,
                            'txid': (t.txn_id or next((tx.get('txn_id') for tx in from_to_map[t.from_account][t.to_account] if tx.get('txn_id')), None)),
                            'amt': str(t.amount), 'disputed': str(t.disputed_amount), 'action': t.action_taken, 'state': t.state if t.state and t.state != 'Unknown' else (t.ifsc_code or 'Unknown State'),
                            'atm_info': {'atm_id': t.atm_id, 'amount': t.atm_withdraw_amount, 'date': t.atm_withdraw_date, 'location': t.atm_location} if t.atm_id else None,
                            'cheque_info': {'cheque_no': t.cheque_no, 'amount': t.cheque_withdraw_amount, 'date': t.cheque_withdraw_date, 'ifsc': t.cheque_ifsc} if t.cheque_no else None,
                            'hold_info': {'txn_id': t.put_on_hold_txn_id, 'amount': t.put_on_hold_amount, 'date': t.put_on_hold_date, 'court_order_date': t.court_order_date, 'refund_status': t.refund_status, 'refund_amount': t.refund_amount} if t.put_on_hold_txn_id else None,
                            'kyc_name': t.kyc_name, 'kyc_aadhar': t.kyc_aadhar, 'kyc_mobile': t.kyc_mobile, 'kyc_address': t.kyc_address, 'transactions_from_parent': from_to_map[t.from_account][t.to_account]
                        }
                        parent['children'].append(child)
            return root

        return jsonify(build_hierarchy(transactions))
    except Exception as e:
        logger.error(f"Error processing graph data for ACK {ack_no}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error while processing graph data.'}), 500

@analysis_bp.route('/available_ack_nos')
@login_required
def available_ack_nos():
    if current_user.role in ['Admin', 'Viewer']:
        ack_nos = db.session.query(Transaction.ack_no).distinct().all()
    else:
        complaints = Complaint.query.filter(or_(Complaint.assigned_to == current_user.id, Complaint.uploaded_by == current_user.id)).with_entities(Complaint.ack_no).all()
        user_ack_nos = [c.ack_no for c in complaints]
        if not user_ack_nos: return jsonify({'available_ack_nos': []})
        ack_nos = db.session.query(Transaction.ack_no).filter(Transaction.ack_no.in_(user_ack_nos)).distinct().all()
    return jsonify({'available_ack_nos': sorted([ack[0] for ack in ack_nos if ack[0]])})

@analysis_bp.route('/atm_data/<ack_no>')
@login_required
def atm_data(ack_no):
    check_case_access(ack_no)
    try:
        up = db.session.query(UploadedFile).join(Transaction, Transaction.upload_id == UploadedFile.id).filter(Transaction.ack_no == ack_no).order_by(UploadedFile.upload_time.desc()).first()
        if not up or not up.data: return jsonify({'atm': []})

        xls = pd.ExcelFile(io.BytesIO(up.data))
        sheet_name = next((s for s in xls.sheet_names if 'withdrawal' in s.lower() and 'atm' in s.lower()), None)
        if not sheet_name: return jsonify({'atm': []})

        df = pd.read_excel(xls, sheet_name=sheet_name)
        df.columns = [str(c).encode('ascii', 'ignore').decode().strip().replace('\xa0', ' ') for c in df.columns]
        
        layer_map = {str(acc).strip(): lay for acc, lay in db.session.query(Transaction.to_account, Transaction.layer).filter(Transaction.ack_no == ack_no).distinct().all() if acc}
        
        acc_col = next((col for col in df.columns if 'account no' in col.lower() or 'account number' in col.lower()), None)
        if acc_col:
            def get_layer(row):
                val = str(row.get(acc_col)).strip()
                if val in layer_map: return layer_map[val]
                if val.endswith('.0') and val[:-2] in layer_map: return layer_map[val[:-2]]
                try:
                    iv = str(int(float(val)))
                    if iv in layer_map: return layer_map[iv]
                except: pass
                return ''
            df['Layer'] = df.apply(get_layer, axis=1)
        
        return jsonify({'atm': df.fillna('').to_dict(orient='records'), 'columns': list(df.columns)})
    except Exception as e:
        logger.error(f"[atm_data] Error: {e}", exc_info=True)
        return jsonify({'atm': [], 'error': str(e)})

@analysis_bp.route('/statewise_summary/<ack_no>')
@login_required
def statewise_summary(ack_no):
    check_case_access(ack_no)
    try:
        known_count = db.session.query(Transaction).filter(Transaction.ack_no == ack_no, Transaction.state.isnot(None), Transaction.state != 'Unknown').count()
        if known_count == 0:
            txns_un = Transaction.query.filter(Transaction.ack_no == ack_no, (Transaction.state.is_(None) | (Transaction.state == 'Unknown')), Transaction.ifsc_code.isnot(None)).all()
            if txns_un:
                ifscs = {t.ifsc_code for t in txns_un}
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                    res = {f: ex.submit(get_state_from_api, f) for f in ifscs}
                    ifsc_map = {f: r.result() for f, r in res.items()}
                save_ifsc_cache()
                for t in txns_un:
                    if t.ifsc_code in ifsc_map: t.state = ifsc_map[t.ifsc_code].title()
                db.session.commit()

        summaries = db.session.query(Transaction.state, func.count(Transaction.id), func.sum(Transaction.amount), func.group_concat(distinct(Transaction.ifsc_code))).filter(Transaction.ack_no == ack_no, Transaction.state.isnot(None), Transaction.state != 'Unknown').group_by(Transaction.state).all()
        
        regions = {
            'Southern': ['Tamil Nadu', 'Kerala', 'Karnataka', 'Andhra Pradesh', 'Telangana', 'Puducherry', 'Lakshadweep', 'Andaman and Nicobar Islands'],
            'Western': ['Maharashtra', 'Gujarat', 'Rajasthan', 'Goa', 'Daman and Diu', 'Dadra and Nagar Haveli'],
            'Eastern': ['West Bengal', 'Odisha', 'Bihar', 'Jharkhand', 'Assam', 'Arunachal Pradesh', 'Nagaland', 'Manipur', 'Mizoram', 'Tripura', 'Meghalaya', 'Sikkim'],
            'Northern': ['Jammu and Kashmir', 'Himachal Pradesh', 'Punjab', 'Chandigarh', 'Uttarakhand', 'Haryana', 'Delhi', 'Uttar Pradesh', 'Madhya Pradesh', 'Chhattisgarh', 'Ladakh']
        }
        
        res_list = []
        for s, tc, ta, ic in summaries:
            res_list.append({'state': s.title(), 'total_transactions': tc, 'total_amount': float(ta or 0), 'ifsc_codes': sorted(ic.split(',')) if ic else []})

        reg_map = {r: [] for r in regions}; others = []
        for item in res_list:
            found = False
            for r, states in regions.items():
                if item['state'] in states: reg_map[r].append(item); found = True; break
            if not found: others.append(item)

        s_order = regions['Southern']
        reg_map['Southern'].sort(key=lambda x: (s_order.index(x['state']) if x['state'] in s_order else 99, -x['total_amount']))
        for r in ['Western', 'Eastern', 'Northern']: reg_map[r].sort(key=lambda x: x['total_amount'], reverse=True)

        return jsonify(reg_map['Southern'] + reg_map['Western'] + reg_map['Eastern'] + reg_map['Northern'] + others)
    except Exception as e:
        logger.error(f"Error in statewise_summary for {ack_no}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@analysis_bp.route('/put_on_hold_transactions/<ack_no>')
@login_required
def put_on_hold_transactions(ack_no):
    check_case_access(ack_no)
    try:
        from ifsc_utils import get_ifsc_info
        hold_txns = Transaction.query.filter(Transaction.ack_no == ack_no.strip(), Transaction.put_on_hold_txn_id.isnot(None)).all()
        poh_map = {p.txn_id: p for p in POHRefundDetails.query.filter_by(ack_no=ack_no.strip()).all()}
        
        response = []
        for t in hold_txns:
            ifsc_data = get_ifsc_info(t.ifsc_code) or {}
            pdata = poh_map.get(t.put_on_hold_txn_id)
            response.append({
                'account_number': t.account_number or t.to_account, 'bank_name': t.bank_name, 'branch_name': ifsc_data.get('BRANCH', 'Unknown'), 'ifsc_code': t.ifsc_code, 'amount': t.put_on_hold_amount, 'layer': t.layer,
                'court_order_date': pdata.court_order_date if pdata else t.court_order_date, 'refund_status': pdata.refund_status if pdata else t.refund_status, 'refund_amount': pdata.refund_amount if pdata else t.refund_amount
            })
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error fetching hold transactions for {ack_no}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@analysis_bp.route('/state_transactions/<ack_no>/<state>')
@login_required
def state_transactions(ack_no, state):
    check_case_access(ack_no)
    page = int(request.args.get('page', 1)); per_page = int(request.args.get('per_page', 50))
    state_l = state.strip().lower()
    q = Transaction.query.filter(Transaction.ack_no == ack_no, db.func.lower(db.func.trim(Transaction.state)) == state_l)
    total = q.count()
    txns = q.order_by(Transaction.atm_id.isnot(None).desc()).offset((page-1)*per_page).limit(per_page).all()
    
    res = []
    for t in txns:
        if t.atm_id: tp, am, tid = 'ATM Withdrawal', t.atm_withdraw_amount, 'N/A'
        elif t.cheque_no: tp, am, tid = 'Cheque Withdrawal', t.cheque_withdraw_amount, 'N/A'
        elif t.put_on_hold_txn_id: tp, am, tid = 'Put on Hold', t.put_on_hold_amount, 'N/A'
        else: tp, am, tid = 'Account Transfer', str(t.amount), t.txn_id
        res.append({'ack_no': t.ack_no, 'account_name': t.account_number, 'bank_name': t.bank_name, 'amount': am, 'ifsc_code': t.ifsc_code, 'date': t.txn_date or 'N/A', 'transaction_type': tp, 'transaction_id': tid, 'layer': t.layer or 'N/A', 'is_atm': t.atm_id is not None})
    
    return jsonify({'transactions': res, 'total_count': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page})

@analysis_bp.route('/save_kyc', methods=['POST'])
@login_required
def save_kyc():
    if session.get('role') == 'Viewer': return jsonify({"status": "error", "message": "View-only users cannot edit KYC"}), 403
    data = request.get_json(); txn_id = data.get('txn_id')
    if not txn_id: return jsonify({"status": "error", "message": "Transaction ID missing"}), 400
    try:
        kyc = KYCDetails.query.filter_by(txn_id=txn_id).first()
        if not kyc: kyc = KYCDetails(txn_id=txn_id); db.session.add(kyc)
        kyc.name, kyc.aadhar, kyc.mobile, kyc.address = data.get('name'), data.get('aadhar'), data.get('mobile'), data.get('address')
        txn = Transaction.query.filter_by(txn_id=txn_id).first()
        if txn: txn.kyc_name, txn.kyc_aadhar, txn.kyc_mobile, txn.kyc_address = kyc.name, kyc.aadhar, kyc.mobile, kyc.address
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback(); return jsonify({"status": "error", "message": str(e)}), 500

@analysis_bp.route('/save_hold_refund', methods=['POST'])
@login_required
def save_hold_refund():
    if session.get('role') == 'Viewer': return jsonify({"status": "error", "message": "View-only users cannot edit refund details"}), 403
    data = request.get_json() or {}; ack_no = (data.get('ack_no') or '').strip(); hold_id = (data.get('hold_txn_id') or '').strip()
    if not ack_no or not hold_id: return jsonify({"status": "error", "message": "Missing required identifiers"}), 400
    txn = Transaction.query.filter_by(ack_no=ack_no, put_on_hold_txn_id=hold_id).first()
    if not txn: return jsonify({"status": "error", "message": "Put-on-hold transaction not found"}), 404
    try:
        txn.court_order_date, txn.refund_status = (data.get('court_order_date') or '').strip() or None, (data.get('refund_status') or '').strip() or None
        ra = data.get('refund_amount'); txn.refund_amount = float(ra) if ra not in (None, '') else None
        poh = POHRefundDetails.query.filter_by(ack_no=ack_no, txn_id=hold_id).first()
        if not poh: poh = POHRefundDetails(ack_no=ack_no, txn_id=hold_id); db.session.add(poh)
        poh.court_order_date, poh.refund_status, poh.refund_amount = txn.court_order_date, txn.refund_status, txn.refund_amount
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback(); return jsonify({"status": "error", "message": str(e)}), 500

@analysis_bp.route('/ifsc_info/<ifsc>')
@login_required
def ifsc_info(ifsc):
    try:
        from ifsc_utils import get_ifsc_info
        return jsonify(get_ifsc_info(ifsc) or {})
    except Exception as e:
        logger.error(f"Error returning IFSC info for {ifsc}: {e}")
        return jsonify({}), 500
