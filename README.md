# 📡 NetPulse — Broadband Recharge & Revenue Intelligence Platform

**NetPulse** is a web-based broadband management platform built with **Python Flask and MySQL**. It helps broadband providers manage customers, subscriptions, recharges, billing history, follow-ups, revenue analytics, and customer plan recommendations from a single dashboard.

The platform provides separate experiences for **Customers, Staff, and Administrators**, making it easier to manage the complete broadband subscription lifecycle.

---

## 🚀 Features

### 👤 Customer Portal

* Customer login and authentication
* View current broadband plan
* View subscription expiry/due date
* View billing and recharge history
* Recharge broadband plans
* Simulated payment failure option for demonstration
* View recent transactions
* Self-service customer registration
* Select a broadband plan during registration

### 👨‍💼 Staff Management

* Staff login
* View customers whose plans are expiring soon
* Follow-up queue for customer renewals
* Mark customers as followed up
* Search customers by connection/customer details
* Perform manual customer recharge

### 📊 Admin Dashboard

* Total revenue overview
* Total customer count
* Payment recovery rate
* Customers approaching plan expiry
* Monthly revenue analytics
* Plan-wise subscriber distribution
* Renewal vs. lapse analysis
* Customer usage intelligence
* Plan upgrade/downgrade recommendations

### 🧠 Intelligent Plan Recommendations

NetPulse analyzes customer data usage against their current plan limit.

* **80% or more usage** → Recommended to upgrade
* **35% or less usage** → Recommended to downgrade
* **Between 35% and 80%** → Plan is considered right-sized

Recommendations are available through the:

```text
/api/plan_recommendations
```

---

## 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │      NetPulse        │
                    │   Broadband Platform │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │  Customer  │   │   Staff    │   │   Admin    │
       │   Portal   │   │  Dashboard │   │  Dashboard │
       └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                    ┌──────────────────┐
                    │   Flask Backend  │
                    │   Python + API   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   MySQL Database │
                    │                  │
                    │ • Customers      │
                    │ • Plans          │
                    │ • Transactions   │
                    │ • Usage Logs     │
                    │ • Users          │
                    └──────────────────┘
```

---

## 🛠️ Tech Stack

### Backend

* **Python**
* **Flask**
* **PyMySQL**
* **python-dotenv**
* **Werkzeug**

### Frontend

* **HTML5**
* **CSS3**
* **Bootstrap 5**
* **Jinja2**
* **Chart.js**
* JavaScript

### Database

* **MySQL 8.0+**

### Authentication & Security

* Session-based authentication
* Password hashing using Werkzeug
* Role-based access control

Supported roles:

```text
Customer
Staff
Admin
```

---

## 📁 Project Structure

```text
netpulse-broadband-platform/
│
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── schema.sql              # Database schema
├── .env.example            # Environment configuration template
├── .gitignore
│
├── certs/                  # SSL/certificate files
│
├── static/                 # CSS, JavaScript and static assets
│
└── templates/              # Jinja2 HTML templates
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/lokeshwar5221/netpulse-broadband-platform.git
```

Navigate into the project:

```bash
cd netpulse-broadband-platform
```

---

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

On Linux/macOS:

```bash
source venv/bin/activate
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🗄️ MySQL Configuration

Make sure **MySQL 8.0 or later** is installed and running.

Create a `.env` file in the project root:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=broadband_db
```

> **Important:** Never commit your real `.env` file or database password to GitHub.

The application automatically initializes the database and creates the required tables when it starts.

---

## ▶️ Running the Application

Start the Flask application:

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

The application automatically creates the required database structure and seeds demo data.

---

## 🔐 Demo Credentials

| Role     | Username  | Password   |
| -------- | --------- | ---------- |
| Customer | `BB-1001` | `pass123`  |
| Staff    | `staff`   | `staff123` |
| Admin    | `admin`   | `admin123` |

Seeded customers from `BB-1001` to `BB-1006` use:

```text
Password: pass123
```

> These credentials are intended for local development and demonstration only. Change them before deploying the application to a production environment.

---

## 🔌 API Endpoints

NetPulse provides JSON APIs for dashboard analytics and recommendations.

| Endpoint                    | Description                     |
| --------------------------- | ------------------------------- |
| `/api/summary`              | Overall platform statistics     |
| `/api/revenue_trend`        | Monthly revenue data            |
| `/api/plan_distribution`    | Subscriber distribution by plan |
| `/api/renewal_rate`         | Renewal and lapse statistics    |
| `/api/plan_recommendations` | Customer plan recommendations   |

---

## 📈 Analytics Dashboard

The Admin Dashboard uses **Chart.js** to visualize important broadband business metrics, including:

* Monthly revenue trends
* Subscriber distribution by broadband plan
* Renewal and lapse rates
* Customer usage patterns
* Plan optimization opportunities

This helps administrators understand both **financial performance** and **customer subscription behavior**.

---

## 🔄 Application Workflow

```text
Customer Registration
        ↓
Select Broadband Plan
        ↓
Account & Connection Created
        ↓
Customer Uses Broadband Service
        ↓
Usage Data Recorded
        ↓
Recharge / Renewal
        ↓
Revenue & Usage Analytics
        ↓
Plan Recommendation
        ↓
Upgrade / Downgrade / Right-size
```

---

## 🎯 Project Objectives

NetPulse was designed to address common challenges faced by broadband service providers:

* Managing broadband customers efficiently
* Tracking subscription expiry dates
* Improving customer renewal rates
* Simplifying recharge and billing operations
* Providing staff with actionable follow-up information
* Visualizing business revenue and subscriber data
* Identifying customers who may need a different broadband plan
* Reducing manual subscription management

---

## 🔮 Future Enhancements

Possible future improvements include:

* 💳 Real payment gateway integration
* 📱 Mobile application for customers
* 📩 SMS and email renewal notifications
* 🔔 Automated expiry reminders
* 📊 Advanced customer analytics
* 🤖 Machine-learning-based plan recommendations
* 🧾 Automated invoice generation
* 📈 Real-time broadband usage monitoring
* 🔐 Two-factor authentication
* ☁️ Cloud deployment
* 🐳 Docker support
* 📡 Integration with ISP/network monitoring systems

---

## 🔒 Security Notes

For production deployment:

* Use strong database credentials
* Keep `.env` out of version control
* Use HTTPS
* Change all demo passwords
* Configure secure Flask session settings
* Enable proper database access controls
* Validate and sanitize user input
* Use production-grade deployment such as Gunicorn/Nginx

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a new branch

```bash
git checkout -b feature/your-feature
```

3. Make your changes
4. Commit your changes

```bash
git commit -m "Add new feature"
```

5. Push the branch

```bash
git push origin feature/your-feature
```

6. Open a Pull Request

---

## 📄 License

This project is available for educational and development purposes.

---

## 👨‍💻 Author

**Lokeshwar**

GitHub:
https://github.com/lokeshwar5221

Project Repository:
https://github.com/lokeshwar5221/netpulse-broadband-platform

---

## ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.

**NetPulse — Making Broadband Subscription Management Smarter, Simpler, and More Data-Driven.**
