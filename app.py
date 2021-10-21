import getopt
import os
import random
import sys
import time
from urllib.parse import urlparse

from flask import Flask, request, session, flash, redirect, \
    url_for, jsonify
from celery import Celery

from werkzeug.utils import secure_filename

import locustExtract

app = Flask(__name__)

# Celery configuration

app.config['CELERY_BROKER_URL'] = os.getenv('REDISCLOUD_URL') if os.getenv(
    'REDISCLOUD_URL') else 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = os.getenv('REDISCLOUD_URL') if os.getenv(
    'REDISCLOUD_URL') else 'redis://localhost:6379/0'

# Initialize Celery
celery_app = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_RESULT_BACKEND'],
                    include=['app'])
celery_app.conf.update(app.config)

app.config['UPLOAD_FOLDER'] = os.getcwd()


@celery_app.task(bind=True)
def start_test_execution(self,yaml_location):
    """Background task that runs a long function with progress reports."""
    locustExtract.scriptentrypoint(os.path.abspath(yaml_location))
    print('executed long task')
    return {'status': 'Task completed!'}


@app.route('/', methods=['GET'])
def go_home():
    response = {
        'state': 'alive and kicking'
    }
    return jsonify(response)


@app.route('/start', methods=['POST', 'GET'])
def start_test():
    if request.method == 'POST':
        f = request.files['file']
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], f.filename))
        yaml_location = f.filename
        print('file uploaded successfully')
    task = start_test_execution.apply_async(args=[yaml_location])
    print('called test task method')
    return jsonify({}), 202, {'Location': url_for('test_task_status',
                                                  task_id=task.id)}


@app.route('/status/<task_id>')
def test_task_status(task_id):
    print('star background job')
    task = start_test_execution.AsyncResult(task_id)
    print('should have started')
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'status': task.info.get('status', '')
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        # something went wrong in the background job
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # this is the exception raised
        }
    return jsonify(response)


if __name__ == '__main__':
    # argumentList = sys.argv[1:]
    # options = "i:"
    # long_options = ["input="]
    # arguments, values = getopt.getopt(argumentList, options, long_options)
    # if len(arguments) == 0:
    #     sys.exit("No arguments given hence terminated!!")
    # for currentArgument, currentValue in arguments:
    #     if currentArgument in ("-i", "--input"):
    #         yaml_location = currentValue
    #     else:
    #         sys.exit("[ERROR] Please provide valid config file!!")
    app.run(port=5000, debug=False)
