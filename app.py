import os
import subprocess
import uuid
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, after_this_request
import threading
import time
from werkzeug.utils import secure_filename
from pdf2docx import Converter


def delayed_cleanup(filepaths, delay=60):
    def cleanup():
        time.sleep(delay)
        for filepath in filepaths:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
    threading.Thread(target=cleanup).start()

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    conversion_type = request.form.get('conversion_type')
    if not conversion_type:
        flash('No conversion type selected')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Use UUID to prevent file name collisions
        unique_id = str(uuid.uuid4())
        base_filename, ext = os.path.splitext(filename)

        input_filename = f"{base_filename}_{unique_id}{ext}"
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        file.save(input_path)

        try:
            if conversion_type == 'pdf_to_word':
                if not filename.lower().endswith('.pdf'):
                    flash('Please upload a PDF file for this conversion.')
                    return redirect(url_for('index'))

                output_filename = f"{base_filename}_{unique_id}.docx"
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

                cv = Converter(input_path)
                cv.convert(output_path, start=0, end=None)
                cv.close()

                delayed_cleanup([input_path, output_path])

                return send_file(output_path, as_attachment=True, download_name=f"{base_filename}.docx")

            elif conversion_type == 'word_to_pdf':
                if not (filename.lower().endswith('.doc') or filename.lower().endswith('.docx')):
                    flash('Please upload a Word document (.doc or .docx) for this conversion.')
                    return redirect(url_for('index'))

                output_filename = f"{base_filename}_{unique_id}.pdf"
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

                # libreoffice will save the pdf in the same directory as the input file
                # or we can specify the outdir
                result = subprocess.run([
                    'libreoffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', app.config['UPLOAD_FOLDER'], input_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if result.returncode != 0:
                    flash(f'Error during conversion: {result.stderr.decode("utf-8")}')
                    return redirect(url_for('index'))

                # The output file name will have the original base name but with .pdf extension
                # Because of our unique_id, input_filename is `base_id.docx`, so the output is `base_id.pdf`
                actual_output_filename = f"{base_filename}_{unique_id}.pdf"
                actual_output_path = os.path.join(app.config['UPLOAD_FOLDER'], actual_output_filename)

                if os.path.exists(actual_output_path):
                    delayed_cleanup([input_path, actual_output_path])
                    return send_file(actual_output_path, as_attachment=True, download_name=f"{base_filename}.pdf")
                else:
                    flash('Conversion failed. Output file not found.')
                    return redirect(url_for('index'))

            else:
                flash('Invalid conversion type')
                return redirect(url_for('index'))
        except Exception as e:
            flash(f'An error occurred: {str(e)}')
            return redirect(url_for('index'))
    else:
        flash('Invalid file type')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
