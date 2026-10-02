from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import pandas as pd
from io import BytesIO

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('accounting_system.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    
    # Kunin ang napiling buwan/taon filter kung meron man (format: YYYY-MM)
    selected_month = request.args.get('month', '')

    # 1. Daily Inputs query (May optional filter para sa monthly report)
    if selected_month:
        daily_data = conn.execute("SELECT * FROM daily_inputs WHERE liquidation_date LIKE ? ORDER BY liquidation_date DESC", (selected_month + '%',)).fetchall()
        # Summary by Account Title para sa Daily Report
        daily_summary = conn.execute("""
            SELECT account_title, SUM(amount) as total_amount, SUM(vatable) as total_vatable, SUM(input_tax) as total_tax 
            FROM daily_inputs WHERE liquidation_date LIKE ? 
            GROUP BY account_title
        """, (selected_month + '%',)).fetchall()
    else:
        daily_data = conn.execute("SELECT * FROM daily_inputs ORDER BY liquidation_date DESC").fetchall()
        daily_summary = conn.execute("""
            SELECT account_title, SUM(amount) as total_amount, SUM(vatable) as total_vatable, SUM(input_tax) as total_tax 
            FROM daily_inputs 
            GROUP BY account_title
        """).fetchall()

    # 2. Sellers Data
    sellers = conn.execute('SELECT * FROM sellers').fetchall()
    seller_data = []
    for s in sellers:
        last_tx = conn.execute('SELECT balance FROM seller_ledger WHERE seller_id = ? ORDER BY id DESC LIMIT 1', (s['id'],)).fetchone()
        balance = last_tx['balance'] if last_tx else s['tcp']
        seller_data.append({
            'id': s['id'],
            'seller_name': s['seller_name'],
            'project_name': s['project_name'],
            'tcp': s['tcp'],
            'balance': balance
        })

    if selected_month:
        ledger_history = conn.execute('''
            SELECT sl.*, s.seller_name, s.project_name, s.tcp 
            FROM seller_ledger sl 
            JOIN sellers s ON sl.seller_id = s.id
            WHERE sl.date LIKE ?
            ORDER BY sl.id DESC
        ''', (selected_month + '%',)).fetchall()
        
        refund_data = conn.execute("SELECT * FROM refunds WHERE date LIKE ? ORDER BY date DESC", (selected_month + '%',)).fetchall()
        investor_data = conn.execute("SELECT * FROM investor_ledger WHERE date LIKE ? ORDER BY date DESC", (selected_month + '%',)).fetchall()
    else:
        ledger_history = conn.execute('''
            SELECT sl.*, s.seller_name, s.project_name, s.tcp 
            FROM seller_ledger sl 
            JOIN sellers s ON sl.seller_id = s.id
            ORDER BY sl.id DESC
        ''').fetchall()
        
        refund_data = conn.execute("SELECT * FROM refunds ORDER BY date DESC").fetchall()
        investor_data = conn.execute("SELECT * FROM investor_ledger ORDER BY date DESC").fetchall()

    conn.close()
    
    return render_template('index.html', 
                           daily_data=daily_data, 
                           daily_summary=daily_summary,
                           sellers=sellers, 
                           seller_data=seller_data, 
                           ledger_history=ledger_history, 
                           refund_data=refund_data, 
                           investor_data=investor_data,
                           selected_month=selected_month)

@app.route('/add_daily', methods=['POST'])
def add_daily():
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO daily_inputs (liquidation_date, dt_no, account_title, employee_sell, particulars, supplier, address, tin_no, e_date, e_ref, vatable, input_tax, amount, oic)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        request.form['liquidation_date'], request.form['dt_no'], request.form['account_title'],
        request.form['employee_sell'], request.form['particulars'], request.form['supplier'],
        request.form['address'], request.form['tin_no'], request.form.get('e_date', ''), request.form.get('e_ref', ''),
        float(request.form['vatable'] or 0), float(request.form['input_tax'] or 0),
        float(request.form['amount'] or 0), request.form['oic']
    ))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_seller_profile', methods=['POST'])
def add_seller_profile():
    seller_name = request.form['seller_name']
    project_name = request.form['project_name']
    tcp = float(request.form['tcp'] or 0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sellers (seller_name, project_name, tcp) VALUES (?, ?, ?)', (seller_name, project_name, tcp))
    seller_id = cursor.lastrowid
    
    date = request.form.get('date')
    if date:
        voucher_no = request.form.get('voucher_no', '')
        particulars = request.form.get('particulars', 'Initial Record / Opening')
        amount = float(request.form.get('amount', 0) or 0)
        balance = tcp - amount
        
        conn.execute('''
            INSERT INTO seller_ledger (seller_id, date, voucher_no, particulars, amount, balance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (seller_id, date, voucher_no, particulars, amount, balance))

    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_seller_payment', methods=['POST'])
def add_seller_payment():
    seller_id = request.form['seller_id']
    date = request.form['date']
    voucher_no = request.form['voucher_no']
    particulars = request.form['particulars']
    amount = float(request.form['amount'] or 0)

    conn = get_db_connection()
    seller = conn.execute('SELECT tcp FROM sellers WHERE id = ?', (seller_id,)).fetchone()
    last_row = conn.execute('SELECT balance FROM seller_ledger WHERE seller_id = ? ORDER BY id DESC LIMIT 1', (seller_id,)).fetchone()
    
    prev_balance = last_row['balance'] if last_row else seller['tcp']
    new_balance = prev_balance - amount

    conn.execute('''
        INSERT INTO seller_ledger (seller_id, date, voucher_no, particulars, amount, balance)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (seller_id, date, voucher_no, particulars, amount, new_balance))
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_refund', methods=['POST'])
def add_refund():
    total_payment = float(request.form['total_payment'] or 0)
    amount = float(request.form['amount'] or 0)
    conn = get_db_connection()
    last_row = conn.execute('SELECT balance FROM refunds WHERE client_name = ? AND site = ? ORDER BY id DESC LIMIT 1', 
                            (request.form['client_name'], request.form['site'])).fetchone()
    prev_balance = last_row['balance'] if last_row else total_payment
    new_balance = prev_balance - amount
    conn.execute('''
        INSERT INTO refunds (client_name, site, total_payment, total_refund, monthly, start_date, bank_account, date, amount, balance, mode_of_payment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (request.form['client_name'], request.form['site'], total_payment, float(request.form['total_refund'] or 0), float(request.form['monthly'] or 0), request.form['start_date'], request.form['bank_account'], request.form['date'], amount, new_balance, request.form['mode_of_payment']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_investor', methods=['POST'])
def add_investor():
    initial_capital = float(request.form['initial_capital'] or 0)
    amount = float(request.form['amount'] or 0)
    conn = get_db_connection()
    last_row = conn.execute('SELECT balance FROM investor_ledger WHERE investor_name = ? AND project_name = ? ORDER BY id DESC LIMIT 1', 
                            (request.form['investor_name'], request.form['project_name'])).fetchone()
    prev_balance = last_row['balance'] if last_row else initial_capital
    new_balance = prev_balance + amount
    conn.execute('''
        INSERT INTO investor_ledger (investor_name, project_name, initial_capital, date, voucher_no, particulars, amount, balance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (request.form['investor_name'], request.form['project_name'], initial_capital, request.form['date'], request.form['voucher_no'], request.form['particulars'], amount, new_balance))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/export_excel')
def export_excel():
    selected_month = request.args.get('month', '')
    conn = sqlite3.connect('accounting_system.db')
    
    if selected_month:
        # Ligtas na paraan (Parameterized Query sa Pandas)
        param = (f"{selected_month}%",)
        df_daily = pd.read_sql_query("SELECT * FROM daily_inputs WHERE liquidation_date LIKE ?", conn, params=param)
        df_seller = pd.read_sql_query("SELECT * FROM seller_ledger WHERE date LIKE ?", conn, params=param)
        df_investor = pd.read_sql_query("SELECT * FROM investor_ledger WHERE date LIKE ?", conn, params=param)
        df_refund = pd.read_sql_query("SELECT * FROM refunds WHERE date LIKE ?", conn, params=param)
    else:
        df_daily = pd.read_sql_query("SELECT * FROM daily_inputs", conn)
        df_seller = pd.read_sql_query("SELECT * FROM seller_ledger", conn)
        df_investor = pd.read_sql_query("SELECT * FROM investor_ledger", conn)
        df_refund = pd.read_sql_query("SELECT * FROM refunds", conn)
        
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_daily.to_excel(writer, sheet_name='Daily Inputs', index=False)
        df_seller.to_excel(writer, sheet_name='Seller Ledger', index=False)
        df_investor.to_excel(writer, sheet_name='Investor Room', index=False)
        df_refund.to_excel(writer, sheet_name='Refunds', index=False)
    
    output.seek(0)
    filename = f"Accounting_Report_{selected_month}.xlsx" if selected_month else "Accounting_Report_All.xlsx"
    
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True)