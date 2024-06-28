# from cryptography.fernet import Fernet
# import json
# from filekey import filekey

# key = filekey.encode()
# print(filekey)
# print(key)

# fernet = Fernet(key)

# # Path to the file to encrypt
# postgres_conn_file_path = '/home/nikhilnamburi/Desktop/python/airflow/dags/postgres_connection.py'

# # Read the original file
# with open(postgres_conn_file_path, 'rb') as file:
#     original_data = file.read()

# # Immediately decrypt to verify
# # decrypted_data = fernet.decrypt(original_data)
# # #print(f"Decrypted data: {decrypted_data.decode('utf-8'), type(decrypted_data.decode('utf-8'))}")
# # postgres_conn = json.loads(decrypted_data)
# # print(postgres_conn , type(postgres_conn))

# encrypted_data = fernet.encrypt(original_data)

# # # Save the encrypted data back to the file
# with open(postgres_conn_file_path, 'wb') as encrypted_file:
#     encrypted_file.write(encrypted_data)

