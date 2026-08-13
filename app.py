from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pymysql
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "my-secret-key")

# For Vercel Serverless (use /tmp for file uploads)
UPLOAD_FOLDER = '/tmp/uploads' if os.environ.get("VERCEL") else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- MySQL Configuration (Reads Environment Variables from Vercel) ---
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'mysql-1103018b-scrapbook.d.aivencloud.com')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 12968))
MYSQL_USER = os.environ.get('MYSQL_USER', 'avnadmin')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'defaultdb')


def get_db():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor,
        ssl={'ssl': {}}  # <-- REQUIRED for Aiven MySQL
    )


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        dob = request.form["dob"]
        gender = request.form["gender"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if password != confirm:
            return "Passwords do not match."

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=%s OR username=%s",
            (email, username)
        )
        user = cursor.fetchone()

        if user:
            conn.close()
            return "Email or Username already exists."

        cursor.execute("""
        INSERT INTO users(first_name, last_name, username, email, phone, dob, gender, password)
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (first_name, last_name, username, email, phone, dob, gender, generate_password_hash(password)))

        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("reg.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("scrapbook"))

        return "Invalid Email or Password."

    return render_template("log.html")


@app.route("/scrapbook")
def scrapbook():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")


@app.route("/api/scrapbooks")
def get_scrapbooks():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM scrapbooks WHERE user_id=%s", (session["user_id"],))
    rows = cursor.fetchall()
    conn.close()

    return jsonify([{"id": row["id"], "name": row["name"], "memories": []} for row in rows])


@app.route("/api/scrapbooks", methods=["POST"])
def create_scrapbook():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    name = data.get("name")

    if not name:
        return jsonify({"error": "Scrapbook name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO scrapbooks(user_id, name) VALUES(%s, %s)", (session["user_id"], name))
    scrapbook_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({"id": scrapbook_id, "name": name, "memories": []})


@app.route("/api/scrapbooks/<int:scrapbook_id>", methods=["DELETE"])
def delete_scrapbook(scrapbook_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM scrapbooks WHERE id=%s AND user_id=%s", (scrapbook_id, session["user_id"]))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/scrapbooks/<int:scrapbook_id>/memories", methods=["GET"])
def get_memories(scrapbook_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, image_path, caption, date FROM memories WHERE scrapbook_id=%s", (scrapbook_id,))
    rows = cursor.fetchall()
    conn.close()

    return jsonify(rows)


@app.route("/api/scrapbooks/<int:scrapbook_id>/memories", methods=["POST"])
def add_memory(scrapbook_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    caption = request.form.get("caption", "")
    date = request.form.get("date", "")
    file = request.files.get("image")

    image_path = ""
    if file and file.filename != "":
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        image_path = f"/static/uploads/{filename}"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO memories (scrapbook_id, image_path, caption, date) VALUES (%s, %s, %s, %s)",
        (scrapbook_id, image_path, caption, date)
    )

    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"id": memory_id, "image_path": image_path, "caption": caption, "date": date})


@app.route("/api/memories/<int:memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM memories WHERE id=%s", (memory_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)