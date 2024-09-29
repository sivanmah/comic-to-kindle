import os
import io
from zipfile import ZipFile
import subprocess
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
from ebooklib import epub
import uuid
import threading
import time


app = Flask(__name__)
CORS(app)
task_progress = {}

os.makedirs('uploads', exist_ok=True)
UPLOAD_FOLDER = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

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
def start_conversion():
    if not request.files:
        return jsonify({'error': 'No files found in request'}), 400
    
    conversion_id = str(uuid.uuid4())
    conversion_folder = os.path.join(app.config['UPLOAD_FOLDER'], conversion_id)
    os.makedirs(conversion_folder, exist_ok=True)

    saved_files = {}
    for key, file in request.files.items():
        directory, filename = os.path.split(key)
        if file and allowed_file(filename):
            filename = secure_filename(filename)
            dir_path = os.path.join(conversion_folder, directory)
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, filename)
            file.save(file_path)
            if directory not in saved_files:
                saved_files[directory] = []
            saved_files[directory].append(file_path)

    if not saved_files:
        return jsonify({'error': 'No valid images found in upload'}), 400

    thread = threading.Thread(target=background_task, args=(conversion_id, saved_files))
    thread.start()

    return jsonify({'task_id': conversion_id}), 202


def background_task(conversion_id, fileLists):
    task_progress[conversion_id] = {'progress': 1, 'status': 'In Progress'}
    output_folder = os.path.join(app.config['OUTPUT_FOLDER'], conversion_id)
    os.makedirs(output_folder, exist_ok=True)

    results = []
    for directory, files in fileLists.items():
        files.sort()
        book_title = directory if directory else "Untitled"
        
        # Create EPUB
        epub_filename = f"{book_title}.epub"
        epub_path = os.path.join(output_folder, epub_filename)
        create_epub_from_images(files, epub_path, book_title)
        
        # Convert EPUB to MOBI
        mobi_filename = f"{book_title}.mobi"
        mobi_path = os.path.join(output_folder, mobi_filename)
        try:
            convert_epub_to_mobi(epub_path, mobi_path)
        except Exception as e:
            results.append({
                'book_title': book_title,
                'error': str(e)
            })
        else:
            task_progress[conversion_id]['progress'] += 1
            results.append({
                'book_title': book_title,
                'epub_path': epub_path,
                'mobi_path': mobi_path
            })

    task_progress[conversion_id]['status'] = 'Completed'


@app.route('/download/<conversion_id>')
def download_mobi(conversion_id):
    output_folder = os.path.join(app.config['OUTPUT_FOLDER'], conversion_id)
    if not os.path.exists(output_folder):
        return jsonify({'error': 'Conversion ID not found'}), 404 

    mobi_files = [f for f in os.listdir(output_folder) if f.endswith('.mobi')]
    if not mobi_files:
        return jsonify({'error': 'No MOBI files found for this conversion ID'}), 404

    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        for mobi_file in mobi_files:
            mobi_path = os.path.join(output_folder, mobi_file)
            zf.write(mobi_path, mobi_file)   
    
    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='conversion.zip',
    )

@app.route('/status/<conversion_id>')
def get_status(conversion_id):
    progress = task_progress[conversion_id].get('progress', 0)
    status = task_progress[conversion_id].get('status', 'In Progress')
    if status == 'Completed':
        return jsonify({'progress': progress, 'conversion_id': conversion_id, 'status': status})
    else:
        return jsonify({'progress': progress})


if __name__ == '__main__':
    app.run(debug=True)
