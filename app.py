from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pymysql
import os
import ssl
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "my-secret-key")

# File upload handling for serverless
if os.environ.get("VERCEL") or not os.access('.', os.W_OK):
    UPLOAD_FOLDER = '/tmp'
else:
    UPLOAD_FOLDER = 'static/uploads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- MySQL Configuration from Environment Variables ---
MYSQL_HOST = os.environ.get('MYSQL_HOST')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
MYSQL_DB = os.environ.get('MYSQL_DB')


def get_db():
    """Establish a secure connection to Aiven MySQL."""
    try:
        ssl_ctx = ssl.create_default_context()
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            ssl=ssl_ctx,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        raise e


def init_db():
    """Ensure database tables exist on Aiven MySQL."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            username VARCHAR(100) UNIQUE,
            email VARCHAR(100) UNIQUE,
            phone VARCHAR(20),
            dob VARCHAR(20),
            gender VARCHAR(20),
            password VARCHAR(255)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrapbooks(
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            name VARCHAR(255) NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories(
            id INT AUTO_INCREMENT PRIMARY KEY,
            scrapbook_id INT,
            image_path VARCHAR(255),
            caption TEXT,
            date VARCHAR(50),
            FOREIGN KEY(scrapbook_id) REFERENCES scrapbooks(id) ON DELETE CASCADE
        )
        """)

        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)


# --- IMPORTANT: Commented out for Vercel Serverless ---
# with app.app_context():
#     init_db()


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "")
        last_name = request.form.get("last_name", "")
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        dob = request.form.get("dob", "")
        gender = request.form.get("gender", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            return "Passwords do not match.", 400

        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM users WHERE email=%s OR username=%s",
                (email, username)
            )
            user = cursor.fetchone()

            if user:
                conn.close()
                return "Email or Username already exists.", 400

            cursor.execute("""
            INSERT INTO users(first_name, last_name, username, email, phone, dob, gender, password)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (first_name, last_name, username, email, phone, dob, gender, generate_password_hash(password)))

            conn.commit()
            conn.close()

            return redirect(url_for("login"))
        except Exception as e:
            print("Register error:", e)
            return f"Database Error during registration: {str(e)}", 500

    return render_template("reg.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            conn.close()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("scrapbook"))

            return "Invalid Email or Password.", 401
        except Exception as e:
            print("Login error:", e)
            return f"Database Error during login: {str(e)}", 500

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

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM scrapbooks WHERE user_id=%s", (session["user_id"],))
        rows = cursor.fetchall()
        conn.close()

        return jsonify([{"id": row["id"], "name": row["name"], "memories": []} for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrapbooks", methods=["POST"])
def create_scrapbook():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    name = data.get("name")

    if not name:
        return jsonify({"error": "Scrapbook name is required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("INSERT INTO scrapbooks(user_id, name) VALUES(%s, %s)", (session["user_id"], name))
        scrapbook_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({"id": scrapbook_id, "name": name, "memories": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrapbooks/<int:scrapbook_id>", methods=["DELETE"])
def delete_scrapbook(scrapbook_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM scrapbooks WHERE id=%s AND user_id=%s", (scrapbook_id, session["user_id"]))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrapbooks/<int:scrapbook_id>/memories", methods=["GET"])
def get_memories(scrapbook_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id, image_path, caption, date FROM memories WHERE scrapbook_id=%s", (scrapbook_id,))
        rows = cursor.fetchall()
        conn.close()

        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/memories/<int:memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM memories WHERE id=%s", (memory_id,))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)