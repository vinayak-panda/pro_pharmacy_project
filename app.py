from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from functools import wraps
import os
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pharmacy_secret_key_2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///pharmacy.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/prescriptions'

db = SQLAlchemy(app)

# ===================== MODELS =====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, pharmacist, customer
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    medicines = db.relationship('Medicine', backref='category', lazy=True)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    medicines = db.relationship('Medicine', backref='supplier', lazy=True)

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    generic_name = db.Column(db.String(150))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    batch_number = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(30), default='tablets')
    purchase_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    expiry_date = db.Column(db.Date)
    low_stock_threshold = db.Column(db.Integer, default=10)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False

    @property
    def is_expiring_soon(self):
        if self.expiry_date:
            return date.today() <= self.expiry_date <= date.today() + timedelta(days=30)
        return False

    @property
    def is_low_stock(self):
        return self.quantity <= self.low_stock_threshold

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bills = db.relationship('Bill', backref='customer', lazy=True)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    customer_name = db.Column(db.String(100))
    subtotal = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(30), default='cash')
    prescription_file = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('BillItem', backref='bill', lazy=True)

class BillItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'))
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'))
    medicine_name = db.Column(db.String(150))
    quantity = db.Column(db.Integer)
    unit_price = db.Column(db.Float)
    total_price = db.Column(db.Float)
    medicine = db.relationship('Medicine')

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    total_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), default='pending')  # pending, received, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship('Supplier')
    items = db.relationship('PurchaseOrderItem', backref='order', lazy=True)

class PurchaseOrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'))
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'))
    medicine_name = db.Column(db.String(150))
    quantity = db.Column(db.Integer)
    unit_price = db.Column(db.Float)
    total_price = db.Column(db.Float)
    medicine = db.relationship('Medicine')

# ===================== HELPERS =====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') not in ['admin']:
            flash('Access denied!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def generate_bill_number():
    last = Bill.query.order_by(Bill.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"BILL-{datetime.now().strftime('%Y%m')}-{num:04d}"

def generate_order_number():
    last = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"PO-{datetime.now().strftime('%Y%m')}-{num:04d}"

# ===================== ROUTES =====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['full_name'] = user.full_name
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_medicines = Medicine.query.count()
    total_customers = Customer.query.count()
    total_suppliers = Supplier.query.count()

    today = date.today()
    today_bills = Bill.query.filter(db.func.date(Bill.created_at) == today).all()
    today_sales = sum(b.total for b in today_bills)

    month_start = today.replace(day=1)
    month_bills = Bill.query.filter(db.func.date(Bill.created_at) >= month_start).all()
    month_sales = sum(b.total for b in month_bills)

    expired = Medicine.query.filter(Medicine.expiry_date < today).count()
    expiring_soon = Medicine.query.filter(
        Medicine.expiry_date >= today,
        Medicine.expiry_date <= today + timedelta(days=30)
    ).count()

    low_stock = Medicine.query.filter(Medicine.quantity <= Medicine.low_stock_threshold).count()

    recent_bills = Bill.query.order_by(Bill.created_at.desc()).limit(5).all()
    
    # Monthly sales chart data
    monthly_data = []
    for i in range(6):
        m_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        m_end = (m_start + timedelta(days=32)).replace(day=1)
        bills = Bill.query.filter(
            db.func.date(Bill.created_at) >= m_start,
            db.func.date(Bill.created_at) < m_end
        ).all()
        monthly_data.append({
            'month': m_start.strftime('%b %Y'),
            'sales': sum(b.total for b in bills)
        })
    monthly_data.reverse()

    return render_template('dashboard.html',
        total_medicines=total_medicines,
        total_customers=total_customers,
        total_suppliers=total_suppliers,
        today_sales=today_sales,
        month_sales=month_sales,
        today_bills=len(today_bills),
        expired=expired,
        expiring_soon=expiring_soon,
        low_stock=low_stock,
        recent_bills=recent_bills,
        monthly_data=monthly_data
    )

# ---- MEDICINES ----
@app.route('/medicines')
@login_required
def medicines():
    search = request.args.get('search', '')
    category_id = request.args.get('category', '')
    filter_type = request.args.get('filter', '')
    
    query = Medicine.query
    if search:
        query = query.filter(Medicine.name.ilike(f'%{search}%'))
    if category_id:
        query = query.filter_by(category_id=category_id)
    today = date.today()
    if filter_type == 'expired':
        query = query.filter(Medicine.expiry_date < today)
    elif filter_type == 'expiring':
        query = query.filter(Medicine.expiry_date >= today, Medicine.expiry_date <= today + timedelta(days=30))
    elif filter_type == 'low_stock':
        query = query.filter(Medicine.quantity <= Medicine.low_stock_threshold)
    
    medicines = query.order_by(Medicine.name).all()
    categories = Category.query.all()
    return render_template('medicines.html', medicines=medicines, categories=categories)

@app.route('/medicines/add', methods=['GET', 'POST'])
@login_required
def add_medicine():
    if request.method == 'POST':
        med = Medicine(
            name=request.form['name'],
            generic_name=request.form.get('generic_name'),
            category_id=request.form.get('category_id') or None,
            supplier_id=request.form.get('supplier_id') or None,
            batch_number=request.form.get('batch_number'),
            quantity=int(request.form['quantity']),
            unit=request.form.get('unit', 'tablets'),
            purchase_price=float(request.form['purchase_price']),
            selling_price=float(request.form['selling_price']),
            expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form.get('expiry_date') else None,
            low_stock_threshold=int(request.form.get('low_stock_threshold', 10)),
            description=request.form.get('description')
        )
        db.session.add(med)
        db.session.commit()
        flash('Medicine added successfully!', 'success')
        return redirect(url_for('medicines'))
    categories = Category.query.all()
    suppliers = Supplier.query.all()
    return render_template('add_medicine.html', categories=categories, suppliers=suppliers)

@app.route('/medicines/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_medicine(id):
    med = Medicine.query.get_or_404(id)
    if request.method == 'POST':
        med.name = request.form['name']
        med.generic_name = request.form.get('generic_name')
        med.category_id = request.form.get('category_id') or None
        med.supplier_id = request.form.get('supplier_id') or None
        med.batch_number = request.form.get('batch_number')
        med.quantity = int(request.form['quantity'])
        med.unit = request.form.get('unit', 'tablets')
        med.purchase_price = float(request.form['purchase_price'])
        med.selling_price = float(request.form['selling_price'])
        med.expiry_date = datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form.get('expiry_date') else None
        med.low_stock_threshold = int(request.form.get('low_stock_threshold', 10))
        med.description = request.form.get('description')
        db.session.commit()
        flash('Medicine updated!', 'success')
        return redirect(url_for('medicines'))
    categories = Category.query.all()
    suppliers = Supplier.query.all()
    return render_template('edit_medicine.html', medicine=med, categories=categories, suppliers=suppliers)

@app.route('/medicines/delete/<int:id>')
@admin_required
def delete_medicine(id):
    med = Medicine.query.get_or_404(id)
    db.session.delete(med)
    db.session.commit()
    flash('Medicine deleted!', 'success')
    return redirect(url_for('medicines'))

@app.route('/api/medicine/<int:id>')
@login_required
def get_medicine_api(id):
    med = Medicine.query.get_or_404(id)
    return jsonify({
        'id': med.id, 'name': med.name, 'quantity': med.quantity,
        'selling_price': med.selling_price, 'unit': med.unit
    })

@app.route('/api/medicines/search')
@login_required
def search_medicines_api():
    q = request.args.get('q', '')
    meds = Medicine.query.filter(Medicine.name.ilike(f'%{q}%'), Medicine.quantity > 0).limit(10).all()
    return jsonify([{'id': m.id, 'name': m.name, 'price': m.selling_price, 'qty': m.quantity, 'unit': m.unit} for m in meds])

# ---- CATEGORIES ----
@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        cat = Category(name=request.form['name'], description=request.form.get('description'))
        db.session.add(cat)
        db.session.commit()
        flash('Category added!', 'success')
    cats = Category.query.all()
    return render_template('categories.html', categories=cats)

@app.route('/categories/delete/<int:id>')
@admin_required
def delete_category(id):
    cat = Category.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted!', 'success')
    return redirect(url_for('categories'))

# ---- SUPPLIERS ----
@app.route('/suppliers')
@login_required
def suppliers():
    sups = Supplier.query.all()
    return render_template('suppliers.html', suppliers=sups)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        sup = Supplier(
            name=request.form['name'],
            contact_person=request.form.get('contact_person'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address')
        )
        db.session.add(sup)
        db.session.commit()
        flash('Supplier added!', 'success')
        return redirect(url_for('suppliers'))
    return render_template('add_supplier.html')

@app.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(id):
    sup = Supplier.query.get_or_404(id)
    if request.method == 'POST':
        sup.name = request.form['name']
        sup.contact_person = request.form.get('contact_person')
        sup.email = request.form.get('email')
        sup.phone = request.form.get('phone')
        sup.address = request.form.get('address')
        db.session.commit()
        flash('Supplier updated!', 'success')
        return redirect(url_for('suppliers'))
    return render_template('edit_supplier.html', supplier=sup)

@app.route('/suppliers/delete/<int:id>')
@admin_required
def delete_supplier(id):
    sup = Supplier.query.get_or_404(id)
    db.session.delete(sup)
    db.session.commit()
    flash('Supplier deleted!', 'success')
    return redirect(url_for('suppliers'))

# ---- CUSTOMERS ----
@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '')
    query = Customer.query
    if search:
        query = query.filter(Customer.name.ilike(f'%{search}%'))
    custs = query.order_by(Customer.name).all()
    return render_template('customers.html', customers=custs)

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        cust = Customer(
            name=request.form['name'],
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address')
        )
        db.session.add(cust)
        db.session.commit()
        flash('Customer added!', 'success')
        return redirect(url_for('customers'))
    return render_template('add_customer.html')

@app.route('/customers/<int:id>')
@login_required
def customer_detail(id):
    cust = Customer.query.get_or_404(id)
    bills = Bill.query.filter_by(customer_id=id).order_by(Bill.created_at.desc()).all()
    total_spent = sum(b.total for b in bills)
    return render_template('customer_detail.html', customer=cust, bills=bills, total_spent=total_spent)

# ---- BILLING ----
@app.route('/billing')
@login_required
def billing():
    bills = Bill.query.order_by(Bill.created_at.desc()).all()
    return render_template('billing.html', bills=bills)

@app.route('/billing/new', methods=['GET', 'POST'])
@login_required
def new_bill():
    if request.method == 'POST':
        data = request.get_json()
        bill = Bill(
            bill_number=generate_bill_number(),
            customer_id=data.get('customer_id') or None,
            customer_name=data.get('customer_name', 'Walk-in Customer'),
            subtotal=data['subtotal'],
            discount=data.get('discount', 0),
            tax=data.get('tax', 0),
            total=data['total'],
            payment_method=data.get('payment_method', 'cash'),
            created_by=session['user_id']
        )
        db.session.add(bill)
        db.session.flush()

        for item in data['items']:
            med = Medicine.query.get(item['medicine_id'])
            if med and med.quantity >= item['quantity']:
                bi = BillItem(
                    bill_id=bill.id,
                    medicine_id=item['medicine_id'],
                    medicine_name=item['medicine_name'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    total_price=item['total_price']
                )
                db.session.add(bi)
                med.quantity -= item['quantity']
            else:
                db.session.rollback()
                return jsonify({'error': f'Insufficient stock for {item["medicine_name"]}'}), 400

        db.session.commit()
        return jsonify({'success': True, 'bill_id': bill.id, 'bill_number': bill.bill_number})

    customers = Customer.query.order_by(Customer.name).all()
    return render_template('new_bill.html', customers=customers)

@app.route('/billing/<int:id>')
@login_required
def bill_detail(id):
    bill = Bill.query.get_or_404(id)
    return render_template('bill_detail.html', bill=bill)

@app.route('/billing/<int:id>/pdf')
@login_required
def bill_pdf(id):
    bill = Bill.query.get_or_404(id)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('title', fontSize=20, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a5276'), spaceAfter=6)
    header_style = ParagraphStyle('header', fontSize=10, fontName='Helvetica', textColor=colors.grey)
    
    elements.append(Paragraph("Medicine House", title_style))
    elements.append(Paragraph("Your Health, Our Priority | Ph: +91-9999999999", header_style))
    elements.append(Spacer(1, 15))
    
    info_data = [
        ['Bill Number:', bill.bill_number, 'Date:', bill.created_at.strftime('%d-%m-%Y %H:%M')],
        ['Customer:', bill.customer_name, 'Payment:', bill.payment_method.upper()],
    ]
    info_table = Table(info_data, colWidths=[1.2*inch, 2.3*inch, 1.2*inch, 2.3*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    table_data = [['#', 'Medicine', 'Qty', 'Unit Price', 'Total']]
    for i, item in enumerate(bill.items, 1):
        table_data.append([
            str(i), item.medicine_name, str(item.quantity),
            f'Rs. {item.unit_price:.2f}', f'Rs. {item.total_price:.2f}'
        ])
    
    table_data.append(['', '', '', 'Subtotal:', f'Rs. {bill.subtotal:.2f}'])
    table_data.append(['', '', '', 'Discount:', f'Rs. {bill.discount:.2f}'])
    table_data.append(['', '', '', 'Tax (GST):', f'Rs. {bill.tax:.2f}'])
    table_data.append(['', '', '', 'TOTAL:', f'Rs. {bill.total:.2f}'])

    t = Table(table_data, colWidths=[0.4*inch, 3.2*inch, 0.8*inch, 1.4*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-5), [colors.white, colors.HexColor('#eaf2ff')]),
        ('GRID', (0,0), (-1,-5), 0.5, colors.lightgrey),
        ('FONTNAME', (3,-4), (3,-1), 'Helvetica-Bold'),
        ('FONTNAME', (4,-1), (4,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (4,-1), (4,-1), 11),
        ('TEXTCOLOR', (3,-1), (4,-1), colors.HexColor('#1a5276')),
        ('LINEABOVE', (3,-4), (4,-4), 1, colors.grey),
        ('LINEABOVE', (3,-1), (4,-1), 2, colors.HexColor('#1a5276')),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Thank you for choosing Medicine House!", ParagraphStyle('thanks', fontSize=10, fontName='Helvetica-Oblique', textColor=colors.grey, alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=bill_{bill.bill_number}.pdf'
    return response

# ---- PURCHASE ORDERS ----
@app.route('/purchase-orders')
@login_required
def purchase_orders():
    orders = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('purchase_orders.html', orders=orders)

@app.route('/purchase-orders/add', methods=['GET', 'POST'])
@login_required
def add_purchase_order():
    if request.method == 'POST':
        data = request.get_json()
        po = PurchaseOrder(
            order_number=generate_order_number(),
            supplier_id=data['supplier_id'],
            total_amount=data['total_amount'],
            notes=data.get('notes', '')
        )
        db.session.add(po)
        db.session.flush()
        for item in data['items']:
            poi = PurchaseOrderItem(
                order_id=po.id,
                medicine_id=item['medicine_id'],
                medicine_name=item['medicine_name'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total_price=item['total_price']
            )
            db.session.add(poi)
        db.session.commit()
        return jsonify({'success': True, 'order_id': po.id})
    suppliers = Supplier.query.all()
    medicines = Medicine.query.all()
    return render_template('add_purchase_order.html', suppliers=suppliers, medicines=medicines)

@app.route('/purchase-orders/<int:id>/receive')
@login_required
def receive_order(id):
    order = PurchaseOrder.query.get_or_404(id)
    if order.status == 'pending':
        for item in order.items:
            med = Medicine.query.get(item.medicine_id)
            if med:
                med.quantity += item.quantity
        order.status = 'received'
        db.session.commit()
        flash('Order received! Stock updated.', 'success')
    return redirect(url_for('purchase_orders'))

@app.route('/purchase-orders/<int:id>/cancel')
@login_required
def cancel_order(id):
    order = PurchaseOrder.query.get_or_404(id)
    order.status = 'cancelled'
    db.session.commit()
    flash('Order cancelled.', 'warning')
    return redirect(url_for('purchase_orders'))

# ---- REPORTS ----
@app.route('/reports')
@login_required
def reports():
    today = date.today()
    period = request.args.get('period', 'today')
    
    if period == 'today':
        start = today
    elif period == 'week':
        start = today - timedelta(days=7)
    elif period == 'month':
        start = today.replace(day=1)
    else:
        start = today.replace(month=1, day=1)

    bills = Bill.query.filter(db.func.date(Bill.created_at) >= start).all()
    total_revenue = sum(b.total for b in bills)
    total_bills = len(bills)
    
    # Top selling medicines
    from sqlalchemy import func
    top_medicines = db.session.query(
        BillItem.medicine_name,
        func.sum(BillItem.quantity).label('total_qty'),
        func.sum(BillItem.total_price).label('total_revenue')
    ).join(Bill).filter(db.func.date(Bill.created_at) >= start).group_by(BillItem.medicine_name).order_by(func.sum(BillItem.total_price).desc()).limit(10).all()

    expiry_report = Medicine.query.filter(
        Medicine.expiry_date <= today + timedelta(days=60)
    ).order_by(Medicine.expiry_date).all()

    low_stock_report = Medicine.query.filter(Medicine.quantity <= Medicine.low_stock_threshold).all()

    return render_template('reports.html',
        period=period, bills=bills,
        total_revenue=total_revenue, total_bills=total_bills,
        top_medicines=top_medicines,
        expiry_report=expiry_report,
        low_stock_report=low_stock_report
    )

# ---- USERS ----
@app.route('/users')
@admin_required
def users():
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        u = User(
            username=request.form['username'],
            password=hash_password(request.form['password']),
            role=request.form['role'],
            full_name=request.form['full_name'],
            email=request.form.get('email'),
            phone=request.form.get('phone')
        )
        db.session.add(u)
        db.session.commit()
        flash('User added!', 'success')
        return redirect(url_for('users'))
    return render_template('add_user.html')

@app.route('/users/delete/<int:id>')
@admin_required
def delete_user(id):
    u = User.query.get_or_404(id)
    if u.id == session['user_id']:
        flash("Can't delete yourself!", 'danger')
        return redirect(url_for('users'))
    db.session.delete(u)
    db.session.commit()
    flash('User deleted!', 'success')
    return redirect(url_for('users'))

# ===================== INIT DB =====================
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=hash_password('admin123'),
                        role='admin', full_name='Administrator', email='admin@pharmacy.com')
            pharmacist = User(username='pharmacist', password=hash_password('pharm123'),
                            role='pharmacist', full_name='John Pharmacist')
            db.session.add_all([admin, pharmacist])

            cats = ['Tablets', 'Syrups', 'Injections', 'Capsules', 'Ointments', 'Drops', 'Vitamins']
            cat_objs = [Category(name=c) for c in cats]
            db.session.add_all(cat_objs)

            sup = Supplier(name='MedSupply Co.', contact_person='Ramesh Kumar',
                          phone='9876543210', email='supply@medsupply.com',
                          address='Mumbai, Maharashtra')
            db.session.add(sup)
            db.session.flush()

            medicines_data = [
                ('Paracetamol 500mg', 'Paracetamol', 1, sup.id, 'B001', 200, 'tablets', 2.5, 5.0, date(2026, 6, 30)),
                ('Amoxicillin 250mg', 'Amoxicillin', 1, sup.id, 'B002', 150, 'capsules', 8.0, 15.0, date(2026, 3, 15)),
                ('Cough Syrup', 'Dextromethorphan', 2, sup.id, 'B003', 80, 'bottles', 25.0, 55.0, date(2027, 1, 1)),
                ('Vitamin C 1000mg', 'Ascorbic Acid', 7, sup.id, 'B004', 5, 'tablets', 3.0, 8.0, date(2027, 6, 1)),
                ('Ibuprofen 400mg', 'Ibuprofen', 1, sup.id, 'B005', 300, 'tablets', 3.5, 7.0, date(2026, 12, 31)),
                ('Antacid Syrup', 'Magnesium Hydroxide', 2, sup.id, 'B006', 60, 'bottles', 20.0, 45.0, date(2025, 12, 1)),
            ]
            for m in medicines_data:
                med = Medicine(name=m[0], generic_name=m[1], category_id=m[2], supplier_id=m[3],
                             batch_number=m[4], quantity=m[5], unit=m[6],
                             purchase_price=m[7], selling_price=m[8], expiry_date=m[9])
                db.session.add(med)

            cust = Customer(name='Rajesh Sharma', phone='9898989898', email='rajesh@gmail.com', address='Andheri, Mumbai')
            db.session.add(cust)
            db.session.commit()
            print("✅ Database initialized with demo data!")

# Initialize DB on startup (works with gunicorn too)
init_db()

if __name__ == '__main__':
    init_db()
    app.run(debug=False)
