import sqlite3

def init_db():
    conn = sqlite3.connect('accounting_system.db')
    cursor = conn.cursor()
    
    # 1. Daily Input / Liquidation Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_inputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liquidation_date TEXT,
            dt_no TEXT,
            account_title TEXT,
            employee_sell TEXT,
            particulars TEXT,
            supplier TEXT,
            address TEXT,
            tin_no TEXT,
            e_date TEXT,
            e_ref TEXT,
            vatable REAL,
            input_tax REAL,
            amount REAL,
            oic TEXT
        )
    ''')
    
    # 2. Sellers Master List (Ang "Folders" ng bawat Seller)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_name TEXT,
            project_name TEXT,
            tcp REAL
        )
    ''')

    # 3. Seller/Lot Ledger Transactions (History ng hulog)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seller_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            date TEXT,
            voucher_no TEXT,
            particulars TEXT,
            amount REAL,
            balance REAL,
            FOREIGN KEY(seller_id) REFERENCES sellers(id)
        )
    ''')
    
    # 4. Refund Summary & Individual Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refunds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            site TEXT,
            total_payment REAL,
            total_refund REAL,
            monthly REAL,
            start_date TEXT,
            bank_account TEXT,
            date TEXT,
            amount REAL,
            balance REAL,
            mode_of_payment TEXT
        )
    ''')

    # 5. Investor Ledger Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS investor_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_name TEXT,
            project_name TEXT,
            initial_capital REAL,
            date TEXT,
            voucher_no TEXT,
            particulars TEXT,
            amount REAL,
            balance REAL
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database at lahat ng tables ay matagumpay na nagawa!")