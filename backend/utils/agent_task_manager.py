import uuid
from threading import Lock

class AgentTaskManager:
    """Manages the state and progress of asynchronous agent tasks."""
    def __init__(self):
        self.tasks = {}
        self.lock = Lock()

    def create_task(self):
        """Creates a new task and returns its ID."""
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks[task_id] = {
                'status': 'pending',
                'message': 'Task created. Waiting to start...',
                'is_complete': False,
                'result': None,
                'success': None
            }
        return task_id

    def update_progress(self, task_id, message, status='in_progress'):
        """Updates the progress message and status of a task."""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = status
                self.tasks[task_id]['message'] = message
                print(f"TASK [{task_id}]: {message}") # Also log to console

    def complete_task(self, task_id, result, success=True):
        """Marks a task as complete and stores the final result."""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = 'complete' if success else 'error'
                self.tasks[task_id]['message'] = 'Task finished.'
                self.tasks[task_id]['is_complete'] = True
                self.tasks[task_id]['result'] = result
                self.tasks[task_id]['success'] = success

    def get_task_status(self, task_id):
        """Retrieves the current status of a task."""
        with self.lock:
            return self.tasks.get(task_id, {'status': 'not_found', 'message': 'Task not found.'})

    def cleanup_task(self, task_id):
        """Removes a task from the manager, e.g., after it's been fetched."""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
