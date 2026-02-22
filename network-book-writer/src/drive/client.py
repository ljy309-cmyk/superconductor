"""구글 드라이브 클라이언트 - 파일 읽기/쓰기/삭제"""

import io
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]


class GoogleDriveClient:
    """구글 드라이브 API 클라이언트"""

    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None

    def authenticate(self) -> None:
        """OAuth2 인증 수행"""
        creds = None
        token_file = Path(self.token_path)

        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w") as f:
                f.write(creds.to_json())

        self.service = build("drive", "v3", credentials=creds)
        logger.info("구글 드라이브 인증 완료")

    def read_file(self, file_id: str) -> str:
        """파일 ID로 문서 내용 읽기 (Google Docs → 텍스트)"""
        # Google Docs인 경우 text/plain으로 export
        try:
            content = self.service.files().export(fileId=file_id, mimeType="text/plain").execute()
            return content.decode("utf-8")
        except Exception:
            # 일반 파일인 경우 직접 다운로드
            content = self.service.files().get_media(fileId=file_id).execute()
            if isinstance(content, bytes):
                return content.decode("utf-8")
            return str(content)

    def list_files(self, folder_id: str, name_contains: str | None = None) -> list[dict]:
        """폴더 내 파일 목록 조회"""
        query = f"'{folder_id}' in parents and trashed = false"
        if name_contains:
            query += f" and name contains '{name_contains}'"

        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime)",
            orderBy="name",
        ).execute()

        return results.get("files", [])

    def upload_file(self, name: str, content: str, folder_id: str, mime_type: str = "text/plain") -> str:
        """텍스트 파일을 구글 드라이브에 업로드, 파일 ID 반환"""
        file_metadata = {
            "name": name,
            "parents": [folder_id],
        }

        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype=mime_type,
            resumable=True,
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()

        file_id = file.get("id")
        logger.info(f"파일 업로드 완료: {name} (ID: {file_id})")
        return file_id

    def update_file(self, file_id: str, content: str, mime_type: str = "text/plain") -> None:
        """기존 파일 내용 업데이트"""
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype=mime_type,
            resumable=True,
        )

        self.service.files().update(
            fileId=file_id,
            media_body=media,
        ).execute()

        logger.info(f"파일 업데이트 완료: {file_id}")

    def delete_file(self, file_id: str) -> None:
        """파일 삭제"""
        self.service.files().delete(fileId=file_id).execute()
        logger.info(f"파일 삭제 완료: {file_id}")

    def create_folder(self, name: str, parent_folder_id: str) -> str:
        """하위 폴더 생성, 폴더 ID 반환"""
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }

        folder = self.service.files().create(
            body=file_metadata,
            fields="id",
        ).execute()

        folder_id = folder.get("id")
        logger.info(f"폴더 생성 완료: {name} (ID: {folder_id})")
        return folder_id
