# NetPulse — Broadband Recharge & Revenue Intelligence Platform

A Flask + **MySQL** web platform for broadband subscription management, revenue analytics, customer recharges, and usage intelligence.

## Features

1. **Customer recharge & billing history** — view current plan and due date, recharge online (with a "simulate failed payment" toggle for demo), and see the last 10 transactions.
2. **Staff follow-up queue** — customers whose plan expires within 7 days, with a one-click "Mark Followed Up" action, plus a customer lookup for manual recharge.
3. **Admin revenue dashboard** — total revenue, customer count, payment recovery rate, and customers nearing expiry as stat cards, plus three Chart.js visualizations: monthly revenue trend, plan-wise subscriber distribution, and renewal vs. lapse rate.
4. **Plan upgrade/downgrade recommendations** — on the admin dashboard, each customer's average monthly data usage is compared against their current plan's data limit. Customers using ≥80% of their limit are flagged to **upgrade**; customers using ≤35% are flagged to **downgrade**; everyone else is "right-sized." Served by `/api/plan_recommendations`.
5. **Self-service registration** — new customers can create their own account and connection at `/register` (name, connection ID, address, plan choice, username, password), and are logged straight in afterward.

All chart/recommendation data is served through JSON API endpoints (`/api/summary`, `/api/revenue_trend`, `/api/plan_distribution`, `/api/renewal_rate`, `/api/plan_recommendations`).

## Tech Stack

- **Backend:** Python, Flask, PyMySQL
- **Database:** MySQL 8.0+ (connected via PyMySQL & dotenv configuration)
- **Frontend:** HTML5, CSS3, Jinja2 templates, Bootstrap 5, Chart.js
- **Auth:** Session-based login with hashed passwords (`Werkzeug`). Role-based access control (`customer`, `staff`, `admin`).

### Demo credentials (seeded automatically)

| Role     | Username | Password  | Sees                                   |
|----------|----------|-----------|-----------------------------------------|
| Customer | `BB-1001`| `pass123` | Only their own plan, due date, billing  |
| Staff    | `staff`  | `staff123`| Follow-up queue + any customer lookup   |
| Admin    | `admin`  | `admin123`| Everything, incl. the revenue dashboard |

Every seeded customer (`BB-1001` … `BB-1006`) has a login with password `pass123`.

## MySQL Database Configuration

Configuration settings are loaded automatically from `.env`:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=broadband_db
```

### Running the Application

```bash
pip install -r requirements.txt
python app.py
```

`init_db()` automatically connects to your MySQL server, creates the `broadband_db` database if missing, creates tables (`plans`, `customers`, `transactions`, `usage_logs`, `users`), and seeds standard demo data.

Visit `http://localhost:5000` in your browser.
