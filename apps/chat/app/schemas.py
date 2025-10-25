from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RequestOtpIn(BaseModel):
    phone: str


class VerifyOtpIn(BaseModel):
    phone: str
    otp: str
    session_id: Optional[str] = None
    name: Optional[str] = None


class PublishKeyIn(BaseModel):
    device_id: str
    public_key: str
    device_name: Optional[str] = None
    push_token: Optional[str] = None


class DeviceOut(BaseModel):
    device_id: str
    public_key: str
    device_name: Optional[str] = None
    created_at: datetime


class AddContactIn(BaseModel):
    phone: str


class ContactOut(BaseModel):
    user_id: str
    phone: str
    name: Optional[str] = None


class SendMessageIn(BaseModel):
    recipient_user_id: str
    sender_device_id: str
    ciphertext: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: str
    sender_device_id: str
    recipient_user_id: str
    ciphertext: str
    delivered: bool
    read: bool
    sent_at: datetime


class InboxOut(BaseModel):
    messages: List[MessageOut]


class ConversationOut(BaseModel):
    id: str
    user_a: str
    user_b: str
    last_message_at: datetime


class ConversationsOut(BaseModel):
    conversations: List[ConversationOut]


class AttachmentCreateIn(BaseModel):
    content_type: Optional[str] = None
    filename: Optional[str] = None
    ciphertext_b64: str


class AttachmentOut(BaseModel):
    id: str
    message_id: str
    content_type: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: int
    ciphertext_b64: str
    created_at: datetime
    download_url: Optional[str] = None


class AttachmentsOut(BaseModel):
    attachments: List[AttachmentOut]


class ReactionCreateIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


class ReactionOut(BaseModel):
    id: str
    message_id: str
    user_id: str
    emoji: str
    created_at: datetime


class ReactionsOut(BaseModel):
    reactions: List[ReactionOut]


class PresenceOut(BaseModel):
    user_id: str
    online: bool
    last_seen: Optional[datetime] = None


class TypingIn(BaseModel):
    conversation_id: Optional[str] = None
    peer_user_id: Optional[str] = None
    is_typing: bool = True


class ConversationSummary(BaseModel):
    id: str
    user_a: str
    user_b: str
    last_message_at: datetime
    unread_count: int


class ConversationsSummaryOut(BaseModel):
    conversations: List[ConversationSummary]
