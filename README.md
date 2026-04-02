# 💊 MediCare - Pharmacy Management System
## Built with Flask & SQLite

Link :https://pro-pharmacy-project.onrender.com/login

---

## 🚀 Features
- ✅ Login/Signup with role-based access (Admin, Pharmacist)
- ✅ Dashboard with sales charts & alerts
- ✅ Medicine inventory management
- ✅ Category & Supplier management
- ✅ Billing with PDF invoice generation
- ✅ Customer management & purchase history
- ✅ Purchase Order management (with stock auto-update)
- ✅ Reports: Sales, Top medicines, Expiry, Low stock
- ✅ Expiry date & Low stock alerts
- ✅ User management (Admin only)

---

## ⚙️ Setup Instructions

### Step 1: Install Python
Make sure Python 3.8+ is installed.

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the App
```bash
python app.py
```

### Step 4: Open in Browser
```
http://localhost:5000
```

---

## 🔐 Default Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Pharmacist | `pharmacist` | `pharm123` |

---

## 📁 Project Structure
```
pharmacy_app/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── pharmacy.db         # SQLite database (auto-created)
├── static/
│   ├── css/            # Custom styles
│   └── uploads/        # Uploaded prescriptions
└── templates/
    ├── base.html           # Base layout with sidebar
    ├── login.html          # Login page
    ├── dashboard.html      # Dashboard
    ├── medicines.html      # Medicine list
    ├── add_medicine.html   # Add medicine form
    ├── edit_medicine.html  # Edit medicine form
    ├── billing.html        # Bills list
    ├── new_bill.html       # Create new bill
    ├── bill_detail.html    # Bill details + PDF
    ├── customers.html      # Customer list
    ├── customer_detail.html # Customer profile
    ├── add_customer.html   # Add customer
    ├── suppliers.html      # Suppliers list
    ├── add_supplier.html   # Add supplier
    ├── edit_supplier.html  # Edit supplier
    ├── categories.html     # Categories
    ├── purchase_orders.html # Purchase orders
    ├── add_purchase_order.html # New PO
    ├── reports.html        # Reports & analytics
    ├── users.html          # User management
    └── add_user.html       # Add user
```

---

## 🎯 Tech Stack
- **Backend:** Python Flask
- **Database:** SQLite (via SQLAlchemy ORM)
- **Frontend:** Bootstrap 5, Chart.js, Font Awesome
- **PDF:** ReportLab
- **Font:** Plus Jakarta Sans (Google Fonts)

---

Made with ❤️ for TY IT Project
