import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import bcrypt
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'parking_app'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'instance', 'parking.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#=============================================================== Database Setup ==============================================================
db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    reservations = db.relationship('Reservation', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    number_of_spots = db.Column(db.Integer, nullable=False)
    spots = db.relationship('ParkingSpot', backref='parking_lot', lazy=True, cascade="all, delete-orphan")
    status = db.Column(db.String(20), nullable=False, default='Available')

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=1)
    current_occupancy = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='Available')
    reservations = db.relationship('Reservation', backref='parking_spot', lazy=True)

    def is_available(self):
        return self.current_occupancy <= self.capacity

    def __repr__(self):
        return f'<ParkingSpot {self.id} in Lot {self.lot_id}>'

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=True)
    parking_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime, nullable=True)
    parking_cost = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<Reservation {self.id} for Spot {self.spot_id} by User {self.user_id}>'

#============================================================== Create Admin User ==============================================================
with app.app_context():
    db.create_all()
    
    existing_admin = User.query.filter_by(username='admin').first()
    if not existing_admin:
        admin_password = 'admin'
        encrypted_admin_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
        
        default_admin = User(username='admin', password=encrypted_admin_password.decode('utf-8'), email='admin@example.com', is_admin=True )
        
        db.session.add(default_admin)
        db.session.commit()
        print("Created default admin user (username: admin, password: admin)")

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('index.html')

#<------------------------------------------------------------ USER REGISTER --------------------------------------------------------->
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'GET':
        return render_template('register.html')
    
    new_username = request.form['username']
    new_password = request.form['password']
    new_email = request.form['email']
    user_phone = request.form.get('phone')
    user_address = request.form.get('address')

    duplicate_user = User.query.filter( (User.username == new_username) | (User.email == new_email)).first()
    if duplicate_user:
        flash('Username or email already exists.', 'danger')
        return redirect(url_for('register'))

    encrypted_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    password_string = encrypted_password.decode('utf-8')

    user_account = User( username=new_username, password=password_string, email=new_email, phone=user_phone, address=user_address, is_admin=False)
    
    db.session.add(user_account)
    db.session.commit()
    flash('Registration successful! Please login.', 'success')
    return redirect(url_for('login'))

#<------------------------------------------------------------ USER AND ADMIN LOGIN --------------------------------------------------------->
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'GET':
        return render_template('login.html')
    
    entered_username = request.form['username']
    entered_password = request.form['password']

    found_user = User.query.filter_by(username=entered_username).first()

    if found_user:
        password_matches = bcrypt.checkpw( entered_password.encode('utf-8'), found_user.password.encode('utf-8'))
        
        if password_matches:
            session['user_id'] = found_user.id
            session['username'] = found_user.username
            session['is_admin'] = found_user.is_admin
            
            flash('Login successful!', 'success')
            
            if found_user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
    else:
        flash('Invalid username or password.', 'danger')
        return redirect(url_for('login'))

#<------------------------------------------------------------ USER AND ADMIN LOGOUT --------------------------------------------------------->
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)