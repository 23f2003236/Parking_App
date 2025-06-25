# PARKING_App

# Vehicle Parking System

A comprehensive web application for managing parking lots, reservations, and user accounts. This system allows users to book first avaible parking spots, track their parking history, and provides administrators with tools to manage the entire parking system.


### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Rohan-kumar23/PARKING_App.git
   cd PARKING_App
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

5. **Run the application**
   ```bash
   python app.py
   ```


## 🛠️ Technology Stack

- **Backend**: Flask (Python) with SQLAlchemy ORM
- **Database**: SQLite
- **Frontend**: Bootstrap 5, HTML5, CSS3, JavaScript 
- **Visualization**: Chart.js for interactive charts
- **Authentication**: Flask-Session with bcrypt password hashing
- **Icons**: FontAwesome 6.0+ for modern iconography
- **Migration**: Flask-Migrate for database version control

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git (optional but recommended)

## 🙏 Acknowledgements

- **[Flask](https://flask.palletsprojects.com/)** - Web framework
- **[SQLAlchemy](https://www.sqlalchemy.org/)** - Database ORM
- **[Bootstrap](https://getbootstrap.com/)** - UI framework
- **[Chart.js](https://www.chartjs.org/)** - Data visualization
- **[FontAwesome](https://fontawesome.com/)** - Icon library


<div align ="center">

**Developed with ❤️ by [Rohan Kumar](https://github.com/Rohan-kumar23)**

</div>