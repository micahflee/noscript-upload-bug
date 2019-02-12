import os
import tempfile
from datetime import datetime
from flask import Flask, Request, flash, request, redirect, url_for
from werkzeug.utils import secure_filename


def human_readable_filesize(b):
    """
    Returns filesize in a human readable format.
    """
    thresh = 1024.0
    if b < thresh:
        return '{:.1f} B'.format(b)
    units = ('KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    u = 0
    b /= thresh
    while b >= thresh:
        b /= thresh
        u += 1
    return '{:.1f} {}'.format(b, units[u])


class CustomTemporaryFile(object):
    """
    A custom TemporaryFile that tells ReceiveModeRequest every time data gets
    written to it, in order to track the progress of uploads.
    """
    def __init__(self, filename, write_func, close_func):
        self.onionshare_filename = filename
        self.onionshare_write_func = write_func
        self.onionshare_close_func = close_func

        # Create a temporary file
        self.f = tempfile.TemporaryFile('wb+')
        print('Writing to temporary file: {}'.format(self.f.name))

        # Make all the file-like methods and attributes actually access the
        # TemporaryFile, except for write
        attrs = ['closed', 'detach', 'fileno', 'flush', 'isatty', 'mode',
                 'name', 'peek', 'raw', 'read', 'read1', 'readable', 'readinto',
                 'readinto1', 'readline', 'readlines', 'seek', 'seekable', 'tell',
                 'truncate', 'writable', 'writelines']
        for attr in attrs:
            setattr(self, attr, getattr(self.f, attr))

    def write(self, b):
        """
        Custom write method that calls out to onionshare_write_func
        """
        bytes_written = self.f.write(b)
        self.onionshare_write_func(self.onionshare_filename, bytes_written)

    def close(self):
        """
        Custom close method that calls out to onionshare_close_func
        """
        self.f.close()
        self.onionshare_close_func(self.onionshare_filename)


class CustomRequest(Request):
    """
    A custom flask Request object that keeps track of how much data has been
    uploaded for each file
    """
    def __init__(self, environ, populate_request=True, shallow=False):
        super(CustomRequest, self).__init__(environ, populate_request, shallow)

        # Prevent running the close() method more than once
        self.closed = False

        self.upload_request = self.method == 'POST'

        if self.upload_request:
            # A dictionary that maps filenames to the bytes uploaded so far
            self.progress = {}

            try:
                self.content_length = int(self.headers['Content-Length'])
            except:
                self.content_length = 0

            print("{}: {}".format(
                datetime.now().strftime("%b %d, %I:%M%p"),
                'Upload of total size {} is starting'.format(human_readable_filesize(self.content_length))
            ))

            self.previous_file = None

    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        """
        This gets called for each file that gets uploaded, and returns an file-like
        writable stream.
        """
        if self.upload_request:
            self.progress[filename] = {
                'uploaded_bytes': 0,
                'complete': False
            }

        return CustomTemporaryFile(filename, self.file_write_func, self.file_close_func)

    def close(self):
        """
        Closing the request.
        """
        super(CustomRequest, self).close()

        # Prevent calling this method more than once per request
        if self.closed:
            return
        self.closed = True

        print('Upload finished')

    def file_write_func(self, filename, length):
        """
        This function gets called when a specific file is written to.
        """
        if self.closed:
            return

        if self.upload_request:
            self.progress[filename]['uploaded_bytes'] += length

            if self.previous_file != filename:
                if self.previous_file is not None:
                    print('')
                self.previous_file = filename

            print('=> {} bytes ({}) {}'.format(
                self.progress[filename]['uploaded_bytes'],
                human_readable_filesize(self.progress[filename]['uploaded_bytes']),
                filename
            ))

    def file_close_func(self, filename):
        """
        This function gets called when a specific file is closed.
        """
        self.progress[filename]['complete'] = True


UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.request_class = CustomRequest

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return redirect(url_for('upload_file'))
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''


if __name__ == '__main__':
    app.run()
