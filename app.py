import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from functools import wraps
import bcrypt
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'parking_app'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'instance', 'parking.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)

# Note: I copied the decorator pattern from the flask docs but tweaked it!
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20)) # Optional
    address = db.Column(db.String(200)) # Optional
    is_admin = db.Column(db.Boolean, default=False) 

    reservations = db.relationship('Reservation', backref='user', lazy=True, cascade = "all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    __tablename__ = 'parking_lot'
    id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    number_of_spots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Available')
    
    spots = db.relationship('ParkingSpot', backref='parking_lot', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    
class ParkingSpot(db.Model):
    __tablename__ = 'parking_spot'
    id = db.Column(db.Integer, primary_key=True)
    spot_number = db.Column(db.Integer, nullable=False)
    occupied = db.Column(db.Integer, nullable=False, default=0)
    capacity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default='Available')

    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id', ondelete='CASCADE'), nullable=False)
    reservations = db.relationship('Reservation', backref='parking_spot', lazy=True, cascade = "all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f'<ParkingSpot- {self.id} in Lot- {self.lot_id}>'

class Reservation(db.Model):
    __tablename__ = 'reservation'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(20), nullable=True)
    parking_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    leaving_time = db.Column(db.DateTime, nullable=True)
    parking_cost = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return f'<Reservation- {self.id} for Spot- {self.spot_id} by User- {self.user_id}>'


with app.app_context():
    db.create_all()
    #check if the default admin user already exists(bcz i keep forgeting)
    existing_admin = User.query.filter_by(username='admin').first()
    if not existing_admin:
        admin_password = 'admin'
        encrypted_admin_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
        
        admin_credentials = User(username='admin', password=encrypted_admin_password.decode('utf-8'), email='admin@example.com', is_admin=True )
        
        db.session.add(admin_credentials)
        db.session.commit()
        print("Created default admin user (username: admin, password: admin)")

@app.template_filter('currency')
def format_as_currency(amount):
    # format the amount as currency (e.g., ₹123.45) in Indian Rupees
    if amount is None:
        return "₹0.00"
    return f"₹{amount:.2f}"

@app.template_filter('calculate_current_cost')
def calculate_current_cost(start_time, hourly_rate):
    """Calculates the current parking cost when the vehicle is still parked 
       (i.e., leaving time is None). Rounds up to the next hour."""
    if not start_time or hourly_rate is None:
        return 0.0
    duration = datetime.now() - start_time
    hours_parked = duration.total_seconds() / 3600
    
    billing = int(hours_parked) + (1 if hours_parked % 1 > 0 else 0) # Round up to next hour
    return max(billing * hourly_rate, hourly_rate) 

def calculate_final_cost(start_time, end_time, hourly_rate):
    '''calculating the final cost of the parking session based on the start and end time and the hourly rate'''

    if not start_time or not end_time or hourly_rate is None:
        return 0.0
    duration = end_time - start_time
    hours_parked = duration.total_seconds() / 3600
    billing = int(hours_parked) + (1 if hours_parked % 1 > 0 else 0) 
    return max(billing * hourly_rate, hourly_rate) 

@app.template_filter('calculate_duration')
def calculate_duration(start_time, end_time):
    '''calculating the duration of the parking session in hours and minutes based on the start and the end time'''

    if not start_time or not end_time:
        return "N/A"
    
    duration = end_time - start_time
    seconds = duration.total_seconds()
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    phone = request.form.get('phone')
    address = request.form.get('address')

    existing = User.query.filter( (User.username == username) | (User.email == email)).first()
    if existing:
        flash('OOPS! Username or email already exists.', 'danger')
        return redirect(url_for('register'))

    encrypted_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    password_string = encrypted_password.decode('utf-8')

    user_account = User( username=username, password=password_string, email=email, phone=phone, address=address, is_admin=False)

    db.session.add(user_account)
    db.session.commit()
    flash('Registration successful! Please login.', 'success')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'GET':
        return render_template('login.html')
    # POST request
    username = request.form.get('username','').strip()
    password = request.form.get('password','')

    if not username or not password:
        flash('Please enter both username and password.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):

        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
            
        flash('Login successful, welcome back!', 'success')
        return redirect(url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard'))
    #login failed 
    flash('OOPS! Invalid username or password. Try again!', 'danger')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

#<------------------------------------------------------------------------------------- ADMIN ROUTES --------------------------------------------------------->
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    
    lots = ParkingLot.query.order_by(ParkingLot.id.asc()).all()
    
    #calculating the availablity of each parking lot by counting the available spots of each lot and storing it in dictionary!
    avaialble = {}
    for lot in lots:
        available_count = ParkingSpot.query.filter_by( lot_id=lot.id, status='A').count()
        avaialble[lot.id] = available_count

    total_spots = ParkingSpot.query.count()
    busy_spots = ParkingSpot.query.filter_by(status='O').count()
    free_spots = ParkingSpot.query.filter_by(status='A').count()
    
    return render_template('admin_dashboard.html',
                            parking_lots=lots,
                            lot_availability=avaialble,
                            total_lots=len(lots),
                            total_spots=total_spots,
                            occupied_spots=busy_spots,
                            available_spots=free_spots )

@app.route('/admin/lots/add', methods=['GET', 'POST'])
@admin_required
def add_lot():
    if request.method == 'GET':
        return render_template('parking_lot_form.html', lot=None)
    # POST request
    name = request.form['location_name']
    address = request.form['address']
    pin = request.form['pin_code']
    price = float(request.form['price'])
    spots = int(request.form['number_of_spots'])

    #checking total spots and price are positive or not ?
    if spots <= 0 or price < 0:
        flash('Number of spots and price must be positive.', 'warning')
        return render_template('parking_lot_form.html', lot=None)

    #if yes, then create a new parking lot
    new_lot = ParkingLot( location_name=name,
                            address=address,
                            pin_code=pin, 
                            price=price, 
                            number_of_spots=spots,
                            status = 'Active' )
    db.session.add(new_lot)
    db.session.flush()

    # Now creating parking spots
    for num in range(1, spots + 1):
        spot = ParkingSpot(lot_id=new_lot.id,
                            spot_number=num,
                            capacity=1,
                            status='A',
                            occupied = 0)
        db.session.add(spot)
    #if everything is fine, commit the changes!
    db.session.commit()
    flash(f'Parking lot "{name}" and its {spots} spots created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/lots/edit/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def edit_lot(lot_id):
    
    lot = ParkingLot.query.get_or_404(lot_id) # get the lot first

    if request.method == 'GET':
        return render_template('parking_lot_form.html', lot=lot)
    # POST request
    name = request.form['location_name']
    address = request.form['address']
    pin = request.form['pin_code']
    new_price = float(request.form['price'])
    new_count = int(request.form['number_of_spots'])
    # checking if the new price and spot count are valid or not ?
    if new_price < 0:
        flash('OOPS! Price cannot be negative', 'warning')
        return render_template('parking_lot_form.html', lot=lot)
    if new_count < 1:
        flash('OOPS! You need at least 1 parking spot', 'warning')
        return render_template('parking_lot_form.html', lot=lot)
    #if yes, then update the lot
    lot.location_name = name
    lot.address = address
    lot.pin_code = pin
    lot.price = new_price

    current_spots = ParkingSpot.query.filter_by(lot_id=lot_id).count()

    ''' now we have to update the number of spots in the lot - there are three cases here:
    1. if the new spot count is same as the current spot count, then update the lot and then commit it !
    2. if the new spot count is greater than the current spot count, then add the new spots and update the lot and then commit it !
    3. if the new spot count is less than the current spot count, then remove the extra spots and update the lot and then commit it !'''
    
    #handling case 1:
    if new_count == current_spots:
        db.session.commit()
        flash(f'Updated "{lot.location_name}" successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    #handling case 2 :
    elif new_count > current_spots:
        add_spot = new_count - current_spots
        
        for i in range(add_spot):
            next_spot_num = current_spots + i + 1
            new_spot = ParkingSpot( lot_id=lot_id,
                                    spot_number=next_spot_num, 
                                    capacity=1,
                                    status='A' ,
                                    occupied = 0 )
            db.session.add(new_spot)
        lot.number_of_spots = new_count
        db.session.commit()
        flash(f'Added {add_spot} new spots!', 'success')
        return redirect(url_for('admin_dashboard'))

    #handling case 3 :
    else:
        remove_spot = current_spots - new_count
        busy_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()

        if new_count < busy_spot:
            flash(f"Can't do that! {busy_spot} people are currently parked, but you want only {new_count} spots. Increase that for no error! ", 'danger')
            return render_template('parking_lot_form.html', lot=lot)
        
        delete_spot = ParkingSpot.query.filter( ParkingSpot.lot_id == lot_id, 
                                               ParkingSpot.spot_number > new_count ).all()
        for spot in delete_spot:
            db.session.delete(spot)
        lot.number_of_spots = new_count
        db.session.commit()
        flash(f'Removed {remove_spot} spots successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/lots/delete/<int:lot_id>', methods=['POST'])
@admin_required
def delete_lot(lot_id):
    '''deleting a lot means deleting all the spots too from that lot and then deleting the lot itself 
    but if there are occupied spots in the lot, then we can't delete it !'''

    lot = ParkingLot.query.get_or_404(lot_id)
    busy = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()

    # we can't delete a lot if it has occupied spots!
    if busy > 0:
        flash(f'Sorry , You Cannot delete lot "{lot.location_name}" because it has occupied spots.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    lot_name = lot.location_name # save it for flash message
    db.session.delete(lot)
    db.session.commit()
    flash(f'YOOH! Parking lot "{lot_name}" deleted successfully!', 'success') 
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_view_users():
    
    users = User.query.filter_by(is_admin=False).order_by(User.id.asc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/view/<int:user_id>')
@admin_required
def admin_view_user(user_id):

    user = User.query.get_or_404(user_id)

    # get all the reservations of the user
    history = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_time.desc()).all()
    money_spent = 0
    for reservation in history: 
        if reservation.parking_cost:
            money_spent += reservation.parking_cost
    
    if history:
        avg_cost = money_spent / len(history)
    else:
        avg_cost = 0

    completed = [reservation for reservation in history if reservation.leaving_time]

    # if the user has finished sessions then calculate the avg parking time if not then return not avaible
    if completed:
        total_parking_time = 0
        for reservation in completed:
            session_duration = reservation.leaving_time - reservation.parking_time
            total_parking_time += session_duration.total_seconds()
        
        avg_sec = total_parking_time / len(completed)
        hours = int(avg_sec // 3600)
        minutes = int((avg_sec % 3600) // 60)
        avg_duration = f'{hours}h {minutes}m'
    else:
        avg_duration = 'N/A'
    
    return render_template('admin_view_user.html',
                            user=user,
                            parking_history=history,
                            total_cost=money_spent,
                            avg_cost=avg_cost,
                            avg_duration=avg_duration )

@app.route('/admin/add_user', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    if request.method == 'GET':
        return render_template('admin_add_user.html')
    # POST request
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    phone = request.form.get('phone', '')
    address = request.form.get('address', '')
    
    user_exist = User.query.filter((User.username == username) | (User.email == email)).first() 
    # checking if the username or email already exists or not ?
    if user_exist:
        flash('OOPS! Username or email already exists.', 'danger')
        return render_template('admin_add_user.html')

    # if not then create a new user and commit it!
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user = User( username=username,
                password=hashed.decode('utf-8'), 
                email=email, phone=phone, 
                address=address,
                is_admin=False)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{username}" created successfully!', 'success')
    return redirect(url_for('admin_view_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    ''' deleting user with all his reservations from the database !'''

    user = User.query.get_or_404(user_id)
    Reservation.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted!', 'success')
    return redirect(url_for('admin_view_users'))

@app.route('/admin/lots/<int:lot_id>/spots')
@admin_required
def view_lot_spots(lot_id):
    ''' In this route we are checking all the available spots and the number of busy and free spots in the lot !'''

    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).order_by(ParkingSpot.spot_number).all()
    free_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').count()
    busy_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()

    return render_template('parking_lot_spots.html',
                           lot=lot,
                           spots=spots,
                           available_count=free_spots,
                           occupied_count=busy_spots)

@app.route('/admin/spots/<int:spot_id>')
@admin_required
def view_parking_spot(spot_id):
    '''here we are checking if the spot is occupied or not ? if spot are occupied, then find the reservation 
       for that spot. if not, then return the spot details without any reservation details !'''
    
    spot = ParkingSpot.query.get_or_404(spot_id)
    reservation = None

    # checking if the spot is occupied or not?
    if spot.status == 'O': 
        curr_reservation = Reservation.query.filter_by( spot_id=spot_id,  leaving_time=None).first() # if yes then find the reservation for that spot
    # if not then return the spot details without any reservation details!
    return render_template('parking_spot_detail.html',spot=spot, reservation=reservation ) 

@app.route('/admin/search')
@admin_required
def admin_search():
    # Get search input
    query = request.args.get('q', '').strip() #why strip? bcz we want to remove any leading or trailing spaces 
    search_type = request.args.get('type', 'all')  # default to 'all' 

    results = {'lots': [],'users': [],'spots': []}

    if not query:
        return render_template('admin_search.html', results=results, search_query=query, search_type=search_type)

    search = f"%{query}%" # sql-wildcards 

    # Search users (either by id , email , username)
    if search_type == 'all' or search_type == 'users':
        if  query.isdigit():
            user_id = int(query)
            user = User.query.filter(User.id == user_id, User.is_admin == False).first()
            if user:
                results['users'].append(user)
        else:
            #case-insensitive bcz who remmembers usernames ?
            found_users = User.query.filter(User.is_admin == False,(User.username.ilike(search) | User.email.ilike(search))).all()
            results['users'].extend(found_users)

    # Search spots (by location name as per wireframe )
    if search_type == 'all' or search_type == 'spots':
        found_spots = (ParkingSpot.query.join(ParkingLot).filter(ParkingLot.location_name.ilike(search)).order_by(ParkingLot.location_name, ParkingSpot.spot_number).all())
        results['spots'] = found_spots

    # Search lots (by location name )
    if search_type == 'all' or search_type == 'lots':
        found_lots = (ParkingLot.query.filter(ParkingLot.location_name.ilike(search)).order_by(ParkingLot.location_name).all())
        results['lots'] = found_lots

    return render_template('admin_search.html',
                            results=results,
                            search_query=query,
                            search_type=search_type)

@app.route('/admin/summary')
@admin_required
def admin_summary():

    lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    users = User.query.filter_by(is_admin=False).count()
    busy = db.session.query(ParkingSpot).join(Reservation).filter( Reservation.leaving_time.is_(None), Reservation.is_active.is_(True)).count()
    free = total_spots - busy
    
    finished_sessions = Reservation.query.filter(Reservation.leaving_time != None).all()

    #calculating the total revenue generated from all the parking sessions and the revenue generated by each parking lot at once!
    revenue = 0
    earnings_by_lot = {}
    for parking_session in finished_sessions:
        if parking_session.parking_cost:
            lot_id = parking_session.parking_spot.lot_id
            earnings_by_lot[lot_id] = earnings_by_lot.get(lot_id, 0) + parking_session.parking_cost
            revenue += parking_session.parking_cost

    lot_data = {} 
    location_names = []
    usage_data = []
    revenues = []
    
    all_lots = ParkingLot.query.all()
    for parking_lot in all_lots:
        lot_id = parking_lot.id
        location_name = parking_lot.location_name
        location_names.append(location_name)
        
        total = ParkingSpot.query.filter_by(lot_id=lot_id).count()
        occupied = db.session.query(ParkingSpot).join(Reservation).filter( ParkingSpot.lot_id == lot_id,
                                                                                  Reservation.leaving_time.is_(None),
                                                                                  Reservation.is_active.is_(True)).count()
        available = total - occupied
        
        usage = (occupied / total) * 100 if total > 0 else 0
        usage_data.append(round(usage, 1))
        lot_revenue = round(earnings_by_lot.get(lot_id, 0), 2)
        revenues.append(lot_revenue)
        
        lot_data[lot_id] = { 'name': location_name,
                                'total_spots': total, 
                                'occupied_spots': occupied, 
                                'available_spots': available, 
                                'utilization': usage / 100, 
                                'revenue': lot_revenue}
    
    return render_template('admin_summary.html',
                            total_lots=lots,
                            total_spots=total_spots,
                            occupied_spots=busy,
                            available_spots=free,
                            total_users=users,
                            total_revenue=revenue,
                            lot_summary=lot_data,
                            lot_names=location_names,
                            utilization_data=usage,
                            revenue_data=revenues )

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Allowing user to update his  email and password ( changing username is locked for now )"""
    user = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not email and not password:
            flash("UGH! You didn't change anything.", 'warning')
            return render_template('edit_profile.html', current_user=user)

        if email and email != user.email:
            if User.query.filter(User.id != user.id, User.email.ilike(email)).first():
                flash("OOPS !Email already in use. Please try different Email. ", 'danger')
                return render_template('edit_profile.html', current_user=user)
            user.email = email

        if password:
            if len(password) < 6:
                flash("UHM !Password must be at least 6 characters.", 'danger')
                return render_template('edit_profile.html', current_user=user)
            if password != confirm_password:
                flash("OOPS! Passwords don’t match, Please Try again.", 'warning')
                return render_template('edit_profile.html', current_user=user)
            user.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        db.session.commit()
        flash("Your profile is looking fresh!", 'success')
        return redirect(url_for('admin_dashboard' if user.is_admin else 'user_dashboard'))
    return render_template('edit_profile.html', current_user=user)

#<--------------------------------------------------------------------- USER ROUTES -------------------------------------------------------->
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)

    current_booking = Reservation.query.filter_by( user_id=user_id, leaving_time = None).first()
    old_bookings = Reservation.query.filter( Reservation.user_id == user_id,
                                             Reservation.leaving_time != None).order_by(Reservation.leaving_time.desc()).all()

    lots = ParkingLot.query.order_by(ParkingLot.location_name).all()
    # finding the number of free spots in each lot and stored in a dictionary!
    available = {}
    for lot in lots:
        free = ParkingSpot.query.filter_by( lot_id=lot.id, status='A').count()
        available[lot.id] = free

    return render_template('user_dashboard.html',
                            user=user,
                            active_reservation=current_booking,
                            past_reservations=old_bookings,
                            available_lots=lots,
                            lot_availability=available,
                            calculate_duration=calculate_duration )

@app.route('/user/book', methods=['POST'])
@login_required
def book_spot():
    ''' Here we are checking if the user has an active reservation or not, 
        if yes, then we are not allowing the user to book a new reservation
        if no, then we are allowing the user to book a new reservation | using try except block | bcz its case sensitive'''
    
    try:
        user_id = session['user_id']
        lot_id = request.form.get('lot_id')
        car_number = request.form.get('vehicle_number')

        #checking  user has active reservation or not ?
        existing = Reservation.query.filter_by(user_id=user_id, leaving_time=None).first()
        if existing:
            flash("You already have an active reservation.", "warning")
            return redirect(url_for('user_dashboard'))

        # Find available spot
        spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
        if not spot:
            flash("Sorry, No available spots in this lot.", "danger")
            return redirect(url_for('user_dashboard'))

        # Proceed with booking
        spot.status = 'O'
        spot.occupied = 1
        booking = Reservation(spot_id=spot.id, user_id=user_id, vehicle_number=car_number, parking_time=datetime.utcnow())
        db.session.add(booking)
        db.session.commit()

        flash(f'Booked Spot {spot.spot_number} at {spot.parking_lot.location_name}!', 'success')
        return redirect(url_for('user_dashboard'))

    except Exception :
        db.session.rollback()
        flash(f"Error while booking spot, Please try again", "danger")
        return redirect(url_for('user_dashboard'))


@app.route('/user/release/<int:reservation_id>', methods=['POST'])
@login_required
def release_spot(reservation_id):
    ''' Here we are releasing the spot by updating the leaving time, total cost and 
        also mark the spot as available and make the reservation inactive !'''
    
    user_id = session['user_id']

    reservation = Reservation.query.filter_by(id=reservation_id, user_id=user_id, leaving_time=None).first_or_404()
    reservation.leaving_time = datetime.utcnow()
    
    # Calculating the cost 
    reservation.parking_cost = calculate_final_cost(reservation.parking_time, reservation.leaving_time, reservation.parking_spot.parking_lot.price)

    # Free up the spot
    spot = reservation.parking_spot
    spot.status = 'A'
    spot.occupied = 0
    reservation.is_active = False

    db.session.commit()

    flash(f"Spot {spot.spot_number} at {spot.parking_lot.location_name} released! "
          f"Total: ₹{reservation.parking_cost:.2f}", 'success')
    return redirect(url_for('user_dashboard'))


@app.route('/user/summary')
@login_required
def user_summary():

    user_id = session['user_id'] 
    current_parking = Reservation.query.filter_by( user_id=user_id, leaving_time=None).first()
    prev_sessions = Reservation.query.filter( Reservation.user_id == user_id,
                                              Reservation.leaving_time.is_not(None) ).order_by(Reservation.leaving_time.desc()).all()
    
    #calculating the total sessions , total spent and average cost per session
    total_sessions = len(prev_sessions)
    total_spent = sum(s.parking_cost for s in prev_sessions if s.parking_cost)
    avg_cost = total_spent / total_sessions if total_sessions > 0 else 0
    
    # calculating the average duration of the parking sessions
    if total_sessions > 0:
        total_time = sum((s.leaving_time - s.parking_time).total_seconds() for s in prev_sessions if s.parking_time and s.leaving_time )
        avg_seconds = total_time / total_sessions
        avg_hours = int(avg_seconds // 3600)
        avg_minutes = int((avg_seconds % 3600) // 60)
        avg_duration = f"{avg_hours}h {avg_minutes}m"
    else:
        avg_duration = "No data available at present , go and park the car !"

    # graph data for making doughnut chart!
    locations = {} # store => Kitni baar kis location me park kiya
    spending = {} # store => Kisi location ke hisaab se kitna paisa lagaya
    
    for s in prev_sessions:
        place = s.parking_spot.parking_lot.location_name
        locations[place] = locations.get(place, 0) + 1
        if s.parking_cost:
            spending[place] = spending.get(place, 0) + s.parking_cost
    
    spend = sorted(spending.items(), key=lambda x: x[1], reverse=True)

    summary = {'total_reservations': total_sessions,
               'total_cost': total_spent,
               'avg_cost': avg_cost,
               'avg_duration': avg_duration }

    return render_template( 'user_summary.html',
                            summary=summary,
                            active_reservation=current_parking,
                            past_reservations=prev_sessions,
                            location_names=list(locations.keys()),
                            location_counts=list(locations.values()),
                            lot_cost_labels=list(x[0] for x in spend),
                            lot_cost_data=list(x[1] for x in spend),
                            calculate_duration=calculate_duration )

if __name__ == '__main__':
    app.run(debug=True) # Debug mode on because I'm still fixing things 

#================================================================================ END ===========================================================