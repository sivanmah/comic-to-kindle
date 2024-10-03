import os
import io
from zipfile import ZipFile, ZIP_STORED
import subprocess
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps
import uuid
import threading


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

def handle_spread(image):
    width, height = image.size
    if width > height:
        image = image.rotate(90, expand=True)
    return image

def compress_image(image):
    image = ImageOps.grayscale(image)
    return image
    

def create_epub_from_images(image_files, output_epub, book_title):
    with ZipFile(output_epub, 'w') as epub:
        # Add mimetype file
        epub.writestr('mimetype', 'application/epub+zip', compress_type=ZIP_STORED)

        # Add container.xml
        epub.writestr('META-INF/container.xml', '''<?xml version="1.0"?>
        <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
          <rootfiles>
            <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
          </rootfiles>
        </container>''')

        # Create and add content files
        chapters = []
        for i, image_file in enumerate(image_files):
            with Image.open(image_file) as img:
                img_format = img.format.lower()
                img = handle_spread(img)
                img = compress_image(img)
                img_io = io.BytesIO()
                img.save(img_io, img_format)
                img_data = img_io.getvalue()

            epub.writestr(f'OEBPS/images/image_{i}.{img_format}', img_data)

            chapter_content = f'''<?xml version="1.0" encoding="utf-8"?>
            <!DOCTYPE html>
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
            <head>
                <title>Page {i+1}</title>
                <style>
                    body, html {{
                        margin: 0;
                        padding: 0;
                        width: 100%;
                        height: 100%;
                    }}
                    body {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                    }}
                    img {{
                        max-width: 100%;
                        max-height: 100%;
                        object-fit: contain;
                    }}
                </style>
            </head>
            <body>
                <img src="images/image_{i}.{img_format}" alt="Page {i+1}"/>
            </body>
            </html>'''

            epub.writestr(f'OEBPS/page_{i+1}.xhtml', chapter_content)
            chapters.append(f'page_{i+1}.xhtml')

        # Create and add content.opf
        content_opf = f'''<?xml version="1.0" encoding="utf-8"?>
        <package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
            <dc:title>{book_title}</dc:title>
            <dc:identifier id="uuid_id" opf:scheme="uuid">{uuid.uuid4()}</dc:identifier>
            <dc:language>en</dc:language>
          </metadata>
          <manifest>
            {''.join(f'<item id="page_{i+1}" href="{chapter}" media-type="application/xhtml+xml" />' for i, chapter in enumerate(chapters))}
            {''.join(f'<item id="image_{i}" href="images/image_{i}.{Image.open(image_file).format.lower()}" media-type="image/{Image.open(image_file).format.lower()}" />' for i, image_file in enumerate(image_files))}
          </manifest>
          <spine toc="ncx">
            {''.join(f'<itemref idref="page_{i+1}" />' for i in range(len(chapters)))}
          </spine>
        </package>'''

        epub.writestr('OEBPS/content.opf', content_opf)


def convert_epub_to_azw3(epub_file: str, output_azw3: str) -> None:
    try:
        result = subprocess.run(['ebook-convert', epub_file, output_azw3,
                                 '--output-profile=kindle_pw',
                                 '--chapter-mark=none',
                                 '--page-breaks-before=/',
                                 '--no-inline-toc',
], 
                                check=True, capture_output=True, text=True)
        print(f"Conversion output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Conversion error: {e.stderr}")
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
        
        # Convert EPUB to AZW3
        azw3_filename = f"{book_title}.azw3"
        azw3_path = os.path.join(output_folder, azw3_filename)
        try:
            convert_epub_to_azw3(epub_path, azw3_path)
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
                'azw3_path': azw3_path
            })

    task_progress[conversion_id]['status'] = 'Completed'


@app.route('/download/<conversion_id>')
def download_azw3(conversion_id):
    output_folder = os.path.join(app.config['OUTPUT_FOLDER'], conversion_id)
    if not os.path.exists(output_folder):
        return jsonify({'error': 'Conversion ID not found'}), 404 

    azw3_files = [f for f in os.listdir(output_folder) if f.endswith('.azw3')]
    if not azw3_files:
        return jsonify({'error': 'No AZW3 files found for this conversion ID'}), 404

    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        for azw3_file in azw3_files:
            azw3_path = os.path.join(output_folder, azw3_file)
            zf.write(azw3_path, azw3_file)   
    
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
    app.run()
