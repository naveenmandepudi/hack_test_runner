import os
import random
import time
from urllib.parse import urlparse

from flask import Flask, request, render_template, session, flash, redirect, \
    url_for, jsonify
from celery import Celery

app = Flask(__name__)

# Celery configuration

redis_url = None


if (os.getenv('REDISCLOUD_URL')):
    redis_url = urlparse(os.getenv('REDISCLOUD_URL')).hostname

app.config['CELERY_BROKER_URL'] = redis_url if os.getenv('REDISCLOUD_URL') else 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = redis_url if os.getenv('REDISCLOUD_URL') else 'redis://localhost:6379/0'


# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], include=['app'])
celery.conf.update(app.config)


@celery.task(bind=True)
def start_test_execution(self):
    """Background task that runs a long function with progress reports."""
    print('Starting test')

    total = random.randint(10, 50)
    print('executed long task')
    time.sleep(15)
    return {'current': 100, 'total': 100, 'status': 'Task completed!',
            'result': total}


@app.route('/', methods=['GET'])
def go_home():
    response = {
        'state': 'alive and kicking'
    }
    return jsonify(response)


@app.route('/start', methods=['POST','GET'])
def start_test():
    task = start_test_execution.apply_async()
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
    app.run(port=5000, debug=False, threaded=False)