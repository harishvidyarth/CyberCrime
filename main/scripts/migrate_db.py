from flask import Flask
from flask_migrate import Migrate
from models import db
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'fundtrail_db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    from alembic.config import Config
    from alembic import command
    config = Config('migrations/alembic.ini')
    config.set_main_option('script_location', 'migrations')
    command.upgrade(config, 'head')
    print("Database migration completed successfully")
