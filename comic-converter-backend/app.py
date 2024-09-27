import os
import io
import platform
import subprocess
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
from ebooklib import epub
import uuid


app = Flask(__name__)
CORS(app)

os.makedirs('uploads', exist_ok=True)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_epub_from_images(image_files, output_epub, book_title):
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(book_title)
    book.set_language('en')

    with Image.open(image_files[0]) as img:
        img_io = io.BytesIO()
        img.save(img_io, img.format)
        book.set_cover(image_files[0], img_io.getvalue(), create_page=False)

    chapters = []

    for i, image_file in enumerate(image_files):
        with Image.open(image_file) as img:
            img_io = io.BytesIO()
            img.save(img_io, img.format)
            img_data = img_io.getvalue()

            epub_image_name = f'image{i}.{img.format.lower()}'
            epub_image = epub.EpubImage(file_name=epub_image_name, media_type=f'image/{img.format.lower()}', content=img_data)
            book.add_item(epub_image)

            # Create a chapter for each image
            chapter = epub.EpubHtml(title=f'Page {i+1}', file_name=f'page{i+1}.xhtml')
            chapter.content = f'''
            <html>
                <head>
                    <style>
                        img {{
                            width: 100%;
                            height: 100%;
                        }}
                    </style>
                </head>
                <body>
                    <img src="{epub_image_name}" alt="Page {i+1}"/>
                </body>
            </html>
            '''
            book.add_item(chapter)
            chapters.append(chapter)

    book.add_item(epub.EpubNcx())  # create Navigation Control file
    book.add_item(epub.EpubNav())
    book.spine = chapters

    epub.write_epub(output_epub, book, {})

def convert_epub_to_mobi(epub_file, output_mobi):
    try:
        subprocess.run(['ebook-convert', epub_file, output_mobi], 
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Conversion error: {e.stderr.decode()}")
        raise
    except FileNotFoundError:
        print("ebook-convert not found. Please install Calibre.")
        raise


@app.route('/convert', methods=['POST'])
def convert_images():
    app.logger.info("Received /convert request")
    # app.logger.debug(f"Request files: {request.files}")

    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    app.logger.info(f"Number of files received: {len(files)}")

    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    conversion_id = str(uuid.uuid4())
    conversion_folder = os.path.join(app.config['UPLOAD_FOLDER'], conversion_id) 
    os.makedirs(conversion_folder, exist_ok=True)

    saved_files = []
    book_title = "Sample Title"
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(conversion_folder, filename)
            file.save(file_path)
            saved_files.append(file_path)

            if book_title == "Untitled":
                book_title = os.path.basename(os.path.dirname(file.filename))
    if not saved_files:
        return jsonify({'error': 'No valid images found in folder'}), 400

    saved_files.sort()

    epub_path = os.path.join(conversion_folder, 'output.epub')
    create_epub_from_images(saved_files, epub_path, book_title)

    mobi_path = os.path.join(conversion_folder, 'output.mobi')
    convert_epub_to_mobi(epub_path, mobi_path)

    return jsonify({'conversion_id': conversion_id, 'book_title': book_title}), 200

@app.route('/download/<conversion_id>')
def download_mobi(conversion_id):
    mobi_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(conversion_id), 'output.mobi')
    if not os.path.exists(mobi_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(mobi_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
