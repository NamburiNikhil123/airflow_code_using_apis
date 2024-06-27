CREATE TABLE IF NOT EXISTS skipped_data (
    id SERIAL PRIMARY KEY,
    dag_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    continous_skip_count INT NOT NULL, 
    datetime TIMESTAMP without TIME zone NOT NULL
);