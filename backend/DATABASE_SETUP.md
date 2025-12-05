# MySQL Database Setup Instructions

## Prerequisites
1. Install MySQL Server (https://dev.mysql.com/downloads/mysql/)
2. Start MySQL service

## Database Setup

### Step 1: Create Database
Open MySQL command line or MySQL Workbench and run:

```sql
CREATE DATABASE margametis;
```

### Step 2: Create User (Optional)
If you want a dedicated user for the application:

```sql
CREATE USER 'margametis_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON margametis.* TO 'margametis_user'@'localhost';
FLUSH PRIVILEGES;
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` and update:

```bash
DATABASE_URL=mysql+pymysql://root:password@localhost/margametis
# Or with dedicated user:
# DATABASE_URL=mysql+pymysql://margametis_user:your_password@localhost/margametis

SECRET_KEY=your-secret-key-here
```

### Step 4: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Run the Application
The database tables will be created automatically when you start the application:

```bash
python run.py
```

## Tables Created
- `users` - Stores user authentication data (username, password_hash, role)

## Default Connection String
- Host: localhost
- Port: 3306 (default)
- Database: margametis
- User: root
- Password: password (change this!)
