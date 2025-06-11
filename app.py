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

#=============================================================== Database Setup ==============================================================
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
    capacity = db.Column(db.Integer, nullable=False, default=1)
    occupied = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='Available')

    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id', ondelete='CASCADE'), nullable=False)
    reservations = db.relationship('Reservation', backref='parking_spot', lazy=True, cascade = "all, delete-orphan", passive_deletes=True)

    def is_available(self):
        return self.occupied <= self.capacity

    def __repr__(self):
        return f'<ParkingSpot {self.id} in Lot {self.lot_id}>'

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
        return f'<Reservation {self.id} for Spot {self.spot_id} by User {self.user_id}>'


with app.app_context():
    db.create_all()
    #check if the default admin user exists or not ?
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
    time_parked = datetime.now() - start_time
    hours_parked = time_parked.total_seconds() / 3600
    
    billable_hours = int(hours_parked) + (1 if hours_parked % 1 > 0 else 0) # Round up to next hour
    return max(billable_hours * hourly_rate, hourly_rate) # Minimum 1 hour charge for parking

def calculate_final_cost(start_time, end_time, hourly_rate):
    '''calculating the final cost of the parking session'''

    if not start_time or not end_time or hourly_rate is None:
        return None
    time_parked = end_time - start_time
    hours_parked = time_parked.total_seconds() / 3600
    billable_hours = int(hours_parked) + (1 if hours_parked % 1 > 0 else 0) 
    return max(billable_hours * hourly_rate, hourly_rate) 

@app.template_filter('calculate_duration')
def calculate_duration(start_time, end_time):
    '''calculating the duration of the parking session in hours and minutes'''

    if not start_time or not end_time:
        return "N/A"
    time_diff = end_time - start_time
    total_seconds = time_diff.total_seconds()
    
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
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


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'GET':
        return render_template('login.html')
    # POST request
    entered_username = request.form.get('username','').strip()
    entered_password = request.form.get('password','')

    if not entered_username or not entered_password:
        flash('Please enter both username and password.', 'danger')
        return redirect(url_for('login'))
 
    found_user = User.query.filter_by(username=entered_username).first()

    if found_user and bcrypt.checkpw(entered_password.encode('utf-8'), found_user.password.encode('utf-8')):
        #setting the session of user and redirecting to dashboard
        session['user_id'] = found_user.id
        session['username'] = found_user.username
        session['is_admin'] = found_user.is_admin
            
        flash('Login successful!', 'success')
            
        return redirect(url_for('admin_dashboard') if found_user.is_admin else url_for('user_dashboard'))
    #login failed 
    flash('Invalid username or password. Try again!', 'danger')
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
    
    parking_lots = ParkingLot.query.order_by(ParkingLot.location_name).all()
    
    #calculating the availablity of each parking lot and storing it in dictionary!
    lot_availability = {}
    for lot in parking_lots:
        available_count = ParkingSpot.query.filter_by( lot_id=lot.id, status='A').count()
        lot_availability[lot.id] = available_count
    
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = ParkingSpot.query.filter_by(status='A').count()
    
    return render_template('admin_dashboard.html',
                            parking_lots=parking_lots,
                            lot_availability=lot_availability,
                            total_lots=len(parking_lots),
                            total_spots=total_spots,
                            occupied_spots=occupied_spots,
                            available_spots=available_spots )

@app.route('/admin/lots/add', methods=['GET', 'POST'])
@admin_required
def add_lot():
    if request.method == 'GET':
        return render_template('parking_lot_form.html', lot=None)
    # POST request
    location_name = request.form['location_name']
    lot_address = request.form['address']
    pin_code = request.form['pin_code']
    hourly_price = float(request.form['price'])
    total_spots = int(request.form['number_of_spots'])

    #checking total spots and price are positive or not ?
    if total_spots <= 0 or hourly_price < 0:
        flash('Number of spots and price must be positive.', 'warning')
        return render_template('parking_lot_form.html', lot=None)

    #if yes, then create a new parking lot
    new_parking_lot = ParkingLot( location_name=location_name,
                                  address=lot_address,
                                  pin_code=pin_code, 
                                  price=hourly_price, 
                                  number_of_spots=total_spots )
    db.session.add(new_parking_lot)
    db.session.flush() # why flush ? we use flush here to get the lot_id of the new lot to create parking spots

    # create parking spots
    for spot_number in range(1, total_spots + 1):
        parking_spot = ParkingSpot(
            lot_id=new_parking_lot.id,
            spot_number=spot_number,
            status='A')
        db.session.add(parking_spot)
    #if everything is fine, commit the changes!
    db.session.commit()
    flash(f'Parking lot "{location_name}" and its {total_spots} spots created successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/lots/edit/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def edit_lot(lot_id):
    
    lot = ParkingLot.query.get_or_404(lot_id) # get the lot first
    if request.method == 'GET':
        return render_template('parking_lot_form.html', lot=lot)
    # POST request
    new_name = request.form['location_name']
    new_address = request.form['address']
    new_pin = request.form['pin_code']
    new_price = float(request.form['price'])
    new_spot_count = int(request.form['number_of_spots'])
    # checking if the new price and spot count are valid or not ?
    if new_price < 0:
        flash('Price cannot be negative!', 'warning')
        return render_template('parking_lot_form.html', lot=lot)
    if new_spot_count < 1:
        flash('You need at least 1 parking spot!', 'warning')
        return render_template('parking_lot_form.html', lot=lot)
    #if yes, then update the lot
    lot.location_name = new_name
    lot.address = new_address
    lot.pin_code = new_pin
    lot.price = new_price

    current_spots = ParkingSpot.query.filter_by(lot_id=lot_id).count()

    ''' now we have to update the number of spots in the lot - there are three cases here:
    1. if the new spot count is same as the current spot count, then update the lot and then commit it !
    2. if the new spot count is greater than the current spot count, then add the new spots and update the lot and then commit it !
    3. if the new spot count is less than the current spot count, then remove the extra spots and update the lot and then commit it !'''
    
    #handling case 1:
    if new_spot_count == current_spots:
        db.session.commit()
        flash(f'Updated "{lot.location_name}" successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    #handling case 2 :
    elif new_spot_count > current_spots:
        add_spot = new_spot_count - current_spots
        
        for i in range(add_spot):
            next_spot_number = current_spots + i + 1
            new_spot = ParkingSpot( lot_id=lot_id,
                                    spot_number=next_spot_number, 
                                    status='A')
            db.session.add(new_spot)
        lot.number_of_spots = new_spot_count
        db.session.commit()
        flash(f'Added {add_spot} new spots!', 'success')
        return redirect(url_for('admin_dashboard'))

    #handling case 3 :
    else:
        how_many_to_remove = current_spots - new_spot_count
        busy_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
        if new_spot_count < busy_spot:
            flash(f"Can't do that! {busy_spot} people are currently parked, but you want only {new_spot_count} spots. Increase that for no error! ", 'danger')
            return render_template('parking_lot_form.html', lot=lot)
        
        delete_spot = ParkingSpot.query.filter( ParkingSpot.lot_id == lot_id, 
                                               ParkingSpot.spot_number > new_spot_count ).all()
        for spot in delete_spot:
            Reservation.query.filter_by(spot_id=spot.id).delete()
            db.session.delete(spot)
        lot.number_of_spots = new_spot_count
        db.session.commit()
        flash(f'Removed {how_many_to_remove} spots successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/lots/delete/<int:lot_id>', methods=['POST'])
@admin_required
def delete_lot(lot_id):
    '''deleting a lot means deleting all the spots too from that lot and then deleting the lot itself 
    but we already use cascade delete in the models, so no need to delete the spots manually !'''

    lot_to_delete = ParkingLot.query.get_or_404(lot_id)
    spots_in_use = ParkingSpot.query.filter_by(lot_id=lot_to_delete.id, status='O').count()

    # we can't delete a lot if it has occupied spots!
    if spots_in_use > 0:
        flash(f'Cannot delete lot "{lot_to_delete.location_name}" because it has occupied spots.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    lot_name = lot_to_delete.location_name
    db.session.delete(lot_to_delete)
    db.session.commit()
    flash(f'Parking lot "{lot_name}" deleted successfully!', 'success') 
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_view_users():
    # get all the users from the database
    users = User.query.filter_by(is_admin=False).order_by(User.username).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/view/<int:user_id>')
@admin_required
def admin_view_user(user_id):

    user = User.query.get_or_404(user_id)

    # get all the reservations of the user
    user_parking_history = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_time.desc()).all()
    money_spent = 0
    for reservation in user_parking_history: 
        if reservation.parking_cost:
            money_spent += reservation.parking_cost
    
    if user_parking_history:
        avg_spending = money_spent / len(user_parking_history)
    avg_spending = 0

    #appending all the finished sessions by user in a list 
    finished_sessions = []
    for reservation in user_parking_history:
        if reservation.leaving_time:
            finished_sessions.append(reservation)
    # if the user has finished sessions then calculate the avg parking time
    if finished_sessions:
        total_parking_time = 0
        for reservation in finished_sessions:
            session_duration = reservation.leaving_time - reservation.parking_time
            total_parking_time += session_duration.total_seconds()
        
        avg_time_seconds = total_parking_time / len(finished_sessions)
        avg_hours = int(avg_time_seconds // 3600)
        remaining_seconds = avg_time_seconds % 3600
        avg_minutes = int(remaining_seconds // 60)
        avg_duration = f'{avg_hours}h {avg_minutes}m'
    else:
        avg_duration = 'N/A'
    
    return render_template('admin_view_user.html',
                            user=user,
                            parking_history=user_parking_history,
                            total_cost=money_spent,
                            avg_cost=avg_spending,
                            avg_duration=avg_duration )

@app.route('/admin/add_user', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    if request.method == 'GET':
        return render_template('admin_add_user.html')
    # POST request
    uname = request.form['username']
    pwd = request.form['password']
    email = request.form['email']
    phone = request.form.get('phone', '')
    address = request.form.get('address', '')
    
    user_exist = User.query.filter((User.username == uname) | (User.email == email)).first() 
    # checking if the username or email already exists or not ?
    if user_exist:
        flash('Username or email already exists.', 'danger')
        return render_template('admin_add_user.html')

    # if not then create a new user and commit it!
    hashed_password = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt())
    new_user = User( username=uname,
                     password=hashed_password.decode('utf-8'), 
                     email=email, phone=phone, 
                     address=address,
                     is_admin=False)
    db.session.add(new_user)
    db.session.commit()
    flash(f'User "{uname}" created successfully!', 'success')
    return redirect(url_for('admin_view_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    ''' deleting user with all his reservations from the database !'''

    user_to_delete = User.query.get_or_404(user_id)
    user_reservations = Reservation.query.filter_by(user_id=user_to_delete.id)
    user_reservations.delete()
    username = user_to_delete.username
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'User {username} has been deleted successfully.', 'success')
    return redirect(url_for('admin_view_users'))

@app.route('/admin/lots/<int:lot_id>/spots')
@admin_required
def view_lot_spots(lot_id):
    ''' here we are checking all the available spots in the lot and the number of busy and free spots in the lot !'''

    parking_lot = ParkingLot.query.get_or_404(lot_id)
    all_spots = ParkingSpot.query.filter_by(lot_id=lot_id).order_by(ParkingSpot.spot_number).all()
    
    free_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').count()
    busy_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()

    return render_template('parking_lot_spots.html',
                           lot=parking_lot,
                           spots=all_spots,
                           available_count=free_spots,
                           occupied_count=busy_spots)

@app.route('/admin/spots/<int:spot_id>')
@admin_required
def view_parking_spot(spot_id):
    '''here we are checking if the spot is occupied or not ? if spot are occupied, then find the reservation 
       for that spot. if not, then return the spot details without any reservation details !'''
    
    parking_spot = ParkingSpot.query.get_or_404(spot_id)
    curr_reservation = None

    # checking if the spot is occupied or not?
    if parking_spot.status == 'O':
        # if yes then find the reservation for that spot 
        curr_reservation = Reservation.query.filter_by( spot_id=spot_id,  leaving_time=None).first() 
    # if not then return the spot details without any reservation details!
    return render_template('parking_spot_detail.html',spot=parking_spot, reservation=curr_reservation ) 

@app.route('/admin/search')
@admin_required
def admin_search():
    # Get search input
    query = request.args.get('q', '').strip() #why strip? bcz we want to remove any leading or trailing spaces 
    search_type = request.args.get('type', 'all')  # default to 'all' bcz we are generous to know everything like that !HAHA

    results = {'lots': [],'users': [],'spots': []}

    #if nothing search then we give empty results without hesitation
    if not query:
        return render_template('admin_search.html', results=results, search_query=query, search_type=search_type)

    search_pattern = f"%{query}%" # wildcards 

    # Search users (either by id , email , username)
    if search_type == 'all' or search_type == 'users':
        if  query.isdigit():
            user_id = int(query)
            user = User.query.filter(User.id == user_id, User.is_admin == False).first()
            if user:
                results['users'].append(user)
        else:
            #case-insensitive bcz admin is lazy to type
            found_users = User.query.filter(User.is_admin == False,(User.username.ilike(search_pattern) | User.email.ilike(search_pattern))).all()
            results['users'].extend(found_users)

    # Search spots (by location name as per wireframe )
    if search_type == 'all' or search_type == 'spots':
        found_spots = (ParkingSpot.query.join(ParkingLot).filter(ParkingLot.location_name.ilike(search_pattern)).order_by(ParkingLot.location_name, ParkingSpot.spot_number).all())
        results['spots'] = found_spots

    # Search lots (by location name )
    if search_type == 'all' or search_type == 'lots':
        found_lots = (ParkingLot.query.filter(ParkingLot.location_name.ilike(search_pattern)).order_by(ParkingLot.location_name).all())
        results['lots'] = found_lots

    return render_template('admin_search.html',
                            results=results,
                            search_query=query,
                            search_type=search_type)

@app.route('/admin/summary')
@admin_required
def admin_summary():

    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    total_users = User.query.filter_by(is_admin=False).count()
    
    busy_spots = db.session.query(ParkingSpot).join(Reservation).filter( Reservation.leaving_time.is_(None), Reservation.is_active.is_(True)).count()
    free_spots = total_spots - busy_spots
    
    finished_sessions = Reservation.query.filter(Reservation.leaving_time != None).all()

    #calculating the total revenue generated from all the parking sessions and the revenue generated by each parking lot at once!
    total_revenue = 0
    earnings_by_lot = {}
    for parking_session in finished_sessions:
        if parking_session.parking_cost:
            lot_id = parking_session.parking_spot.lot_id
            earnings_by_lot[lot_id] = earnings_by_lot.get(lot_id, 0) + parking_session.parking_cost
            total_revenue += parking_session.parking_cost

    # graph data for making pie chart!
    lot_details = {}
    location_names = []
    usage_percent = []
    lot_revenues = []
    
    all_lots = ParkingLot.query.all()
    for parking_lot in all_lots:
        lot_id = parking_lot.id
        location_name = parking_lot.location_name
        location_names.append(location_name)
        
        spots_in_lot = ParkingSpot.query.filter_by(lot_id=lot_id).count()
        
        occupied_in_lot = db.session.query(ParkingSpot).join(Reservation).filter( ParkingSpot.lot_id == lot_id,
                                                                                  Reservation.leaving_time != None,
                                                                                  Reservation.is_active == True).count()
        available_in_lot = spots_in_lot - occupied_in_lot
        
        usage = (occupied_in_lot / spots_in_lot) * 100 if spots_in_lot > 0 else 0
        lot_revenue = round(earnings_by_lot.get(lot_id, 0), 2)

        usage_percent.append(round(usage, 1))
        lot_revenues.append(lot_revenue)
        
        lot_details[lot_id] = { 'name': location_name,
                                'total_spots': spots_in_lot, 
                                'occupied_spots': occupied_in_lot, 
                                'available_spots': available_in_lot, 
                                'utilization': usage / 100, 
                                'revenue': lot_revenue}
    
    return render_template('admin_summary.html',
                            total_lots=total_lots,
                            total_spots=total_spots,
                            occupied_spots=busy_spots,
                            available_spots=free_spots,
                            total_users=total_users,
                            total_revenue=total_revenue,
                            lot_summary=lot_details,
                            lot_names=location_names,
                            utilization_data=usage_percent,
                            revenue_data=lot_revenues )

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    ''' this is common for both admin and user , they can change their 
        username , email , phone , address  anytime anywhere '''
    
    user_id = session['user_id'] # Get the user ID from the session
    user = User.query.get_or_404(user_id) # Automatically handles "not found"

    if request.method == 'GET':
        return render_template('edit_profile.html', current_user=user)
    # POST request
    new_uname = request.form['username']
    new_email = request.form['email']
    new_phone = request.form.get('phone', '')
    new_address = request.form.get('address', '')

    user_exist = User.query.filter( User.id != user_id, (User.username == new_uname) | (User.email == new_email)).first()
    # check if the username or email already exists in the database or not ?
    if user_exist:
        flash('Username or email already taken.', 'danger')
        return render_template('edit_profile.html', current_user=user)
    # If not, then update the user account 
    user.username = new_uname
    user.email = new_email
    user.phone = new_phone
    user.address = new_address
    db.session.commit()
    session['username'] = user.username # updating the session username too
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('admin_dashboard' if user.is_admin else 'user_dashboard'))

#<--------------------------------------------------------------------- USER ROUTES -------------------------------------------------------->
@app.route('/user/dashboard')
@login_required
def user_dashboard():

    current_user_id = session['user_id'] # getting the current user id of the user
    current_user = User.query.get_or_404(current_user_id) # getting the current user details

    current_booking = Reservation.query.filter_by( user_id=current_user_id, leaving_time = None).first()
    old_bookings = Reservation.query.filter( Reservation.user_id == current_user_id, Reservation.leaving_time != None).order_by(Reservation.leaving_time.desc()).all()

    all_lots = ParkingLot.query.order_by(ParkingLot.location_name).all()

    # finding the number of free spots in each lot and stored in a dictionary
    spots_available = {}
    for parking_lot in all_lots:
        free_spots = ParkingSpot.query.filter_by( lot_id=parking_lot.id, status='A').count()
        spots_available[parking_lot.id] = free_spots

    return render_template('user_dashboard.html',
                            user=current_user,
                            active_reservation=current_booking,
                            past_reservations=old_bookings,
                            available_lots=all_lots,
                            lot_availability=spots_available,
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
            flash("No available spots in this lot.", "danger")
            return redirect(url_for('user_dashboard'))

        # Proceed with booking
        spot.status = 'O'
        spot.occupied = 1
        booking = Reservation(spot_id=spot.id, user_id=user_id, vehicle_number=car_number, parking_time=datetime.utcnow())
        db.session.add(booking)
        db.session.commit()

        flash(f'Booked Spot {spot.spot_number} at {spot.parking_lot.location_name}!', 'success')
        return redirect(url_for('user_dashboard'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error while booking: {str(e)}", "danger")
        return redirect(url_for('user_dashboard'))


@app.route('/user/release/<int:reservation_id>', methods=['POST'])
@login_required
def release_spot(reservation_id):
    ''' Here we are releasing the spot by updating the leaving time, total cost and 
        free up the spot | using try except block | bcz its case sensitive'''
    
    try:
        current_user = session.get('user_id')

        reservation = Reservation.query.filter_by(id=reservation_id, user_id=current_user, leaving_time=None).first_or_404()
        # Mark leaving time
        reservation.leaving_time = datetime.utcnow()
        rate = reservation.parking_spot.parking_lot.price
        # Calculate cost
        reservation.parking_cost = calculate_final_cost(reservation.parking_time, reservation.leaving_time, rate)

        # Free up the spot
        spot = reservation.parking_spot
        spot.status = 'A'
        spot.occupied = 0
        reservation.is_active = False

        db.session.commit()

        flash(
            f"Spot {spot.spot_number} at {spot.parking_lot.location_name} released. "
            f"Total charge: ₹{reservation.parking_cost:.2f}", 'success')
        return redirect(url_for('user_dashboard'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error while releasing the spot: {str(e)}", 'danger')
        return redirect(url_for('user_dashboard'))


@app.route('/user/summary')
@login_required
def user_summary():

    user_id = session['user_id'] 
    #active reservation
    current_parking = Reservation.query.filter_by( user_id=user_id, leaving_time=None).first()

    past_sessions = Reservation.query.filter( Reservation.user_id == user_id, Reservation.leaving_time.is_not(None) ).order_by(Reservation.leaving_time.desc()).all()
    
    #calculating the total sessions , total spent and average cost per session
    total_sessions = len(past_sessions)
    total_spent = sum(s.parking_cost for s in past_sessions if s.parking_cost)
    avg_cost = total_spent / total_sessions if total_sessions > 0 else 0

    # calculating the average duration of the parking sessions
    if total_sessions > 0:
        total_time = sum((s.leaving_time - s.parking_time).total_seconds() for s in past_sessions if s.parking_time and s.leaving_time )
        avg_seconds = total_time / total_sessions
        avg_hours = int(avg_seconds // 3600)
        avg_minutes = int((avg_seconds % 3600) // 60)
        avg_duration = f"{avg_hours}h {avg_minutes}m"
    else:
        avg_duration = "No data available at present , go and park the car !"
    
    # graph data for making doughnut chart!
    locations = {} # store => Kitni baar kis location me park kiya
    spending = {} # store => Kisi location ke hisaab se kitna paisa lagaya
    
    for parking_session in past_sessions:
        place = parking_session.parking_spot.parking_lot.location_name
        locations[place] = locations.get(place, 0) + 1
        if parking_session.parking_cost:
            spending[place] = spending.get(place, 0) + parking_session.parking_cost
    
    location_names = list(locations.keys())
    location_counts = list(locations.values())

    #spending = {'Pune': 500,'Mumbai': 1200,'Delhi': 700}
    spending = sorted(spending.items(), key=lambda x: x[1], reverse=True)
    names = [name for name, _ in spending]
    amounts = [amount for _, amount in spending]

    summary = {'total_reservations': total_sessions,
               'total_cost': total_spent,
               'avg_cost': avg_cost,
               'avg_duration': avg_duration}

    return render_template( 'user_summary.html',
                            summary=summary,
                            active_reservation=current_parking,
                            past_reservations=past_sessions,
                            location_names=location_names,
                            location_counts=location_counts,
                            lot_cost_labels=names,
                            lot_cost_data=amounts,
                            calculate_duration=calculate_duration )

if __name__ == '__main__':
    app.run(debug=True) # Debug mode on because I'm still fixing things 



#================================================================================ END ===========================================================