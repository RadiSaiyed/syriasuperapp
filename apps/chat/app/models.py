import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint, Text, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Text


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    devices = relationship("Device", back_populates="user")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(String(64), nullable=False)  # client-generated identifier
    public_key = Column(Text, nullable=False)  # base64 or PEM of Curve25519/Ed25519 (client-defined)
    device_name = Column(String(64), nullable=True)
    push_token = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("user_id", "contact_user_id", name="uq_contact"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    contact_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_a = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user_b = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_group = Column(Boolean, nullable=False, default=False)
    name = Column(String(128), nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    avatar_blob_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    archived = Column(Boolean, nullable=False, default=False)
    archived_at = Column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    sender_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    sender_device_id = Column(String(64), nullable=False)
    recipient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ciphertext = Column(Text, nullable=False)
    delivered = Column(Boolean, nullable=False, default=False)
    read = Column(Boolean, nullable=False, default=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    content_type = Column(String(64), nullable=True)
    filename = Column(String(256), nullable=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    ciphertext_b64 = Column(Text, nullable=False)  # store base64 to keep text
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    blob_id = Column(UUID(as_uuid=True), nullable=True)


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction_unique"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    emoji = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("user_id", "blocked_user_id", name="uq_block"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    blocked_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conv_part"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(16), nullable=False, default="member")  # owner|admin|member
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Blob(Base):
    __tablename__ = "blobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    data = Column(LargeBinary, nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MessageReceipt(Base):
    __tablename__ = "message_receipts"
    __table_args__ = (UniqueConstraint("message_id", "device_id", name="uq_receipt"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(String(64), nullable=False)
    delivered = Column(Boolean, nullable=False, default=False)
    read = Column(Boolean, nullable=False, default=False)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class GroupInvite(Base):
    __tablename__ = "group_invites"
    __table_args__ = (UniqueConstraint("code", name="uq_group_invite_code"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    code = Column(String(64), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=False, default=0)  # 0=infinite
    used_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModAudit(Base):
    __tablename__ = "mod_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(64), nullable=False)
    target_type = Column(String(32), nullable=False)
    target_id = Column(String(64), nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
