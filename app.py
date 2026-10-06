import os
import sys
import re
import random
import smtplib
import threading
from datetime import datetime, timedelta, date
from functools import wraps
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import pymysql
import pymysql.cursors
from flask import Flask, render_template, request, redirect, url_for, jsonify, g, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "netpulse-hackathon-demo-secret")

# MySQL Configuration
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("MYSQL_DB", "broadband_db")

MYSQL_SSL_CA = os.environ.get(
    "MYSQL_SSL_CA",
    os.path.join(os.path.dirname(__file__), "certs", "aiven-ca.pem")
)

# Email SMTP Configuration (Gmail Sender / Admin Account)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.environ.get("OUTBOUND_EMAIL_HOST_USER") or os.environ.get("EMAIL_HOST_USER", "knsknsk10@gmail.com")
EMAIL_HOST_PASSWORD = os.environ.get("OUTBOUND_EMAIL_HOST_PASSWORD") or os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@yourdomain.com")


# ---------------------------------------------------------------------------
# Email Helper Functions (Async SMTP to Registered Customer Email)
# ---------------------------------------------------------------------------

def send_email_async(to_email, subject, body_html, body_text=None):
    """Sends outbound email asynchronously to the recipient's specific registered email address."""
    def _send():
        if not to_email or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            print(f"[Email] Skipped sending to '{to_email}': Invalid recipient or missing SMTP credentials.")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"NetPulse Broadband <{EMAIL_HOST_USER}>"
            msg["To"] = to_email

            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=10)
            if EMAIL_USE_TLS:
                server.starttls()
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.sendmail(EMAIL_HOST_USER, [to_email], msg.as_string())
            server.quit()
            print(f"[Email] Successfully sent '{subject}' to customer email: {to_email}")
        except Exception as e:
            print(f"[Email] Error sending email to {to_email}: {e}")

    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()


def send_welcome_email(to_email, customer_name, connection_id, plan_name):
    subject = f"Welcome to NetPulse Broadband! (Connection: {connection_id})"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #0F3443;">Welcome to NetPulse Broadband!</h2>
        <p>Dear <strong>{customer_name}</strong>,</p>
        <p>Thank you for registering with NetPulse Broadband. Your account has been successfully created!</p>
        <div style="background-color: #f4f6f8; padding: 15px; border-radius: 6px; margin: 15px 0;">
            <p style="margin: 5px 0;"><strong>Connection ID:</strong> {connection_id}</p>
            <p style="margin: 5px 0;"><strong>Registered Email:</strong> {to_email}</p>
            <p style="margin: 5px 0;"><strong>Subscribed Plan:</strong> {plan_name}</p>
            <p style="margin: 5px 0;"><strong>Status:</strong> Pending Activation Payment</p>
        </div>
        <p>Please complete your activation payment to start enjoying high-speed internet service.</p>
        <p style="color: #666; font-size: 12px; margin-top: 20px;">NetPulse Customer Support</p>
    </div>
    """
    send_email_async(to_email, subject, html_content)


def send_recharge_receipt(to_email, customer_name, connection_id, plan_name, amount, payment_mode, status, due_date):
    subject = f"Recharge Receipt ({status}) - NetPulse ({connection_id})"
    color = "#10B981" if status == "Success" else "#EF4444"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #0F3443;">Recharge Transaction Notification</h2>
        <p>Hi <strong>{customer_name}</strong>,</p>
        <p>Here are the transaction details for connection <strong>{connection_id}</strong>:</p>
        <div style="background-color: #f4f6f8; padding: 15px; border-radius: 6px; margin: 15px 0;">
            <p style="margin: 5px 0;"><strong>Plan:</strong> {plan_name}</p>
            <p style="margin: 5px 0;"><strong>Amount Paid:</strong> ₹{amount}</p>
            <p style="margin: 5px 0;"><strong>Payment Mode:</strong> {payment_mode}</p>
            <p style="margin: 5px 0;"><strong>Transaction Status:</strong> <span style="color: {color}; font-weight: bold;">{status}</span></p>
            <p style="margin: 5px 0;"><strong>Valid Until:</strong> {due_date}</p>
        </div>
        {"<p style='color: #10B981;'>Your plan has been activated/extended successfully!</p>" if status == 'Success' else "<p style='color: #EF4444;'>Payment failed. Please retry from your customer portal.</p>"}
        <p style="color: #666; font-size: 12px; margin-top: 20px;">NetPulse Customer Support</p>
    </div>
    """
    send_email_async(to_email, subject, html_content)


def send_expiry_reminder(to_email, customer_name, connection_id, due_date, price, days_left=7, usage_info=None):
    subject = f"Urgent: 7-Day Renewal Reminder for Connection {connection_id}"
    
    recommendation_html = ""
    if usage_info:
        rec_type = usage_info.get("recommendation", "No change")
        reason = usage_info.get("reason", "")
        sugg_plan = usage_info.get("suggested_plan")
        
        border_color = "#10B981" if rec_type == "No change" else ("#F59E0B" if rec_type == "Upgrade" else "#EF4444")
        bg_color = "#F0FDF4" if rec_type == "No change" else ("#FEF3C7" if rec_type == "Upgrade" else "#FEE2E2")
        
        sugg_html = ""
        if sugg_plan:
            sugg_html = f"""<p style="margin: 8px 0 0 0; color: #0EA5E9; font-weight: bold;">Suggested Plan: {sugg_plan['name']} (₹{sugg_plan['price']}/month, {sugg_plan['speed']}, {sugg_plan['data_limit']})</p>"""

        recommendation_html = f"""
        <div style="background-color: {bg_color}; border-left: 4px solid {border_color}; padding: 15px; margin: 15px 0; border-radius: 6px;">
            <h4 style="margin: 0 0 5px 0; color: #0F3443;">💡 AI Usage Recommendation: {rec_type}</h4>
            <p style="margin: 0; color: #334155; font-size: 14px;">{reason}</p>
            {sugg_html}
        </div>
        """

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #0F3443;">NetPulse 7-Day Renewal Notice</h2>
        <p>Dear <strong>{customer_name}</strong>,</p>
        <p>This is a notification that your NetPulse Broadband plan for connection <strong>{connection_id}</strong> will expire in <strong>{days_left} day(s)</strong> on <strong>{due_date}</strong>.</p>
        
        <div style="background-color: #fff8e6; border-left: 4px solid #f59e0b; padding: 15px; margin: 15px 0; border-radius: 6px;">
            <p style="margin: 0; color: #92400e;"><strong>Current Renewal Price:</strong> ₹{price}</p>
            <p style="margin: 5px 0 0 0; color: #92400e;">Please recharge online before your due date to avoid service interruption.</p>
        </div>

        {recommendation_html}

        <p>Log in to your portal to recharge instantly using UPI, Card, or Net Banking.</p>
        <p style="color: #666; font-size: 12px; margin-top: 20px;">NetPulse Support Team</p>
    </div>
    """
    send_email_async(to_email, subject, html_content)


def check_and_send_7day_renewal_alerts():
    """Queries all customers expiring within the next 7 days and sends renewal reminder emails including AI usage recommendations to each customer's registered email address."""
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            charset='utf8mb4'
        )
        db = MySQLDatabaseWrapper(conn)
        today = datetime.now().date()
        week_ahead = today + timedelta(days=7)

        rows = db.execute(
            """SELECT c.*, p.name AS plan_name, p.price
               FROM customers c JOIN plans p ON c.plan_id = p.id
               WHERE c.due_date BETWEEN %s AND %s""",
            (today.strftime("%Y-%m-%d"), week_ahead.strftime("%Y-%m-%d")),
        ).fetchall()

        count = 0
        for cust in rows:
            due_str = str(cust["due_date"])
            due_date_obj = datetime.strptime(due_str, "%Y-%m-%d").date() if isinstance(due_str, str) else due_str
            days_left = (due_date_obj - today).days

            email_addr = cust.get("email")
            if email_addr:
                usage_info = get_usage_recommendation(db, cust["id"], cust["plan_id"])
                send_expiry_reminder(
                    email_addr,
                    cust["name"],
                    cust["connection_id"],
                    due_str,
                    cust["price"],
                    days_left=days_left,
                    usage_info=usage_info
                )
                count += 1

        db.close()
        print(f"[Renewal Alerts] Successfully dispatched 7-day renewal reminder emails for {count} customer(s).")
        return count
    except Exception as e:
        print(f"[Renewal Alerts] Error running 7-day renewal check: {e}")
        return 0


# ---------------------------------------------------------------------------
# MySQL Database Helpers & Wrappers
# ---------------------------------------------------------------------------

class MySQLCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = cursor.lastrowid

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return self._format_row(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [self._format_row(r) for r in rows]

    def _format_row(self, row):
        formatted = {}
        for key, val in row.items():
            if isinstance(val, (date, datetime)):
                formatted[key] = val.strftime("%Y-%m-%d")
            else:
                formatted[key] = val
        return formatted


class MySQLDatabaseWrapper:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, args=None):
        cur = self.conn.cursor(pymysql.cursors.DictCursor)
        cur.execute(query, args or ())
        return MySQLCursorWrapper(cur)

    def executemany(self, query, args):
        cur = self.conn.cursor(pymysql.cursors.DictCursor)
        cur.executemany(query, args)
        return MySQLCursorWrapper(cur)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def print_connection_help(err):
    print("\n" + "=" * 70, file=sys.stderr)
    print("  MySQL Connection Error!", file=sys.stderr)
    print(f"  Details: {err}", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("  Please check your MySQL configuration in the `.env` file:", file=sys.stderr)
    print(f"    MYSQL_HOST={MYSQL_HOST}", file=sys.stderr)
    print(f"    MYSQL_PORT={MYSQL_PORT}", file=sys.stderr)
    print(f"    MYSQL_USER={MYSQL_USER}", file=sys.stderr)
    print("    MYSQL_PASSWORD=<your_mysql_password>", file=sys.stderr)
    print(f"    MYSQL_DB={MYSQL_DB}", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)


def get_server_connection():
    try:
        return pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            autocommit=True,
            charset="utf8mb4",
            ssl={"ca": MYSQL_SSL_CA}
        )
    except pymysql.Error as e:
        print_connection_help(e)
        raise e


def get_db():
    if "db" not in g:
        try:
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                charset='utf8mb4',
                ssl={"ca": MYSQL_SSL_CA}
            )
            g.db = MySQLDatabaseWrapper(conn)
        except pymysql.Error as e:
            print_connection_help(e)
            raise e
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create MySQL database and tables IF NOT EXISTS. Seed demo data ONLY if database is empty."""
    print(f"Connecting to MySQL server at '{MYSQL_HOST}:{MYSQL_PORT}' as user '{MYSQL_USER}'...")
    
    db_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset='utf8mb4',
        ssl={"ca": MYSQL_SSL_CA}
    )
    db = MySQLDatabaseWrapper(db_conn)

    # Ensure tables exist without dropping existing data
    db.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            speed VARCHAR(50) NOT NULL,
            data_limit VARCHAR(50) NOT NULL,
            data_limit_gb DOUBLE NOT NULL,
            validity_days INT NOT NULL,
            price DOUBLE NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            connection_id VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            address TEXT,
            plan_id INT NOT NULL,
            start_date DATE NOT NULL,
            due_date DATE NOT NULL,
            followed_up INT DEFAULT 0,
            FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT NOT NULL,
            plan_id INT NOT NULL,
            amount DOUBLE NOT NULL,
            payment_mode VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            status VARCHAR(50) NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT NOT NULL,
            date DATE NOT NULL,
            data_consumed DOUBLE NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            customer_id INT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # Check if database has already been seeded or updated by user
    plan_count = db.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
    if plan_count == 0:
        print("[Database] Database is empty. Seeding initial demo plans, customers, and users...")
        plans = [
            ("Home Basic", "50 Mbps", "500 GB", 500, 30, 499),
            ("Home Plus", "100 Mbps", "1000 GB", 1000, 30, 799),
            ("Home Pro Unlimited", "300 Mbps", "Unlimited", 3000, 30, 1299),
        ]
        db.executemany(
            "INSERT INTO plans (name, speed, data_limit, data_limit_gb, validity_days, price) VALUES (%s, %s, %s, %s, %s, %s)",
            plans,
        )

        customers = [
            ("Lokesh", "BB-1001", "lokesh@example.com", "12 Gandhi Nagar", 1),
            ("Sailu", "BB-1002", "sailu@example.com", "45 Lake View Rd", 2),
            ("Arjun", "BB-1003", "arjun@example.com", "7 MG Road", 3),
            ("Naveen", "BB-1004", "naveen@example.com", "22 Park Street", 1),
            ("Akhil", "BB-1005", "akhilexample.com", "9 Hill View Colony", 2),
            ("Deepthi", "BB-1006", "deepthi@example.com", "3 Church Street", 3),
        ]

        today = datetime.now()
        plan_validity = {i + 1: plans[i][4] for i in range(len(plans))}
        plan_prices = {i + 1: plans[i][5] for i in range(len(plans))}
        plan_limit_gb = {i + 1: plans[i][3] for i in range(len(plans))}

        customer_ids = []
        for name, cid, email_addr, addr, plan_id in customers:
            start = today - timedelta(days=random.randint(20, 90))
            due = start + timedelta(days=plan_validity[plan_id])
            cur = db.execute(
                "INSERT INTO customers (name, connection_id, email, address, plan_id, start_date, due_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (name, cid, email_addr, addr, plan_id, start.strftime("%Y-%m-%d"), due.strftime("%Y-%m-%d")),
            )
            customer_ids.append((cur.lastrowid, plan_id))

        near_expiry_days = [3, 6]
        for i, (cust_id, plan_id) in enumerate(customer_ids[:2]):
            due = today + timedelta(days=near_expiry_days[i])
            db.execute("UPDATE customers SET due_date = %s WHERE id = %s", (due.strftime("%Y-%m-%d"), cust_id))

        payment_modes = ["UPI", "Card", "Net Banking"]
        usage_tendencies = [1.1, 1.3, 0.6, 0.5, 0.25, 0.2]

        for idx, (cust_id, plan_id) in enumerate(customer_ids):
            for month_back in range(5):
                tx_date = today - timedelta(days=month_back * 30 + random.randint(0, 5))
                status = "Success" if random.random() > 0.18 else "Failed"
                db.execute(
                    "INSERT INTO transactions (customer_id, plan_id, amount, payment_mode, date, status) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        cust_id,
                        plan_id,
                        plan_prices[plan_id],
                        random.choice(payment_modes),
                        tx_date.strftime("%Y-%m-%d"),
                        status,
                    ),
                )

            tendency = usage_tendencies[idx % len(usage_tendencies)]
            monthly_target = plan_limit_gb[plan_id] * tendency
            for d in range(6):
                log_date = today - timedelta(days=d * 5)
                per_log = round((monthly_target / 6) * random.uniform(0.8, 1.2), 1)
                db.execute(
                    "INSERT INTO usage_logs (customer_id, date, data_consumed) VALUES (%s, %s, %s)",
                    (cust_id, log_date.strftime("%Y-%m-%d"), max(per_log, 0.5)),
                )

        db.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email, customer_id) VALUES (%s, %s, %s, %s, %s, %s)",
            ("admin", generate_password_hash("admin123"), "admin", "Business Admin", "admin@gmail.com", None),
        )
        db.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email, customer_id) VALUES (%s, %s, %s, %s, %s, %s)",
            ("staff", generate_password_hash("staff123"), "staff", "Support Staff", "staff@gmail.com", None),
        )
        for (cust_id, _), (name, cid, email_addr, addr, plan_id) in zip(customer_ids, customers):
            db.execute(
                "INSERT INTO users (username, password_hash, role, display_name, email, customer_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (cid, generate_password_hash("pass123"), "customer", name, email_addr, cust_id),
            )

        db.commit()
        print("[Database] MySQL demo seeding complete!")

    db.close()
    print("[Database] Permanent MySQL connection verified!")

    check_and_send_7day_renewal_alerts()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(roles=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login", next=request.path))
            if roles is not None and session.get("role") not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return {
        "current_user": {
            "display_name": session.get("display_name"),
            "role": session.get("role"),
        }
    }


# ---------------------------------------------------------------------------
# Routes - auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form.get("username_or_email", "").strip() or request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        
        user = db.execute(
            "SELECT * FROM users WHERE username = %s OR email = %s",
            (login_input, login_input)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid username/email or password.", form_input=login_input)

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["display_name"] = user["display_name"]
        session["customer_id"] = user["customer_id"]

        if user["role"] == "customer":
            return redirect(url_for("customer_view", customer_id=user["customer_id"]))
        elif user["role"] == "staff":
            return redirect(url_for("expiry_list"))
        else:
            return redirect(url_for("admin_dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    plans = db.execute("SELECT * FROM plans ORDER BY price ASC").fetchall()

    # Calculate next suggested Connection ID (e.g. BB-1007)
    last_cust = db.execute("SELECT connection_id FROM customers WHERE connection_id LIKE 'BB-%%' ORDER BY id DESC LIMIT 1").fetchone()
    next_cid = "BB-1007"
    if last_cust and last_cust.get("connection_id"):
        try:
            num = int(last_cust["connection_id"].replace("BB-", ""))
            next_cid = f"BB-{num + 1}"
        except Exception:
            pass

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        connection_id = request.form.get("connection_id", "").strip() or next_cid
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        plan_id = request.form.get("plan_id")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        errors = []
        if not name or not connection_id or not username or not password or not email:
            errors.append("Name, connection ID, email address, username, and password are all required.")
        elif not re.match(r"^[A-Za-z\s.'-]{2,}$", name):
            errors.append("Full Name must contain letters and spaces only (numbers are not allowed).")

        if plan_id is None:
            errors.append("Please choose a plan.")
        if len(password) < 4:
            errors.append("Password must be at least 4 characters.")

        if not errors:
            existing_user_by_username = db.execute("SELECT 1 FROM users WHERE username = %s", (username,)).fetchone()
            existing_user_by_email = db.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone()
            existing_cust_by_cid = db.execute("SELECT 1 FROM customers WHERE connection_id = %s", (connection_id,)).fetchone()
            existing_cust_by_email = db.execute("SELECT 1 FROM customers WHERE email = %s", (email,)).fetchone()

            if existing_cust_by_cid:
                errors.append(f"Connection ID '{connection_id}' is already registered to another account.")
            if existing_user_by_username:
                errors.append(f"Username '{username}' is already taken.")
            if existing_user_by_email or existing_cust_by_email:
                errors.append(f"Email address '{email}' is already registered.")

        if errors:
            return render_template("register.html", plans=plans, errors=errors, form=request.form, next_cid=next_cid)

        plan = db.execute("SELECT * FROM plans WHERE id = %s", (plan_id,)).fetchone()
        today = datetime.now()
        due = today + timedelta(days=plan["validity_days"])

        cur = db.execute(
            "INSERT INTO customers (name, connection_id, email, address, plan_id, start_date, due_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (name, connection_id, email, address, plan_id, today.strftime("%Y-%m-%d"), due.strftime("%Y-%m-%d")),
        )
        new_customer_id = cur.lastrowid

        db.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email, customer_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (username, generate_password_hash(password), "customer", name, email, new_customer_id),
        )
        db.commit()

        # Send welcome email notification strictly to the registrant's email address
        send_welcome_email(email, name, connection_id, plan["name"])

        # Log new customer in automatically
        user = db.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["display_name"] = user["display_name"]
        session["customer_id"] = user["customer_id"]

        # Redirect immediately to customer portal with payment popup modal auto-trigger
        return redirect(url_for("customer_view", customer_id=new_customer_id, show_payment=1))

    return render_template("register.html", plans=plans, errors=[], form={}, next_cid=next_cid)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Usage-based plan recommendation helper
# ---------------------------------------------------------------------------

def get_usage_recommendation(db, customer_id, current_plan_id):
    plans = db.execute("SELECT * FROM plans ORDER BY price ASC").fetchall()
    plan_order = [dict(p) for p in plans]

    cust_plan = next((p for p in plan_order if p["id"] == current_plan_id), plan_order[0])
    idx = next((i for i, p in enumerate(plan_order) if p["id"] == current_plan_id), 0)

    usage_row = db.execute(
        "SELECT COALESCE(SUM(data_consumed), 0) AS total FROM usage_logs WHERE customer_id = %s",
        (customer_id,),
    ).fetchone()
    usage = usage_row["total"] if usage_row else 0

    limit = cust_plan["data_limit_gb"] or 1
    ratio = usage / limit

    recommendation = "No change"
    suggested_plan = None
    reason = f"You're using {round(usage)} GB against your plan's {round(limit)} GB reference limit — comfortably within plan."

    if ratio >= 0.8 and idx + 1 < len(plan_order):
        suggested_plan = plan_order[idx + 1]
        recommendation = "Upgrade"
        reason = (
            f"You're averaging {round(usage)} GB/month, {round(ratio * 100)}% of your "
            f"{cust_plan['name']} limit — you may hit caps or see slower speeds."
        )
    elif ratio <= 0.35 and idx - 1 >= 0:
        suggested_plan = plan_order[idx - 1]
        recommendation = "Downgrade"
        reason = (
            f"You're averaging only {round(usage)} GB/month, {round(ratio * 100)}% of your "
            f"{cust_plan['name']} limit — you could save money on a smaller plan."
        )

    return {
        "usage_gb": round(usage, 1),
        "limit_gb": round(limit),
        "ratio_pct": round(ratio * 100),
        "recommendation": recommendation,
        "suggested_plan": suggested_plan,
        "reason": reason,
        "current_plan_id": current_plan_id,
        "plan_order": plan_order,
    }


# ---------------------------------------------------------------------------
# Routes - pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    role = session.get("role")
    if role == "customer":
        cust_id = session.get("customer_id")
        if cust_id:
            return redirect(url_for("customer_view", customer_id=cust_id))
        return redirect(url_for("login"))
    elif role == "staff":
        return redirect(url_for("expiry_list"))
    return redirect(url_for("admin_dashboard"))


@app.route("/customers")
@login_required(roles=["staff", "admin"])
def customer_lookup():
    db = get_db()
    customers = db.execute(
        """SELECT c.id, c.name, c.connection_id, c.email, p.name AS plan_name
           FROM customers c JOIN plans p ON c.plan_id = p.id ORDER BY c.id DESC"""
    ).fetchall()
    return render_template("customer_select.html", customers=customers)


@app.route("/customer/<int:customer_id>")
@login_required()
def customer_view(customer_id):
    if session["role"] == "customer" and session.get("customer_id") != customer_id:
        abort(403)

    show_payment = request.args.get("show_payment") == "1"
    target_plan_id = request.args.get("target_plan_id")

    db = get_db()
    customer = db.execute(
        """SELECT c.*, p.name AS plan_name, p.speed, p.data_limit, p.price, p.validity_days
           FROM customers c JOIN plans p ON c.plan_id = p.id WHERE c.id = %s""",
        (customer_id,),
    ).fetchone()
    
    if customer is None:
        abort(404)

    target_plan = None
    if target_plan_id:
        target_plan = db.execute("SELECT * FROM plans WHERE id = %s", (target_plan_id,)).fetchone()

    transactions = db.execute(
        "SELECT * FROM transactions WHERE customer_id = %s ORDER BY date DESC LIMIT 10", (customer_id,)
    ).fetchall()

    due_str = str(customer["due_date"])
    due_date_obj = datetime.strptime(due_str, "%Y-%m-%d").date() if isinstance(due_str, str) else due_str
    days_left = (due_date_obj - datetime.now().date()).days

    usage_info = get_usage_recommendation(db, customer_id, customer["plan_id"])
    all_plans = db.execute("SELECT * FROM plans ORDER BY price ASC").fetchall()

    return render_template(
        "customer_view.html",
        customer=customer,
        target_plan=target_plan,
        transactions=transactions,
        days_left=days_left,
        usage_info=usage_info,
        all_plans=all_plans,
        show_payment=show_payment,
    )


@app.route("/change_plan/<int:customer_id>", methods=["POST"])
@login_required()
def change_plan(customer_id):
    if session["role"] == "customer" and session.get("customer_id") != customer_id:
        abort(403)

    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if customer is None:
        abort(404)

    new_plan_id = request.form.get("plan_id")
    plan = db.execute("SELECT * FROM plans WHERE id = %s", (new_plan_id,)).fetchone()
    if plan is None:
        abort(400)

    # Redirect to customer view with target plan to prompt recharge/payment for the new plan
    return redirect(url_for("customer_view", customer_id=customer_id, target_plan_id=plan["id"], show_payment=1))


@app.route("/recharge/<int:customer_id>", methods=["POST"])
@login_required()
def recharge(customer_id):
    if session["role"] == "customer" and session.get("customer_id") != customer_id:
        abort(403)

    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if customer is None:
        abort(404)

    # Determine plan to recharge (use selected plan_id or fallback to customer's current plan_id)
    plan_id = request.form.get("plan_id")
    plan = None
    if plan_id:
        plan = db.execute("SELECT * FROM plans WHERE id = %s", (plan_id,)).fetchone()

    if plan is None:
        plan = db.execute("SELECT * FROM plans WHERE id = %s", (customer["plan_id"],)).fetchone()

    if plan is None:
        plan = db.execute("SELECT * FROM plans ORDER BY id ASC LIMIT 1").fetchone()

    payment_mode = request.form.get("payment_mode", "UPI")
    simulate_fail = request.form.get("simulate_fail") == "on"

    status = "Failed" if simulate_fail else "Success"
    today = datetime.now()
    today_date = today.date()

    cur_due_str = str(customer["due_date"])
    try:
        cur_due_date = datetime.strptime(cur_due_str, "%Y-%m-%d").date()
    except Exception:
        cur_due_date = today_date

    # Extend validity cumulatively: if plan is active, add days onto current due date!
    base_date = cur_due_date if cur_due_date > today_date else today_date
    new_due_date = base_date + timedelta(days=plan["validity_days"])
    new_due_str = new_due_date.strftime("%Y-%m-%d")

    db.execute(
        "INSERT INTO transactions (customer_id, plan_id, amount, payment_mode, date, status) VALUES (%s, %s, %s, %s, %s, %s)",
        (customer_id, plan["id"], plan["price"], payment_mode, today.strftime("%Y-%m-%d"), status),
    )

    if status == "Success":
        # Update plan_id to the newly recharged plan upon payment completion!
        db.execute(
            "UPDATE customers SET plan_id = %s, due_date = %s, followed_up = 0 WHERE id = %s",
            (plan["id"], new_due_str, customer_id),
        )

    db.commit()

    customer_email = customer.get("email")
    if customer_email:
        send_recharge_receipt(
            customer_email,
            customer["name"],
            customer["connection_id"],
            plan["name"],
            plan["price"],
            payment_mode,
            status,
            new_due_str if status == "Success" else cur_due_str,
        )

    return redirect(url_for("customer_view", customer_id=customer_id))


@app.route("/admin/add_plan", methods=["POST"])
@login_required(roles=["admin"])
def add_plan():
    """Allows Admin to permanently create new broadband plans in MySQL database."""
    db = get_db()
    name = request.form.get("name", "").strip()
    speed = request.form.get("speed", "").strip()
    data_limit = request.form.get("data_limit", "").strip()
    try:
        data_limit_gb = float(request.form.get("data_limit_gb", 500))
    except Exception:
        data_limit_gb = 500.0
    try:
        validity_days = int(request.form.get("validity_days", 30))
    except Exception:
        validity_days = 30
    try:
        price = float(request.form.get("price", 0))
    except Exception:
        price = 0.0

    if name and speed and price > 0:
        db.execute(
            "INSERT INTO plans (name, speed, data_limit, data_limit_gb, validity_days, price) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, speed, data_limit, data_limit_gb, validity_days, price),
        )
        db.commit()
        print(f"[Admin] Permanently added new plan: {name} (Rs. {price})")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/add_staff", methods=["POST"])
@login_required(roles=["admin"])
def add_staff():
    """Allows Admin to create new Support Staff / Admin accounts in MySQL."""
    db = get_db()
    display_name = request.form.get("display_name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "staff").strip()

    errors = []
    if not display_name or not username or not email or not password:
        errors.append("All fields are required.")
    elif not re.match(r"^[A-Za-z\s.'-]{2,}$", display_name):
        errors.append("Full Name must contain letters and spaces only.")

    if len(password) < 4:
        errors.append("Password must be at least 4 characters.")

    if not errors:
        existing_username = db.execute("SELECT 1 FROM users WHERE username = %s", (username,)).fetchone()
        existing_email = db.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone()

        if existing_username:
            errors.append(f"Username '{username}' is already taken.")
        if existing_email:
            errors.append(f"Email '{email}' is already registered.")

    if not errors:
        db.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email, customer_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (username, generate_password_hash(password), role, display_name, email, None),
        )
        db.commit()
        print(f"[Admin] Successfully created new {role} user: {username} ({email})")

    return redirect(url_for("admin_dashboard"))


@app.route("/api/staff_list")
@login_required(roles=["admin"])
def api_staff_list():
    db = get_db()
    users = db.execute(
        "SELECT id, username, display_name, email, role FROM users WHERE role IN ('staff', 'admin') ORDER BY id DESC"
    ).fetchall()
    return jsonify(users)


@app.route("/expiry")
@login_required(roles=["staff", "admin"])
def expiry_list():
    db = get_db()
    today = datetime.now().date()
    week = today + timedelta(days=7)
    rows = db.execute(
        """SELECT c.*, p.name AS plan_name, p.price
           FROM customers c JOIN plans p ON c.plan_id = p.id
           WHERE c.due_date BETWEEN %s AND %s
           ORDER BY c.due_date ASC""",
        (today.strftime("%Y-%m-%d"), week.strftime("%Y-%m-%d")),
    ).fetchall()

    enriched = []
    for r in rows:
        due_str = str(r["due_date"])
        due_val = datetime.strptime(due_str, "%Y-%m-%d").date() if isinstance(due_str, str) else due_val
        days_left = (due_val - today).days
        enriched.append({**dict(r), "days_left": days_left})

    return render_template("expiry.html", customers=enriched)


@app.route("/send_all_renewal_alerts", methods=["POST"])
@login_required(roles=["staff", "admin"])
def send_all_renewal_alerts():
    count = check_and_send_7day_renewal_alerts()
    msg = f"Sent 7-day renewal reminder emails to {count} customer(s) nearing expiry!"
    
    db = get_db()
    today = datetime.now().date()
    week = today + timedelta(days=7)
    rows = db.execute(
        """SELECT c.*, p.name AS plan_name, p.price
           FROM customers c JOIN plans p ON c.plan_id = p.id
           WHERE c.due_date BETWEEN %s AND %s
           ORDER BY c.due_date ASC""",
        (today.strftime("%Y-%m-%d"), week.strftime("%Y-%m-%d")),
    ).fetchall()
    enriched = [{**dict(r), "days_left": (datetime.strptime(str(r["due_date"]), "%Y-%m-%d").date() - today).days} for r in rows]

    return render_template("expiry.html", customers=enriched, success_msg=msg)


@app.route("/followup/<int:customer_id>", methods=["POST"])
@login_required(roles=["staff", "admin"])
def followup(customer_id):
    db = get_db()
    db.execute("UPDATE customers SET followed_up = 1 WHERE id = %s", (customer_id,))
    db.commit()

    customer = db.execute(
        """SELECT c.*, p.price FROM customers c JOIN plans p ON c.plan_id = p.id WHERE c.id = %s""",
        (customer_id,),
    ).fetchone()
    if customer and customer.get("email"):
        due_str = str(customer["due_date"])
        due_date_obj = datetime.strptime(due_str, "%Y-%m-%d").date() if isinstance(due_str, str) else due_str
        days_left = (due_date_obj - datetime.now().date()).days
        
        usage_info = get_usage_recommendation(db, customer["id"], customer["plan_id"])
        send_expiry_reminder(
            customer["email"],
            customer["name"],
            customer["connection_id"],
            due_str,
            customer["price"],
            days_left=days_left,
            usage_info=usage_info
        )

    return redirect(url_for("expiry_list"))


@app.route("/admin")
@login_required(roles=["admin"])
def admin_dashboard():
    return render_template("admin.html")


# ---------------------------------------------------------------------------
# Routes - JSON APIs
# ---------------------------------------------------------------------------

@app.route("/api/revenue_trend")
@login_required(roles=["admin"])
def api_revenue_trend():
    db = get_db()
    rows = db.execute(
        """SELECT DATE_FORMAT(date, '%%Y-%%m') AS month, SUM(amount) AS total
           FROM transactions WHERE status = 'Success'
           GROUP BY month ORDER BY month ASC"""
    ).fetchall()
    return jsonify({"labels": [r["month"] for r in rows], "values": [float(r["total"]) for r in rows]})


@app.route("/api/plan_distribution")
@login_required(roles=["admin"])
def api_plan_distribution():
    db = get_db()
    rows = db.execute(
        """SELECT p.name AS plan_name, COUNT(c.id) AS subscribers
           FROM plans p LEFT JOIN customers c ON c.plan_id = p.id
           GROUP BY p.id, p.name"""
    ).fetchall()
    return jsonify({"labels": [r["plan_name"] for r in rows], "values": [int(r["subscribers"]) for r in rows]})


@app.route("/api/renewal_rate")
@login_required(roles=["admin"])
def api_renewal_rate():
    db = get_db()
    total = db.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"]
    success = db.execute("SELECT COUNT(*) AS n FROM transactions WHERE status = 'Success'").fetchone()["n"]
    failed = total - success
    return jsonify({"labels": ["Renewed", "Lapsed / Failed"], "values": [int(success), int(failed)]})


@app.route("/api/summary")
@login_required(roles=["admin"])
def api_summary():
    db = get_db()
    total_revenue = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM transactions WHERE status = 'Success'"
    ).fetchone()["t"]
    total_customers = db.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
    total = db.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"]
    success = db.execute("SELECT COUNT(*) AS n FROM transactions WHERE status = 'Success'").fetchone()["n"]
    recovery_rate = round((success / total) * 100, 1) if total else 0
    today = datetime.now().date()
    week = today + timedelta(days=7)
    nearing = db.execute(
        "SELECT COUNT(*) AS n FROM customers WHERE due_date BETWEEN %s AND %s",
        (today.strftime("%Y-%m-%d"), week.strftime("%Y-%m-%d")),
    ).fetchone()["n"]
    return jsonify(
        {
            "total_revenue": float(total_revenue),
            "total_customers": int(total_customers),
            "recovery_rate": float(recovery_rate),
            "nearing_expiry": int(nearing),
        }
    )


@app.route("/api/plan_recommendations")
@login_required(roles=["admin"])
def api_plan_recommendations():
    db = get_db()
    customers = db.execute(
        """SELECT c.id, c.name, c.connection_id, c.plan_id, p.name AS plan_name
           FROM customers c JOIN plans p ON c.plan_id = p.id"""
    ).fetchall()

    results = []
    for cust in customers:
        info = get_usage_recommendation(db, cust["id"], cust["plan_id"])
        results.append(
            {
                "customer": cust["name"],
                "connection_id": cust["connection_id"],
                "current_plan": cust["plan_name"],
                "monthly_usage_gb": info["usage_gb"],
                "recommendation": info["recommendation"],
                "suggested_plan": info["suggested_plan"]["name"] if info["suggested_plan"] else None,
                "reason": info["reason"],
            }
        )

    return jsonify(results)


if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        print("Initial database setup skipped due to connection error. App starting...")
    app.run(host="0.0.0.0", port=5000, debug=True)
