UPDATE skipped_data SET continous_skip_count = continous_skip_count + 1, datetime = %s WHERE dag_id = %s AND task_id = %s
