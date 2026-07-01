import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Room, Message, RoomMember

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer that handles real-time chat for a single room.

    Lifecycle:
        connect()    → Validate session, check membership, join the room group.
        receive()    → Save the incoming message to DB, broadcast to the group.
        disconnect() → Leave the room group.
    """

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        """Accept the WebSocket only if the user is an approved room member."""
        session = self.scope.get('session', {})
        self.room_id = session.get('room_id')
        self.room_group_name = f'chat_{self.room_id}'

        if not self.room_id:
            await self.close()
            return

        try:
            room = await self._get_room(self.room_id)
            session_key = getattr(session, 'session_key', None)

            if not session_key:
                await self.close()
                return

            if not await self._is_approved(room, session_key):
                await self.close()
                return

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        except Exception:
            logger.exception('WebSocket connect failed for room %s', self.room_id)
            await self.close()

    async def disconnect(self, close_code):
        """Leave the room's channel-layer group."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # ------------------------------------------------------------------
    # Incoming messages
    # ------------------------------------------------------------------

    async def receive(self, text_data):
        """Handle an incoming chat message: validate, save, and broadcast."""
        try:
            data = json.loads(text_data)
            message = data.get('message')

            if not isinstance(message, str) or not message.strip():
                return

            session = self.scope.get('session', {})
            username = session.get('username')
            if not username:
                return

            room = await self._get_room(self.room_id)
            saved = await self._save_message(room, username, message)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                    'timestamp': saved.timestamp.strftime('%H:%M'),
                },
            )
        except Exception:
            logger.exception('WebSocket receive failed for room %s', self.room_id)

    # ------------------------------------------------------------------
    # Outgoing event handlers (called by channel-layer group_send)
    # ------------------------------------------------------------------

    async def chat_message(self, event):
        """Forward a chat message to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'timestamp': event.get('timestamp'),
        }))

    async def pending_count(self, event):
        """Push the updated pending-request count to connected clients."""
        await self.send(text_data=json.dumps({
            'type': 'pending_count',
            'count': event['count'],
        }))

    # ------------------------------------------------------------------
    # Database helpers (run in a thread-safe sync context)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _get_room(self, room_id):
        return Room.objects.get(id=room_id)

    @database_sync_to_async
    def _is_approved(self, room, session_key):
        return RoomMember.objects.filter(
            room=room, session_key=session_key, status='approved',
        ).exists()

    @database_sync_to_async
    def _save_message(self, room, username, content):
        return Message.objects.create(room=room, user=username, content=content)