from app import app, db, Transaction, get_layer_1_total, format_indian_currency
import unittest

class TestLayer1Total(unittest.TestCase):
    def setUp(self):
        import os
        if os.environ.get('FLASK_ENV') == 'testing':
            app.config['TESTING'] = True
            app.config['WTF_CSRF_ENABLED'] = False
        else:
            app.config['TESTING'] = False
            app.config['WTF_CSRF_ENABLED'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def test_calculation(self):
        with app.app_context():
            ack = "TEST_L1_TOTAL"
            # Create transactions
            # Layer 1
            t1 = Transaction(ack_no=ack, layer=1, amount=100000.0, to_account="A1", txn_id="T1")
            t2 = Transaction(ack_no=ack, layer=1, amount=2200000.0, to_account="A2", txn_id="T2")
            # Layer 2 (should be ignored)
            t3 = Transaction(ack_no=ack, layer=2, amount=50000.0, to_account="A3", txn_id="T3")
            
            db.session.add_all([t1, t2, t3])
            db.session.commit()
            
            total = get_layer_1_total(ack)
            print(f"Calculated Total: {total}")
            self.assertEqual(total, 2300000.0)
            
            formatted = format_indian_currency(total)
            print(f"Formatted: {formatted}")
            self.assertEqual(formatted, "₹23,00,000")

if __name__ == '__main__':
    unittest.main()
