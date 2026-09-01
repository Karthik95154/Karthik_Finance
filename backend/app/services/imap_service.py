import imaplib
import email
from email.header import decode_header
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import asyncio
from app.core.security_util import decrypt_data

logger = logging.getLogger(__name__)

def clean_header(header_val: str) -> str:
    """Decodes email headers correctly (handles UTF-8, etc.)."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        header_text = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                header_text.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                header_text.append(part)
        return "".join(header_text).strip()
    except Exception as e:
        logger.warning(f"Failed to decode header '{header_val}': {e}")
        return str(header_val)

def parse_email_date(date_str: str) -> datetime:
    """Parses email received date safely using parsedate_tz and mktime_tz for timezone-aware local normalization."""
    if not date_str:
        return datetime.now()
    try:
        date_tuple = email.utils.parsedate_tz(date_str)
        if date_tuple:
            return datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
        return datetime.now()
    except Exception as e:
        logger.warning(f"Failed to parse email date '{date_str}': {e}")
        return datetime.now()

def run_imap_polling(config: Dict[str, Any], window_hours: int = 24) -> Dict[str, Any]:
    """
    Synchronous IMAP polling operations.
    Connects to the server, fetches emails from the last `window_hours`,
    and parses out supported attachments with deep diagnostic logging.
    """
    start_total = time.perf_counter()
    logger.info("POLL START")
    
    imap_server = config.get("imap_server")
    imap_port = int(config.get("imap_port") or 993)
    email_address = config.get("email_address")
    encrypted_password = config.get("password")
    
    password = decrypt_data(encrypted_password)
    
    # 1. IMAP Connection / Login
    start_conn = time.perf_counter()
    logger.info(f"Connecting to IMAP server {imap_server}:{imap_port} for {email_address}...")
    mail = imaplib.IMAP4_SSL(imap_server, imap_port)
    logger.info("IMAP CONNECTED")
    
    attachments = []
    errors = []
    attachments_found_count = 0
    
    # Timing variables (in ms)
    connect_time_ms = 0
    search_time_ms = 0
    header_fetch_time_ms = 0
    full_fetch_time_ms = 0
    mime_parse_time_ms = 0
    attachment_extract_time_ms = 0
    hash_time_ms = 0
    
    try:
        mail.login(email_address, password)
        logger.info("LOGIN SUCCESS")
        
        status, select_info = mail.select("INBOX")
        logger.info("INBOX SELECTED")
        connect_time_ms = (time.perf_counter() - start_conn) * 1000.0
        
        # 2. IMAP Search / Select
        start_search = time.perf_counter()
        total_messages = 0
        if status == "OK" and select_info and select_info[0]:
            try:
                total_messages = int(select_info[0])
            except ValueError:
                pass
                
        logger.info(f"Total messages in INBOX = {total_messages}")
        search_time_ms = (time.perf_counter() - start_search) * 1000.0
        
        now_time = datetime.now()
        poll_start_time = now_time - timedelta(hours=window_hours)
        
        # 3. Header Batch Fetching
        start_header = time.perf_counter()
        scan_limit = 100
        email_ids = []
        headers_map = {}
        
        if total_messages > 0:
            start_seq = max(1, total_messages - scan_limit + 1)
            end_seq = total_messages
            # Fetch headers for range in a single batch request
            logger.info(f"Fetching headers in batch for messages {start_seq} to {end_seq}...")
            range_str = f"{start_seq}:{end_seq}"
            try:
                res, batch_data = mail.fetch(range_str, "(BODY[HEADER.FIELDS (DATE SUBJECT FROM MESSAGE-ID CONTENT-TYPE)])")
                if res == "OK" and batch_data:
                    for item in batch_data:
                        if isinstance(item, tuple):
                            # Parse sequence number from response header prefix (e.g. b'5538 (BODY[HEADER...')
                            meta_part = item[0].decode("utf-8", errors="ignore").strip()
                            seq_num = meta_part.split()[0]
                            header_bytes = item[1]
                            headers_map[seq_num] = header_bytes
            except Exception as batch_err:
                logger.error(f"Failed to fetch headers in batch: {batch_err}. Falling back to sequential fetch.")
            
            # Retrieve sequence numbers in list
            email_ids = [str(x) for x in range(start_seq, end_seq + 1)]
            
        logger.info(f"MESSAGES RETURNED = {len(email_ids)}")
        header_fetch_time_ms = (time.perf_counter() - start_header) * 1000.0
        
        # Parse dates and filter sequence numbers within the window
        candidate_ids = []
        email_metadata_map = {}
        
        for msg_id_str in email_ids:
            header_bytes = headers_map.get(msg_id_str)
            if not header_bytes:
                continue
            try:
                msg_headers = email.message_from_bytes(header_bytes)
                raw_date_header = msg_headers.get("Date", "")
                received_date = parse_email_date(raw_date_header)
                
                # Check if it is within the window hours
                if received_date >= poll_start_time:
                    candidate_ids.append(msg_id_str)
                    email_metadata_map[msg_id_str] = {
                        "subject": clean_header(msg_headers.get("Subject", "(No Subject)")),
                        "sender": clean_header(msg_headers.get("From", "")),
                        "received_date": received_date,
                        "message_id": msg_headers.get("Message-ID", ""),
                    }
            except Exception as e:
                logger.warning(f"Error pre-parsing headers for message {msg_id_str}: {e}")
                
        # Batch fetch BODYSTRUCTURE for candidate sequence numbers
        bodystructures_map = {}
        if candidate_ids:
            seqs_str = ",".join(candidate_ids)
            logger.info(f"Fetching BODYSTRUCTURE in batch for {len(candidate_ids)} candidate messages...")
            try:
                res, bs_data = mail.fetch(seqs_str.encode("utf-8"), "(BODYSTRUCTURE)")
                if res == "OK" and bs_data:
                    for item in bs_data:
                        raw_bytes = item[0] if isinstance(item, tuple) else item
                        if isinstance(raw_bytes, bytes):
                            meta_part = raw_bytes.decode("utf-8", errors="ignore").strip()
                            parts = meta_part.split(maxsplit=2)
                            if len(parts) >= 3:
                                seq_num = parts[0]
                                bs_str = parts[2]
                                bodystructures_map[seq_num] = bs_str
            except Exception as bs_err:
                logger.error(f"Failed to fetch BODYSTRUCTURE in batch: {bs_err}")

        # Iterate over candidate emails in reverse order (most recent first)
        for msg_id_str in reversed(candidate_ids):
            try:
                metadata = email_metadata_map.get(msg_id_str)
                if not metadata:
                    continue
                
                subject = metadata["subject"]
                sender = metadata["sender"]
                received_date = metadata["received_date"]
                message_id = metadata["message_id"]
                
                logger.info(f"MESSAGE {msg_id_str} | date: {received_date} | subject: {subject} | sender: {sender}")
                
                # Retrieve BODYSTRUCTURE
                meta_str = bodystructures_map.get(msg_id_str)
                
                # Optimize: Check if BODYSTRUCTURE contains any allowed attachment extensions.
                # Loose case-insensitive search to guarantee ZERO false negatives.
                has_candidate = False
                if meta_str:
                    meta_lower = meta_str.lower()
                    if any(ext in meta_lower for ext in ("pdf", "png", "jpg", "jpeg", "tif", "tiff")):
                        has_candidate = True
                
                if not has_candidate:
                    logger.info("  EMAIL EXCLUDED: No supported attachments (.pdf, .png, .jpg, .jpeg, .tif, .tiff) in BODYSTRUCTURE")
                    continue
                
                # 4. Full Email Fetching (RFC822)
                start_full_fetch = time.perf_counter()
                logger.info(f"  --> Date & BODYSTRUCTURE check passed. Downloading full message body...")
                res, msg_data = mail.fetch(msg_id_str.encode("utf-8"), "(RFC822)")
                if res != "OK" or not msg_data or not msg_data[0]:
                    logger.warning(f"  Full fetch failed for ID {msg_id_str}. Status: {res}")
                    full_fetch_time_ms += (time.perf_counter() - start_full_fetch) * 1000.0
                    continue
                full_fetch_time_ms += (time.perf_counter() - start_full_fetch) * 1000.0
                
                # 5. MIME Parsing
                start_mime = time.perf_counter()
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                parts_list = list(msg.walk())
                logger.info(f"  MIME ATTACHMENTS FOUND = {len(parts_list)}")
                mime_parse_time_ms += (time.perf_counter() - start_mime) * 1000.0
                
                # Walk through MIME parts to find attachments and email body
                email_body_text = ""
                for index, part in enumerate(parts_list):
                    part_content_type = part.get_content_type()
                    content_disposition = part.get("Content-Disposition", "")
                    
                    if part.get_content_maintype() == "multipart":
                        continue
                        
                    # Capture email body (plain text preferred)
                    if part_content_type in ("text/plain", "text/html") and "attachment" not in content_disposition.lower():
                        try:
                            decoded_body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            if part_content_type == "text/plain":
                                email_body_text = decoded_body  # Prefer plain text
                            elif not email_body_text:
                                email_body_text = decoded_body  # Fallback to HTML if no plain text yet
                        except Exception as e:
                            logger.warning(f"  Failed to decode email body part: {e}")
                        continue
                    
                    raw_filename = part.get_filename()
                    if not raw_filename:
                        continue
                    
                    attachments_found_count += 1
                    decoded_filename = clean_header(raw_filename)
                    
                    logger.info(f"  ATTACHMENT {decoded_filename} | size: {len(part.get_payload() or '')} raw characters | type: {part_content_type}")
                    
                    ext = decoded_filename.split(".")[-1].lower() if "." in decoded_filename else ""
                    allowed_exts = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}
                    is_allowed_ext = (ext in allowed_exts)
                    
                    logger.info(f"    EXTENSION CHECK = {'PASS' if is_allowed_ext else 'FAIL'}")
                    
                    if not is_allowed_ext:
                        errors.append({
                            "filename": decoded_filename,
                            "reason": f"Unsupported file extension '.{ext}'"
                        })
                        continue
                    
                    # 6. Attachment extraction/download bytes
                    start_extract = time.perf_counter()
                    try:
                        content_bytes = part.get_payload(decode=True)
                    except Exception as payload_err:
                        logger.error(f"    Error decoding payload for attachment {decoded_filename}: {payload_err}")
                        errors.append({
                            "filename": decoded_filename,
                            "reason": f"Payload decode failed: {str(payload_err)}"
                        })
                        attachment_extract_time_ms += (time.perf_counter() - start_extract) * 1000.0
                        continue
                        
                    attachment_extract_time_ms += (time.perf_counter() - start_extract) * 1000.0
                    
                    if content_bytes is None or len(content_bytes) == 0:
                        logger.info("    EXTENSION CHECK = FAIL (empty payload)")
                        errors.append({
                            "filename": decoded_filename,
                            "reason": "Payload is empty"
                        })
                        continue
                    
                    # 7. SHA-256 hashing
                    start_hash = time.perf_counter()
                    sha255_hash = hashlib.sha256(content_bytes).hexdigest()
                    hash_time_ms += (time.perf_counter() - start_hash) * 1000.0
                    
                    # Convert naive received_date to timezone-aware UTC datetime for the database
                    received_date_utc = received_date.astimezone(timezone.utc)
                    
                    attachments.append({
                        "email_subject": subject,
                        "email_sender": sender,
                        "email_received_at": received_date_utc,
                        "email_message_id": message_id,
                        "email_body": email_body_text.strip(),
                        "filename": decoded_filename,
                        "mime_type": part_content_type,
                        "file_bytes": content_bytes,
                        "file_hash": sha255_hash
                    })
            except Exception as email_err:
                logger.error(f"Error parsing email ID {msg_id_str}: {email_err}", exc_info=True)
                errors.append({
                    "filename": f"Email ID {msg_id_str}",
                    "reason": f"MIME parser crash: {str(email_err)}"
                })
                
        total_time_ms = (time.perf_counter() - start_total) * 1000.0
        logger.info(f"POLL COMPLETE: Found {attachments_found_count} attachments, accepted {len(attachments)} attachments.")
        
        # Log backend internal timings
        logger.info("--- IMAP POLLING TIMINGS ---")
        logger.info(f"IMAP connection/login: {connect_time_ms:.2f} ms")
        logger.info(f"IMAP search: {search_time_ms:.2f} ms")
        logger.info(f"Header fetching: {header_fetch_time_ms:.2f} ms")
        logger.info(f"Full email fetching: {full_fetch_time_ms:.2f} ms")
        logger.info(f"MIME parsing: {mime_parse_time_ms:.2f} ms")
        logger.info(f"Attachment extraction/download: {attachment_extract_time_ms:.2f} ms")
        logger.info(f"SHA-256 hashing: {hash_time_ms:.2f} ms")
        logger.info(f"IMAP internal total: {total_time_ms:.2f} ms")
        
        return {
            "attachments": attachments,
            "errors": errors,
            "emails_checked": len(email_ids),
            "attachments_found": attachments_found_count,
            "timings": {
                "imap_connection_login_ms": connect_time_ms,
                "imap_search_ms": search_time_ms,
                "header_fetching_ms": header_fetch_time_ms,
                "full_email_fetching_ms": full_fetch_time_ms,
                "mime_parsing_ms": mime_parse_time_ms,
                "attachment_extraction_ms": attachment_extract_time_ms,
                "sha256_hashing_ms": hash_time_ms,
                "imap_internal_total_ms": total_time_ms
            }
        }
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass

def test_imap_connection_sync(config: Dict[str, Any]) -> None:
    """Synchronous test of IMAP connection and login with safe diagnostic logs."""
    imap_server = config.get("imap_server")
    imap_port = int(config.get("imap_port") or 993)
    email_address = config.get("email_address")
    password = config.get("password")
    
    # Safe mask for email address
    masked_email = "N/A"
    if email_address:
        parts = email_address.split("@")
        if len(parts) == 2:
            masked_email = f"{parts[0][:3]}***@{parts[1]}"
        else:
            masked_email = "***"
            
    logger.info(f"IMAP HOST = {imap_server}")
    logger.info(f"IMAP PORT = {imap_port}")
    logger.info(f"EMAIL = {masked_email}")
    logger.info(f"PASSWORD AVAILABLE = {'YES' if password else 'NO'}")
    
    # Verify decryption
    decryption_success = "SUCCESS" if password and len(password) > 0 and not password.startswith("gAAAA") else "FAIL"
    logger.info(f"PASSWORD DECRYPTION = {decryption_success}")
    
    mail = None
    ssl_success = "FAIL"
    login_success = "FAIL"
    error_msg = "None"
    
    try:
        # SSL Connection
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        ssl_success = "SUCCESS"
        logger.info(f"SSL CONNECTION = {ssl_success}")
        
        # Login
        mail.login(email_address, password)
        login_success = "SUCCESS"
        logger.info(f"GMAIL LOGIN = {login_success}")
        logger.info(f"ERROR = {error_msg}")
        
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            raise ValueError("Failed to select INBOX.")
            
    except Exception as e:
        error_msg = str(e)
        if ssl_success == "FAIL":
            logger.info(f"SSL CONNECTION = {ssl_success}")
        logger.info(f"GMAIL LOGIN = {login_success}")
        logger.info(f"ERROR = {error_msg}")
        raise e
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass


class IMAPService:
    async def validate_connection(self, config: Dict[str, Any]) -> None:
        """Validate connection details asynchronously by offloading to a thread."""
        await asyncio.to_thread(test_imap_connection_sync, config)

    async def poll_mailbox(self, config: Dict[str, Any], window_hours: int = 24) -> Dict[str, Any]:
        """Poll mailbox asynchronously by offloading the blocking IMAP operations to a thread."""
        return await asyncio.to_thread(run_imap_polling, config, window_hours)

imap_service = IMAPService()
