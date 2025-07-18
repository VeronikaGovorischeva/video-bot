import json
import os
from googleapiclient.http import MediaFileUpload


from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)



def create_folder(name, parent_id):
    service = get_drive_service()
    query = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    if results['files']:
        return results['files'][0]['id']

    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]  # ← MUST be your shared folder ID
    }
    folder = service.files().create(body=metadata, fields='id').execute()
    return folder['id']



def upload_video(local_path, folder_id):
    service = get_drive_service()
    file_metadata = {
        'name': os.path.basename(local_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(local_path, mimetype='video/mp4', resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file['id']

