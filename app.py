from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import os
import pytesseract
from PIL import Image
import mysql.connector
import logging

app = Flask(__name__)

# Setup paths and allowed file types
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Set the path for Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Change for Linux/Mac if needed

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Helper function to validate file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Serve the index page
@app.route('/')
def index():
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        logging.error(f"Error serving index page: {e}")
        return "Error: Unable to load the index page.", 500

# Image upload and processing
@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Extract text using Tesseract OCR
            extracted_text = pytesseract.image_to_string(Image.open(filepath)).strip()

            # Normalize text
            cleaned_text = extracted_text.replace("\n", " ").lower()
            if not cleaned_text:
                return jsonify({"error": "No text found in the image"}), 400

            # Connect to MySQL (Railway.app database)
            try:
                conn = mysql.connector.connect(
                    host="roundhouse.proxy.rlwy.net",
                    port=56076,
                    user="root",
                    password="GztjLsKIBwpNZuyIxVUfMXTXlbBxQcYn",
                    database="railway"
                )
                cursor = conn.cursor()

                # Process extracted text
                ingredients = [item.strip() for item in cleaned_text.split(",")]
                query = """
                    SELECT `Ingredient Name`, `Chemical Name`, `Is Harmful`, `Description`, 
                           `Affected Body Parts`, `Percentage Effect`, `Food Sources` 
                    FROM project_table 
                    WHERE `Ingredient Name` LIKE %s
                """

                results = []
                for ingredient in ingredients:
                    cursor.execute(query, (f"%{ingredient}%",))
                    results.extend(cursor.fetchall())

                # Close database connection
                cursor.close()
                conn.close()

                # Generate response HTML
                result_html = f"<h3>Extracted Text:</h3><p>{extracted_text}</p><br>"

                if results:
                    result_html += """
                        <h3>Ingredient Analysis Results:</h3>
                        <table border="1" style="width:100%; border-collapse: collapse; text-align: left;">
                            <tr>
                                <th>Ingredient Name</th>
                                <th>Chemical Name</th>
                                <th>Is Harmful</th>
                                <th>Description</th>
                                <th>Affected Body Parts</th>
                                <th>Percentage Effect</th>
                                <th>Food Sources</th>
                            </tr>
                    """
                    for row in results:
                        result_html += f"""
                            <tr>
                                <td>{row[0]}</td>
                                <td>{row[1]}</td>
                                <td>{row[2]}</td>
                                <td>{row[3]}</td>
                                <td>{row[4]}</td>
                                <td>{row[5]}</td>
                                <td>{row[6]}</td>
                            </tr>
                        """
                    result_html += "</table>"
                else:
                    result_html += "<p><strong>No matching ingredients found.</strong></p>"

                return result_html, 200

            except mysql.connector.Error as db_err:
                logging.error(f"Database error: {db_err}")
                return jsonify({"error": f"Database error: {db_err}"}), 500

        except Exception as e:
            logging.error(f"Error during processing: {e}")
            return jsonify({"error": f"An error occurred while processing your request: {e}"}), 500

    else:
        return jsonify({"error": "Invalid file format"}), 400


# Run Flask app
if __name__ == '__main__':
    app.run(debug=True)
