from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import hashlib
from datetime import date

app = Flask(__name__)
CORS(app)

def get_db_connection():
    return mysql.connector.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='root',
        database='invosys'
    )

# ------- REGISTRO -------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    print("REGISTER payload:", data)
    pwd_hash = hashlib.sha256(data['password'].encode()).hexdigest()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (data['email'],))
    if cur.fetchone():
        cur.close(); conn.close()
        return jsonify(message='Email ya registrado'), 400
    cur.execute(
      "INSERT INTO users (nombre,email,telefono,password_hash,require_2fa) "
      "VALUES (%s,%s,%s,%s,0)",
      (data['nombre'], data['email'], data.get('telefono'), pwd_hash)
    )
    conn.commit()
    cur.close(); conn.close()
    return jsonify(message='Registro exitoso'), 201

# ------- LOGIN -------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    print("LOGIN payload:", data)
    pwd_hash = hashlib.sha256(data['password'].encode()).hexdigest()

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
      "SELECT id,password_hash FROM users WHERE email=%s",
      (data['email'],)
    )
    user = cur.fetchone()
    cur.close(); conn.close()

    if not user or user['password_hash'] != pwd_hash:
        print("LOGIN failed for:", data['email'])
        return jsonify(message='Credenciales inválidas'), 401

    print("LOGIN success, user ID:", user['id'])
    # devolvemos id y id_usuario por si front usa uno u otro
    return jsonify(
      id_usuario = user['id'],
      id         = user['id'],
      message    = 'Login exitoso'
    ), 200

# ------- CREAR FACTURA -------
@app.route('/api/invoices', methods=['POST'])
def create_invoice():
    data = request.get_json()
    print("CREATE_INVOICE payload:", data)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
      INSERT INTO invoices (
        user_id,invoice_number,invoice_date,due_date,
        issuer_name,issuer_rfc,issuer_email,issuer_phone,issuer_address,
        client_name,client_rfc,client_address,
        subtotal,iva_amount,total_amount
      ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
      data['user_id'],
      data['invoice_number'],
      date.fromisoformat(data['invoice_date']),
      date.fromisoformat(data['due_date']) if data.get('due_date') else None,
      data['issuer']['name'],
      data['issuer']['rfc'],
      data['issuer']['email'],
      data['issuer'].get('phone'),
      data['issuer'].get('address'),
      data['client']['name'],
      data['client']['rfc'],
      data['client'].get('address'),
      data['subtotal'],
      data['iva'],
      data['total']
    ))
    invoice_id = cur.lastrowid
    for item in data['items']:
        cur.execute("""
          INSERT INTO invoice_items (
            invoice_id,description,quantity,unit,price,vat_percent,importe
          ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
          invoice_id,
          item['description'],
          item['quantity'],
          item['unit'],
          item['price'],
          item['vat_percent'],
          item['importe']
        ))
    conn.commit()
    cur.close(); conn.close()
    return jsonify(message='Factura creada', invoice_id=invoice_id), 201

# ------- LISTAR FACTURAS -------
@app.route('/api/invoices', methods=['GET'])
def list_invoices():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(message='Falta user_id'), 400
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
      SELECT invoice_number, invoice_date, total_amount 
      FROM invoices 
      WHERE user_id=%s 
      ORDER BY invoice_date DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    # formatea fechas e importe
    for r in rows:
        r['invoice_date']  = r['invoice_date'].isoformat()
        r['total_amount']  = float(r['total_amount'])
    return jsonify(invoices=rows), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
