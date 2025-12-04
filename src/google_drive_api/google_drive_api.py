#NOTE: YOU WILL NEED TO MAKE SURE YOU HAVE THE FILE "credentials.json" IN ORDER TO ACCESS THE API



googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
import io # Required for downloading file content
import mimetypes # Required for guessing MIME type during upload
#NOTE: You might have to do pip install on a few google libraries before you can use this code
# Define the permissions scope
# 'drive.file' scope grants access only to files created or opened by this app.
SCOPES = ['https://www.googleapis.com/auth/drive.file'] 

def get_drive_service():
    """Authenticates the user and returns the Google Drive API service object."""
    creds = None
    # 1. Load existing credentials (token.pickle)
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # 2. If no valid creds, refresh or perform OAuth login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token silently
            creds.refresh(Request())
        else:
            # Perform full login flow, requires 'credentials.json' in the same directory
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # 3. Save the new/refreshed token
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service

def upload_to_drive(file_path, folder_id=None):
    """
    Uploads a file to Google Drive.
    
    :param file_path: The path to the local file to upload.
    :param folder_id: The Google Drive ID of the target folder. None for root.
    :return: The ID of the uploaded file, or None on failure.
    """
    try:
        service = get_drive_service()
        
        # 1. Guess the MIME type from the file extension
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream' # Default if type cannot be guessed

        # 2. Set file metadata (name and parent folder)
        file_metadata = {'name': os.path.basename(file_path)}
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        # 3. Create media object for upload
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        
        # 4. Execute the upload
        uploaded = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id'
        ).execute()
        
        file_id = uploaded.get('id')
        print(f"✅ Successfully uploaded '{os.path.basename(file_path)}'. ID: {file_id}")
        return file_id
        
    except FileNotFoundError:
        print(f"❌ Error: The file was not found at path: {file_path}")
        return None
    except Exception as e:
        print(f"❌ An error occurred during upload: {e}")
        return None

def download_from_drive(file_id, local_file_path):
    """
    Downloads a file from Google Drive using its file ID.
    TO FIND THE FILE ID ON GOOGLE DRIVE, SIMPLY GO TO THE GOOGLE DRIVE WEBSITE, CLICK ON THE THING YOU WANT, AND THE LONG STRING OF NUMBERS AND CHARACTERS AFTER "/folders" IN THE WEB ADDRESS IS IT
    :param file_id: The ID of the file to download from Drive.
    :param local_file_path: The path and name to save the file locally.
    :return: True on success, False on failure.
    """
    try:
        service = get_drive_service()

        # 1. Execute the download request using alt='media'
        request = service.files().get(fileId=file_id, alt='media')
        file_content = request.execute()

        # 2. Write the downloaded byte content to a local file
        with open(local_file_path, 'wb') as f:
            f.write(file_content)

        print(f"⬇️ Successfully downloaded file ID {file_id} to '{local_file_path}'.")
        return True

    except Exception as e:
        print(f"❌ An error occurred during download for file ID {file_id}: {e}")
        return False


# ----------------------------------------------------------------------
# EXAMPLE USAGE DEMONSTRATION
# ----------------------------------------------------------------------

# --- Configuration (UPDATE THESE VALUES) ---
# NOTE: Ensure 'testimages/temp_upload.txt' exists for this example to work!
# We use a simple text file for easy testing. Replace with your actual image path.
EXAMPLE_LOCAL_UPLOAD_PATH = "testimages/temp_upload.txt"
EXAMPLE_LOCAL_DOWNLOAD_PATH = "downloaded_file_copy.txt"
# Replace with the actual ID of your target folder if desired, otherwise leave None
TARGET_FOLDER_ID = None 

# --- Create a dummy file for testing the upload (optional, but helpful) ---
if not os.path.exists(EXAMPLE_LOCAL_UPLOAD_PATH):
    os.makedirs(os.path.dirname(EXAMPLE_LOCAL_UPLOAD_PATH), exist_ok=True)
    with open(EXAMPLE_LOCAL_UPLOAD_PATH, 'w') as f:
        f.write("This is a test file for Google Drive upload and download.")
    print(f"Created dummy file at: {EXAMPLE_LOCAL_UPLOAD_PATH}")

# 1. UPLOAD TEST
print("\n--- Starting Upload Test ---")
uploaded_id = upload_to_drive(EXAMPLE_LOCAL_UPLOAD_PATH, folder_id=TARGET_FOLDER_ID)

# 2. DOWNLOAD TEST
if uploaded_id:
    print("\n--- Starting Download Test ---")
    download_from_drive(uploaded_id, EXAMPLE_LOCAL_DOWNLOAD_PATH)

    # Clean up the downloaded copy for re-running the script
    if os.path.exists(EXAMPLE_LOCAL_DOWNLOAD_PATH):
        print(f"\nSuccessfully downloaded and saved: {EXAMPLE_LOCAL_DOWNLOAD_PATH}")
        # Optionally, you can delete the local copy after verification
        # os.remove(EXAMPLE_LOCAL_DOWNLOAD_PATH)
        # print(f"Cleaned up local file: {EXAMPLE_LOCAL_DOWNLOAD_PATH}")
